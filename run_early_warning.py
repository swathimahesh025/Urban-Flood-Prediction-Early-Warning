
import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import requests
from apscheduler.schedulers.blocking import BlockingScheduler

from database.db import init_db, fetch_all
from ml.predict import predict_flood_risk
from services.weather import KARNATAKA_MONITORED_ZONES
from services.alerts import send_smtp_alert_email

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "early_warning_state.json"

CHECK_MINUTES = int(os.getenv("EARLY_WARNING_INTERVAL_MINUTES", "30"))
FORECAST_HOURS = int(os.getenv("EARLY_WARNING_HOURS", "24"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("early_warning")

# Seven primary locations used by the existing dashboard.
LOCATION_KEYS = [
    "bengaluru urban",
    "dakshina kannada",
    "udupi",
    "uttara kannada",
    "shivamogga",
    "chikkamagaluru",
    "kodagu",
]


def fetch_hourly_forecast(zone):
    """Fetch hourly weather forecasts for the configured location."""
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": zone["lat"],
        "longitude": zone["lon"],
        "hourly": (
            "precipitation,relative_humidity_2m,temperature_2m,"
            "wind_speed_10m,surface_pressure"
        ),
        "forecast_hours": max(6, min(FORECAST_HOURS, 48)),
        "timezone": "Asia/Kolkata",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    hourly = response.json().get("hourly", {})
    times = hourly.get("time", [])

    required = [
        "precipitation",
        "relative_humidity_2m",
        "temperature_2m",
        "wind_speed_10m",
        "surface_pressure",
    ]

    if not times or any(key not in hourly for key in required):
        raise ValueError(
            "Forecast response is missing required hourly fields"
        )

    rows = []

    for i, stamp in enumerate(times):
        values = [
            hourly[key][i] if i < len(hourly[key]) else None
            for key in required
        ]

        if any(value is None for value in values):
            continue

        rows.append({
            "time": stamp,
            "rainfall": float(values[0]),
            "humidity": float(values[1]),
            "temperature": float(values[2]),
            # Open-Meteo wind speed is km/h; model feature is m/s.
            "wind_speed": float(values[3]) / 3.6,
            "pressure": float(values[4]),
        })

    return rows


def read_state():
    """Read previously sent alert event keys."""
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(state):
    """Persist alert state to prevent duplicate emails."""
    STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8"
    )


def email_body(zone_name, risk, probability, forecast_time, features):
    """Build the forecast email body."""
    return f"""<!doctype html>
<html>
<body style="font-family:Arial,sans-serif;line-height:1.5">
    <h2>{risk.upper()} FLOOD-RISK FORECAST — {zone_name}</h2>

    <p>
        The Urban Flood Prediction early-warning worker has identified
        a <b>{risk}</b> model classification for the forecast hour
        <b>{forecast_time} IST</b>.
    </p>

    <ul>
        <li>Forecast hourly precipitation:
            {features['rainfall']:.1f} mm</li>
        <li>Humidity: {features['humidity']:.0f}%</li>
        <li>Temperature: {features['temperature']:.1f} °C</li>
        <li>Wind speed: {features['wind_speed']:.1f} m/s</li>
        <li>Surface pressure: {features['pressure']:.1f} hPa</li>
        <li>Model probability for predicted class:
            {probability:.1f}%</li>
    </ul>

    <p>
        <b>Precaution:</b> Follow official IMD, KSNDMC, and local
        authority advisories. Avoid flooded roads and underpasses.
        This is an experimental model alert, not an official
        evacuation warning or a guarantee that flooding will occur.
    </p>

    <p>Forecasts can change; the system rechecks periodically.</p>
</body>
</html>"""


def run_early_warning():
    log.info(
        "Starting forecast scan for %s locations",
        len(LOCATION_KEYS)
    )

    try:
        users = fetch_all("SELECT id, name, email FROM users")
    except Exception:
        log.exception("Could not read registered users")
        return

    if not users:
        log.warning("No registered users found; no emails will be sent.")
        return

    state = read_state()

    # Open-Meteo times use Asia/Kolkata and have no UTC offset in the
    # returned strings. Compare them with the local clock.
    now = datetime.now()

    for key in LOCATION_KEYS:
        zone = KARNATAKA_MONITORED_ZONES.get(key)

        if not zone:
            log.warning("Configured location key not found: %s", key)
            continue

        try:
            forecasts = fetch_hourly_forecast(zone)
            predictions = []

            for row in forecasts:
                features = {
                    name: row[name]
                    for name in (
                        "rainfall",
                        "humidity",
                        "temperature",
                        "wind_speed",
                        "pressure",
                    )
                }

                result = predict_flood_risk(features)
                predictions.append((row, result))

            # Select the earliest upcoming forecast, regardless of
            # whether its predicted risk is Low, Medium, or High.
            upcoming = [
                (row, prediction)
                for row, prediction in predictions
                if datetime.fromisoformat(row["time"]) >= now
            ]

            upcoming.sort(
                key=lambda item: datetime.fromisoformat(item[0]["time"])
            )

            if not upcoming:
                log.info(
                    "%s: no valid upcoming forecast",
                    zone["canonical_name"]
                )
                continue

            row, pred = upcoming[0]
            risk = pred["risk_level"]
            forecast_time = row["time"]

            log.info(
                "Selected forecast: location=%s time=%s risk=%s "
                "rainfall=%.1f humidity=%.1f temperature=%.1f "
                "wind_speed=%.2f pressure=%.1f",
                zone["canonical_name"],
                forecast_time,
                risk,
                row["rainfall"],
                row["humidity"],
                row["temperature"],
                row["wind_speed"],
                row["pressure"],
            )

            # Define event_key BEFORE using it in the state dictionary.
            # A different location, forecast hour, or risk creates a
            # different event key.
            event_key = (
                f"{zone['canonical_name']}|"
                f"{forecast_time}|"
                f"{risk}"
            )

            zone_state_key = str(zone["id"])
            previous_event = state.get(zone_state_key, {})

            # Do not send the same forecast event again on every scan.
            if previous_event.get("event_key") == event_key:
                log.info(
                    "Duplicate alert suppressed: location=%s time=%s "
                    "risk=%s",
                    zone["canonical_name"],
                    forecast_time,
                    risk,
                )
                continue

            subject = (
                f"[{risk.upper()}] Flood-risk forecast: "
                f"{zone['canonical_name']} at {forecast_time} IST"
            )

            body = email_body(
                zone["canonical_name"],
                risk,
                pred["probability"],
                forecast_time,
                row,
            )

            successes = 0

            for user in users:
                email = (user.get("email") or "").strip()

                if not email:
                    continue

                ok, message = send_smtp_alert_email(
                    email,
                    subject,
                    body
                )

                if ok:
                    successes += 1
                else:
                    log.error(
                        "Email failed for user id %s: %s",
                        user.get("id"),
                        message,
                    )

            if successes:
                # Save the event only after at least one email succeeds.
                # This allows a later scan to retry if all sends fail.
                state[zone_state_key] = {
                    "event_key": event_key,
                    "risk_level": risk,
                    "forecast_time": forecast_time,
                    "last_sent_at": datetime.now().isoformat(),
                    "sent_count": successes,
                }

                write_state(state)

                log.warning(
                    "Alert sent for %s: %s at %s to %s users",
                    zone["canonical_name"],
                    risk,
                    forecast_time,
                    successes,
                )
            else:
                log.error(
                    "No emails sent for %s; check SMTP configuration",
                    zone["canonical_name"],
                )

        except Exception:
            log.exception(
                "Forecast scan failed for %s",
                zone["canonical_name"],
            )


def main():
    parser = argparse.ArgumentParser(
        description="Urban flood early-warning worker"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one scan and exit"
    )
    args = parser.parse_args()

    init_db()

    if args.once:
        run_early_warning()
        return

    scheduler = BlockingScheduler(timezone="Asia/Kolkata")

    scheduler.add_job(
        run_early_warning,
        "interval",
        minutes=CHECK_MINUTES,
        id="flood_forecast_scan",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now().astimezone(),
    )

    log.info(
        "Worker running continuously; scan interval=%s minutes, "
        "forecast horizon=%s hours",
        CHECK_MINUTES,
        FORECAST_HOURS,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Early-warning worker stopped")


if __name__ == "__main__":
    main()
