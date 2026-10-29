import os
import functools
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from database.db import init_db, execute_query, fetch_one, fetch_all
from ml.predict import predict_flood_risk, get_recommendations
from services.weather import get_karnataka_weather, match_karnataka_zone, KARNATAKA_MONITORED_ZONES
from services.geolocation import sanitize_coordinates, detect_place_name
from services.alerts import process_flood_alert

# Initialize Flask application
app = Flask(__name__)
app.config.from_object(Config)

# Ensure database tables and models are ready on initialization
with app.app_context():
    try:
        init_db()
    except Exception as e:
        app.logger.error(f"Failed to initialize database on startup: {e}")

# -------------------------------------------------------------
# Authentication Decorators
# -------------------------------------------------------------
def login_required(view_func):
    """Restricts access to authenticated users."""
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped_view

def admin_required(view_func):
    """Restricts access to administrators."""
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "admin_id" not in session:
            flash("Administrator login required.", "danger")
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped_view

# -------------------------------------------------------------
# Authentication Routes (User & Admin)
# -------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    """User registration."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("signup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("signup.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("signup.html")

        existing_user = fetch_one("SELECT id FROM users WHERE email = %s", (email,))
        if existing_user:
            flash("An account with this email address already exists.", "warning")
            return render_template("signup.html")

        pw_hash = generate_password_hash(password)
        try:
            user_id = execute_query(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, pw_hash)
            )
            session["user_id"] = user_id
            session["user_name"] = name
            session["user_email"] = email
            flash("Account registered successfully! Welcome aboard.", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Registration error: {e}", "danger")

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """User authentication."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = fetch_one("SELECT * FROM users WHERE email = %s", (email,))
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            flash(f"Welcome back, {user['name']}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        else:
            flash("Invalid email or password. Please try again.", "danger")

    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Dynamic password reset for registered users without token expiration."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not new_password or not confirm_password:
            flash("All fields are required to reset your password.", "danger")
            return render_template("forgot_password.html")

        if new_password != confirm_password:
            flash("New password and confirmation password do not match.", "danger")
            return render_template("forgot_password.html", email=email)

        if len(new_password) < 6:
            flash("Password must be at least 6 characters in length.", "danger")
            return render_template("forgot_password.html", email=email)

        user = fetch_one("SELECT id, name FROM users WHERE email = %s", (email,))
        if not user:
            flash("No registered account found with that email address.", "danger")
            return render_template("forgot_password.html")

        # Dynamically hash and update the password
        new_pw_hash = generate_password_hash(new_password)
        try:
            execute_query(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (new_pw_hash, email)
            )
            flash("Your password has been successfully updated! You can now sign in with your new password.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Error resetting password: {e}", "danger")
            return render_template("forgot_password.html", email=email)

    return render_template("forgot_password.html")

@app.route("/logout")
def logout():
    """Clears user session."""
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_email", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("home"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Separate administrator login."""
    if "admin_id" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = fetch_one("SELECT * FROM admin WHERE username = %s OR email = %s", (username, username))
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Admin authentication successful.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid administrator credentials.", "danger")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    """Clears admin session."""
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("admin_login"))

# -------------------------------------------------------------
# User Flow & Navigation Routes
# -------------------------------------------------------------
@app.route("/")
def home():
    """Root entry point: authenticated users go to dashboard, others go to login."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    """Main resident user dashboard with dual action modes (Auto-fetch GPS & Manual Location)."""
    return render_template("dashboard.html")

@app.route("/custom-location")
def custom_location():
    """Manual city/area search interface."""
    return render_template("custom_location.html")

@app.route("/not-applicable")
def not_applicable_view():
    """Renders location outside Karnataka surveillance zone page."""
    loc = request.args.get("location", "Selected Location")
    return render_template("not_applicable.html", queried_location=loc)

# -------------------------------------------------------------
# Prediction Pipeline Routes (Karnataka Designated Zones)
# -------------------------------------------------------------
@app.route("/predict/auto", methods=["POST"])
def predict_auto():
    """
    Handles GPS-based auto prediction with strict Karnataka zone validation.
    """
    if request.is_json:
        data = request.get_json() or {}
        lat = data.get("latitude")
        lon = data.get("longitude")
    else:
        lat = request.form.get("latitude")
        lon = request.form.get("longitude")

    if lat is None or lon is None:
        if request.is_json:
            return jsonify({"success": False, "error": "Missing latitude or longitude"}), 400
        flash("GPS Coordinates were not received. Please grant location permissions.", "danger")
        return redirect(url_for("dashboard"))

    try:
        lat, lon = sanitize_coordinates(lat, lon)
    except ValueError as e:
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(f"Invalid GPS coordinates: {e}", "danger")
        return redirect(url_for("dashboard"))

    # Strict Karnataka Surveillance Boundary Check
    matched_zone = match_karnataka_zone(lat=lat, lon=lon)
    if not matched_zone:
        place_name = (data.get("place_name") if request.is_json else request.form.get("place_name"))
        if not place_name or not str(place_name).strip():
            place_name = detect_place_name(lat, lon)

        if request.is_json:
            return jsonify({
                "success": False,
                "not_applicable": True,
                "location_name": place_name,
                "redirect_url": url_for("not_applicable_view", location=place_name)
            })
        return render_template("not_applicable.html", queried_location=place_name)

    # Ingest weather for the matched Karnataka zone
    weather = get_karnataka_weather(matched_zone)

    # XGBoost Inference
    ml_result = predict_flood_risk(weather)
    risk_level = ml_result["risk_level"]
    prob = ml_result["probability"]

    # Process alerts if High Risk
    user_email = session.get("user_email")
    alert_info = process_flood_alert({
        "location_name": weather["location_name"],
        "rainfall": weather["rainfall"],
        "humidity": weather["humidity"],
        "pressure": weather["pressure"],
        "risk_level": risk_level,
        "probability": prob
    }, recipient_email=user_email)

    # Persist prediction in database first
    user_id = session.get("user_id")
    is_high_risk = (risk_level == "High Risk")
    pred_id = execute_query(
        """
        INSERT INTO predictions 
        (user_id, location_name, latitude, longitude, rainfall, humidity, temperature, wind_speed, pressure, risk_level, probability, alert_triggered)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user_id,
            weather["location_name"],
            weather["latitude"],
            weather["longitude"],
            weather["rainfall"],
            weather["humidity"],
            weather["temperature"],
            weather["wind_speed"],
            weather["pressure"],
            risk_level,
            prob,
            1 if is_high_risk else 0
        )
    )

    # Process and record alert notification for users
    user_email = session.get("user_email")
    alert_info = process_flood_alert({
        "location_name": weather["location_name"],
        "rainfall": weather["rainfall"],
        "humidity": weather["humidity"],
        "pressure": weather["pressure"],
        "risk_level": risk_level,
        "probability": prob
    }, recipient_email=user_email, user_id=user_id, prediction_id=pred_id)

    if request.is_json:
        return jsonify({
            "success": True,
            "prediction_id": pred_id,
            "location_name": weather["location_name"],
            "alert_status": alert_info["status"],
            "redirect_url": url_for("result_view", prediction_id=pred_id)
        })

    return redirect(url_for("result_view", prediction_id=pred_id))

