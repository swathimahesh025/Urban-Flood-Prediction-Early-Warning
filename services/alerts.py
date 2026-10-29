
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


def send_smtp_alert_email(recipient_email, subject, body_html):
    """Send an alert email using the configured SMTP server."""

    print("\n========== SMTP EMAIL DEBUG ==========")
    print("DEBUG: Email function called")
    print("DEBUG: SMTP username configured:", bool(Config.MAIL_USERNAME))
    print("DEBUG: SMTP password configured:", bool(Config.MAIL_PASSWORD))
    print("DEBUG: SMTP server:", Config.MAIL_SERVER)
    print("DEBUG: SMTP port:", Config.MAIL_PORT)

    if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        message = (
            "SMTP credentials are missing. Check MAIL_USERNAME "
            "and MAIL_PASSWORD in your .env file."
        )
        logger.error(message)
        print("DEBUG:", message)
        return False, message

    target_email = recipient_email or Config.ALERT_RECIPIENT_EMAIL

    if not target_email:
        message = "No recipient email configured."
        logger.error(message)
        print("DEBUG:", message)
        return False, message

    server = None

    try:
        sender_email = Config.MAIL_USERNAME

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"HydroAlert Early Warning <{sender_email}>"
        msg["To"] = target_email

        msg.attach(MIMEText(body_html, "html", "utf-8"))

        print("DEBUG: Connecting to SMTP server...")

        server = smtplib.SMTP(
            Config.MAIL_SERVER,
            int(Config.MAIL_PORT),
            timeout=20
        )
        server.ehlo()

        if Config.MAIL_USE_TLS:
            server.starttls()
            server.ehlo()

        print("DEBUG: Logging in to SMTP server...")
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)

        print("DEBUG: Sending email to:", target_email)
        server.sendmail(
            sender_email,
            [target_email],
            msg.as_string()
        )

        logger.info("Email accepted by SMTP server for %s", target_email)
        print("DEBUG: SMTP accepted the email for delivery.")
        return True, "Email accepted by SMTP server."

    except Exception as e:
        logger.exception("SMTP email delivery failed")
        print("DEBUG: SMTP ERROR:", repr(e))
        return False, f"SMTP Error: {str(e)}"

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def format_alert_email_html(
    location,
    rainfall,
    probability,
    parameters,
    timestamp,
    risk_level
):
    """Generate an HTML email with the predicted risk level."""

    risk_styles = {
        "Low Risk": ("#15803d", "#f0fdf4", "#bbf7d0"),
        "Medium Risk": ("#b45309", "#fffbeb", "#fde68a"),
        "High Risk": ("#dc2626", "#fef2f2", "#fecaca"),
    }

    header_color, badge_bg, badge_border = risk_styles.get(
        risk_level,
        ("#475569", "#f8fafc", "#cbd5e1")
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f8fafc;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: auto;
                background: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid #e2e8f0;
            }}
            .header {{
                background: {header_color};
                color: white;
                padding: 24px;
                text-align: center;
            }}
            .content {{
                padding: 24px;
                color: #1e293b;
            }}
            .badge {{
                display: inline-block;
                background: {badge_bg};
                color: {header_color};
                padding: 6px 14px;
                border-radius: 999px;
                font-weight: bold;
                border: 1px solid {badge_border};
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #e2e8f0;
            }}
            td:first-child {{
                font-weight: bold;
                color: #64748b;
            }}
            .action {{
                background: {badge_bg};
                border-left: 4px solid {header_color};
                padding: 16px;
                margin: 20px 0;
            }}
            .footer {{
                background: #f1f5f9;
                padding: 16px;
                text-align: center;
                font-size: 12px;
                color: #64748b;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{risk_level.upper()} FLOOD ALERT</h1>
                <p>Urban Flood Prediction &amp; Early Warning System</p>
            </div>

            <div class="content">
                <p><span class="badge">{risk_level.upper()} DETECTED</span></p>

                <p>
                    The system detected <strong>{risk_level}</strong>
                    for <strong>{location}</strong>.
                </p>

                <table>
                    <tr><td>Location</td><td>{location}</td></tr>
                    <tr><td>Risk Level</td><td>{risk_level}</td></tr>
                    <tr><td>Model Probability</td>
                        <td>{probability:.1f}%</td></tr>
                    <tr><td>Rainfall</td><td>{rainfall} mm</td></tr>
                    <tr><td>Humidity</td>
                        <td>{parameters.get('humidity', 'N/A')}%</td></tr>
                    <tr><td>Pressure</td>
                        <td>{parameters.get('pressure', 'N/A')} hPa</td></tr>
                    <tr><td>Timestamp</td><td>{timestamp}</td></tr>
                </table>

                <div class="action">
                    <h3>Safety Recommendations</h3>
                    <ul>
                        <li><strong>Low Risk:</strong> Monitor weather
                        updates and keep drainage areas clear.</li>
                        <li><strong>Medium Risk:</strong> Monitor official
                        warnings and avoid flood-prone roads.</li>
                        <li><strong>High Risk:</strong> Follow local
                        emergency instructions and avoid floodwater.</li>
                    </ul>
                    <p>
                        Follow instructions from local disaster
                        management authorities.
                    </p>
                </div>
            </div>

            <div class="footer">
                Automated alert from the Urban Flood Prediction System.
            </div>
        </div>
    </body>
    </html>
    """


def format_alert_sms_text(location, rainfall, probability, risk_level):
    """Generate SMS text; this function does not send an SMS."""

    return (
        f"Urban Flood Alert: {risk_level} detected in {location}. "
        f"Rainfall: {rainfall} mm. "
        f"Model probability: {probability:.1f}%. "
        "Monitor conditions and follow official safety advice."
    )


def process_flood_alert(
    prediction_dict,
    recipient_email=None,
    user_id=None,
    prediction_id=None
):
    """Process alerts for Low, Medium, and High Risk predictions."""

    risk_level = prediction_dict.get("risk_level")

    print("\n========== FLOOD ALERT DEBUG ==========")
    print("DEBUG: process_flood_alert() was called")
    print("DEBUG: Prediction risk level:", repr(risk_level))
    print("DEBUG: Prediction data:", prediction_dict)

    allowed_risks = ("Low Risk", "Medium Risk", "High Risk")

    if risk_level not in allowed_risks:
        message = f"Unrecognized risk level: {risk_level!r}"
        logger.warning(message)
        print("DEBUG:", message)

        return {
            "alert_triggered": False,
            "email_sent": False,
            "status": "Inactive",
            "message": message
        }

    location = prediction_dict.get("location_name", "Target Area")
    rainfall = prediction_dict.get("rainfall", 0.0)
    probability = prediction_dict.get("probability", 0.0)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    target_email = (
        recipient_email
        or Config.ALERT_RECIPIENT_EMAIL
    )

    if not target_email:
        message = "No recipient email configured."
        logger.error(message)
        print("DEBUG:", message)

        return {
            "alert_triggered": True,
            "email_sent": False,
            "recipient": None,
            "status": "Failed - No Recipient",
            "message": message,
            "timestamp": timestamp
        }

    subject = f"{risk_level.upper()} FLOOD ALERT: {location}"

    html_content = format_alert_email_html(
        location=location,
        rainfall=rainfall,
        probability=probability,
        parameters=prediction_dict,
        timestamp=timestamp,
        risk_level=risk_level
    )

    sms_text = format_alert_sms_text(
        location,
        rainfall,
        probability,
        risk_level
    )

    # Attempt email delivery for all three risk levels.
    print("DEBUG: Preparing email for risk level:", risk_level)
    print("DEBUG: Recipient:", target_email)

    email_sent, email_message = send_smtp_alert_email(
        target_email,
        subject,
        html_content
    )

    if email_sent:
        status = f"SMTP accepted email for {target_email}"
        user_message = (
            f"{risk_level} alert email accepted by the SMTP server "
            f"for {target_email}. Check Inbox and Spam."
        )
    else:
        status = f"Email failed: {email_message}"
        user_message = (
            f"{risk_level} alert was generated, but email delivery "
            f"failed: {email_message}"
        )

    # Record the attempt in the database.
    try:
        from database.db import execute_query

        execute_query(
            """
            INSERT INTO alerts (
                user_id,
                prediction_id,
                recipient_email,
                location_name,
                risk_level,
                rainfall,
                status,
                message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                prediction_id,
                target_email,
                location,
                risk_level,
                rainfall,
                status,
                email_message
            )
        )

        print("DEBUG: Alert attempt recorded in database.")

    except Exception as e:
        logger.exception("Could not record alert to database")
        print("DEBUG: Database alert-recording error:", repr(e))

    result = {
        "alert_triggered": True,
        "email_sent": email_sent,
        "recipient": target_email,
        "status": status,
        "message": user_message,
        "sms_text": sms_text,
        "timestamp": timestamp
    }

    print("DEBUG: Final alert result:", result)
    print("=======================================\n")

    return result