@app.route("/predict/manual", methods=["POST"])
def predict_manual():
    """
    Handles manual location prediction with strict Karnataka zone check.
    """
    city_name = request.form.get("city_name", "").strip()
    if not city_name:
        flash("Please enter or select a monitored Karnataka region.", "warning")
        return redirect(url_for("custom_location"))

    # Strict Karnataka Surveillance Boundary Check
    matched_zone = match_karnataka_zone(city_name=city_name)
    if not matched_zone:
        return render_template("not_applicable.html", queried_location=city_name)

    # Ingest weather for the matched Karnataka zone
    weather = get_karnataka_weather(matched_zone)

    # XGBoost Inference
    ml_result = predict_flood_risk(weather)
    risk_level = ml_result["risk_level"]
    prob = ml_result["probability"]
    is_high_risk = (risk_level == "High Risk")

    # Persist record in database first
    user_id = session.get("user_id")
    pred_id = execute_query(
        """
        INSERT INTO predictions 
        (user_id, location_name, latitude, longitude, rainfall, humidity, temperature, wind_speed, pressure, risk_level, probability, alert_triggered)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user_id,
            weather["location_name"],
            weather["latitude"],
            weather["longitude"],
            weather["rainfall"],
            weather["humidity"],
            weather["temperature"],
            weather["wind_speed"],
            weather["pressure"],
            risk_level,
            prob,
            1 if is_high_risk else 0
        )
    )

    # Trigger alert pipeline and record notification
    user_email = session.get("user_email")
    alert_info = process_flood_alert({
        "location_name": weather["location_name"],
        "rainfall": weather["rainfall"],
        "humidity": weather["humidity"],
        "pressure": weather["pressure"],
        "risk_level": risk_level,
        "probability": prob
    }, recipient_email=user_email, user_id=user_id, prediction_id=pred_id)

    return redirect(url_for("result_view", prediction_id=pred_id))

@app.route("/result/<int:prediction_id>")
def result_view(prediction_id):
    """
    Displays full assessment result with dynamic risk styling,
    weather metrics grid, Leaflet map canvas, emergency alert status, and recommendations.
    """
    pred = fetch_one("SELECT * FROM predictions WHERE id = %s", (prediction_id,))
    if not pred:
        flash("Requested prediction report was not found.", "warning")
        return redirect(url_for("dashboard"))

    risk_level = pred["risk_level"]
    recommendations = get_recommendations(risk_level)

    # Theme colors for the UI banner & Leaflet circle
    theme_colors = {
        "Low Risk": {"hex": "#10b981", "badge_class": "badge-low", "banner_class": "banner-low", "text_class": "text-risk-low", "border_class": "border-risk-low"},
        "Medium Risk": {"hex": "#f59e0b", "badge_class": "badge-med", "banner_class": "banner-med", "text_class": "text-risk-med", "border_class": "border-risk-med"},
        "High Risk": {"hex": "#ef4444", "badge_class": "badge-high", "banner_class": "banner-high", "text_class": "text-risk-high", "border_class": "border-risk-high"}
    }
    theme = theme_colors.get(risk_level, theme_colors["Low Risk"])

    zone_data = match_karnataka_zone(city_name=pred["location_name"])
    
    # Retrieve the alert broadcast record for this assessment
    alert_record = fetch_one(
        "SELECT * FROM alerts WHERE prediction_id = %s ORDER BY id DESC LIMIT 1",
        (prediction_id,)
    )

    return render_template(
        "result.html",
        pred=pred,
        recommendations=recommendations,
        theme=theme,
        zone_data=zone_data,
        alert_record=alert_record
    )

@app.route("/api/alerts/send", methods=["POST"])
def send_alert_direct():
    """
    Directly dispatches an urgent flood alert email to a specified recipient email address.
    """
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form

    prediction_id = data.get("prediction_id")
    recipient_email = data.get("email", "").strip()

    if not recipient_email or "@" not in recipient_email:
        if request.is_json:
            return jsonify({"success": False, "error": "Please provide a valid recipient email address."}), 400
        flash("Please provide a valid recipient email address.", "danger")
        return redirect(request.referrer or url_for("dashboard"))

    pred = None
    if prediction_id:
        try:
            pred = fetch_one("SELECT * FROM predictions WHERE id = %s", (int(prediction_id),))
        except (ValueError, TypeError):
            pass

    if not pred:
        pred = fetch_one("SELECT * FROM predictions ORDER BY id DESC LIMIT 1")

    if not pred:
        if request.is_json:
            return jsonify({"success": False, "error": "No assessment record found."}), 404
        flash("No assessment record found to dispatch alert.", "warning")
        return redirect(url_for("dashboard"))

    alert_info = process_flood_alert({
        "location_name": pred["location_name"],
        "rainfall": pred["rainfall"],
        "humidity": pred["humidity"],
        "temperature": pred["temperature"],
        "pressure": pred["pressure"],
        "risk_level": pred["risk_level"],
        "probability": pred["probability"]
    }, recipient_email=recipient_email, user_id=session.get("user_id"), prediction_id=pred["id"])

    return jsonify({
        "success": True,
        "message": f"Emergency alert broadcast triggered for {recipient_email}. Status: {alert_info['status']}",
        "email_sent": alert_info["email_sent"],
        "status": alert_info["status"],
        "recipient": recipient_email,
        "sms_text": alert_info.get("sms_text", "")
    })

@app.route("/api/alerts/recent")
def recent_alerts():
    """Returns recent emergency alerts for the notification modal."""
    alerts = fetch_all("SELECT * FROM alerts ORDER BY id DESC LIMIT 15")
    return jsonify({"success": True, "alerts": alerts})

@app.route("/history")
@admin_required
def history():
    """Assessment history log - strictly restricted to Administrators."""
    predictions = fetch_all("SELECT * FROM predictions ORDER BY created_at DESC LIMIT 100")
    return render_template("history.html", predictions=predictions)

# -------------------------------------------------------------
# Admin Analytics & Dashboard Routes
# -------------------------------------------------------------
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    """Admin dashboard overview with metrics, Leaflet points, and recent audit table."""
    total_preds = fetch_one("SELECT COUNT(*) as count FROM predictions")["count"] or 0
    high_risks = fetch_one("SELECT COUNT(*) as count FROM predictions WHERE risk_level = 'High Risk'")["count"] or 0
    total_users = fetch_one("SELECT COUNT(*) as count FROM users")["count"] or 0
    avg_rainfall_row = fetch_one("SELECT AVG(rainfall) as avg_rain FROM predictions")
    avg_rainfall = round(float(avg_rainfall_row["avg_rain"] or 0.0), 1)

    recent_logs = fetch_all("SELECT * FROM predictions ORDER BY created_at DESC LIMIT 50")
    
    # Coordinates for mapping hotspots
    map_points = fetch_all(
        "SELECT id, location_name, latitude, longitude, risk_level, rainfall, probability, created_at FROM predictions ORDER BY id DESC LIMIT 100"
    )

    return render_template(
        "admin_dashboard.html",
        total_preds=total_preds,
        high_risks=high_risks,
        total_users=total_users,
        avg_rainfall=avg_rainfall,
        recent_logs=recent_logs,
        map_points=map_points
    )

@app.route("/api/admin/chart-data")
@admin_required
def admin_chart_data():
    """API endpoint providing dataset analytics for Chart.js."""
    # 1. Risk distribution
    dist_rows = fetch_all("SELECT risk_level, COUNT(*) as count FROM predictions GROUP BY risk_level")
    dist_map = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    for r in dist_rows:
        if r["risk_level"] in dist_map:
            dist_map[r["risk_level"]] = int(r["count"])

    # 2. Daily volume (last 7 days or entries)
    daily_rows = fetch_all(
        """
        SELECT DATE(created_at) as pred_date, COUNT(*) as count, AVG(rainfall) as avg_rain
        FROM predictions 
        GROUP BY DATE(created_at) 
        ORDER BY pred_date DESC 
        LIMIT 7
        """
    )
    daily_labels = [str(r["pred_date"]) for r in reversed(daily_rows)]
    daily_counts = [int(r["count"]) for r in reversed(daily_rows)]
    daily_rain = [round(float(r["avg_rain"] or 0.0), 1) for r in reversed(daily_rows)]

    return jsonify({
        "distribution": {
            "labels": ["Low Risk", "Medium Risk", "High Risk"],
            "data": [dist_map["Low Risk"], dist_map["Medium Risk"], dist_map["High Risk"]],
            "colors": ["#10b981", "#f59e0b", "#ef4444"]
        },
        "trends": {
            "labels": daily_labels if daily_labels else ["Today"],
            "counts": daily_counts if daily_counts else [0],
            "rainfall": daily_rain if daily_rain else [0.0]
        }
    })

# -------------------------------------------------------------
# Run server
# -------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
