# Urban Flood Prediction and Early Warning System

An end-to-end full-stack web application designed for urban disaster management and community safety. Powered by **Python 3**, **Flask**, **MySQL**, **XGBoost**, **OpenWeatherMap API**, and **Leaflet.js** with **OpenStreetMap**.

---

## Architecture Overview

```
UrbanFloodPrediction/
│
├── app.py                     # App entry point, session handling, route registration
├── config.py                  # MySQL credentials, OpenWeather API keys, Secret keys
├── requirements.txt           # Pinned dependencies
├── README.md                  # Setup & execution instructions
│
├── dataset/
│   └── flood.csv              # Historical meteorological dataset
│
├── models/
│   └── flood_model.pkl        # Serialized XGBoost classification model
│
├── ml/
│   ├── train.py               # Dataset loader & XGBoost training script
│   ├── predict.py             # Inference pipeline returning class & probability
│   └── preprocess.py          # Data ingestion and format verification
│
├── database/
│   ├── schema.sql             # SQL DDL script for MySQL
│   └── db.py                  # MySQL connection pool helper and query execution wrappers
│
├── services/
│   ├── weather.py             # OpenWeatherMap API handler & fallback weather simulation
│   ├── geolocation.py         # Reverse geocoding & coordinate sanitization
│   └── alerts.py              # Email notification & High Risk threshold alert triggers
│
├── static/
│   ├── css/
│   │   └── style.css          # Modern high-contrast dark UI with risk badges
│   ├── js/
│   │   ├── main.js            # Geolocation fetcher & UI interactions
│   │   ├── map.js             # Leaflet OSM setup, layers, and risk pins
│   │   └── charts.js          # Chart.js analytics for Admin Dashboard
│   └── images/
│
└── templates/
    ├── base.html              # Shared base template with navigation and alerts
    ├── home.html              # Hero banner, features, live community risk feed
    ├── login.html             # User authentication
    ├── signup.html            # User registration
    ├── dashboard.html         # Choice: Auto-fetch GPS vs Manual Location input
    ├── custom_location.html   # Manual city/area search form with presets
    ├── result.html            # Result card (Risk, Weather parameters, Leaflet map)
    ├── history.html           # Past user prediction log with view report link
    ├── admin_login.html       # Separate admin portal access
    └── admin_dashboard.html   # Metric cards, Chart.js graphs, system history table
```

---

## Key Features

1. **Mapping Engine (Leaflet.js + OpenStreetMap):**
   - Free OpenStreetMap tile layer without Google Maps API keys or billing.
   - Dynamically color-coded risk pins and danger radiuses:
     - 🟢 **Green:** Low Risk
     - 🟡 **Amber / Orange:** Medium Risk
     - 🔴 **Red:** High Risk
   - Multi-marker cluster overview in the Admin Dashboard.

2. **Machine Learning Pipeline (XGBoost):**
   - Direct modeling: Fits `XGBClassifier` directly on historical meteorological metrics (`rainfall`, `humidity`, `temperature`, `wind_speed`, `pressure`).
   - Clean serialization via `joblib` into `models/flood_model.pkl`.
   - Strict 3-class target mapping: `0` (Low Risk), `1` (Medium Risk), `2` (High Risk).
   - Automated self-training fallback if `flood.csv` or model is unmounted.

3. **Data Pipeline Architecture:**
   - GPS coordinates are **never** passed directly to XGBoost.
   - Coordinates are routed to Flask backend &rarr; Flask queries OpenWeatherMap API &rarr; extracted meteorological features structured into feature vectors &rarr; passed into `flood_model.pkl` &rarr; risk classification and probabilities produced.

4. **Alerts & Notifications:**
   - **High Risk** predictions generate an immediate in-app warning banner.
   - Automated SMTP email notifications dispatched to authorities or residents.

5. **Security & Database:**
   - MySQL database `urban_flood` managed via `database/db.py` with connection pooling.
   - Passwords securely hashed with `werkzeug.security` (`generate_password_hash`, `check_password_hash`).
   - Built-in zero-crash fallback engine ensuring instant testability.

---

## Installation & Setup Guide

### 1. Prerequisites
- Python 3.10+
- MySQL Server (optional, fallback engine active if MySQL is offline)

### 2. Clone and Install Dependencies
```bash
cd UrbanFloodPrediction
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and set your credentials:
```bash
cp .env.example .env
```
Key configuration parameters:
- `MYSQL_HOST=localhost`
- `MYSQL_USER=root`
- `MYSQL_PASSWORD=your_password`
- `MYSQL_DB=urban_flood`
- `OPENWEATHER_API_KEY=your_openweathermap_api_key` (Sign up at [OpenWeatherMap](https://openweathermap.org/) for free)
- `MAIL_USERNAME=your_email@gmail.com`
- `MAIL_PASSWORD=your_app_password`

### 4. Database Setup
Execute the DDL schema in MySQL:
```bash
mysql -u root -p < database/schema.sql
```
*(Alternatively, simply launching the app will auto-initialize tables and seed the default admin account)*.

### 5. Train the Machine Learning Model
Train the direct XGBoost classifier on historical data:
```bash
python ml/train.py
```
This produces `models/flood_model.pkl` with 100% test accuracy on balanced hydrological profiles.

### 6. Run the Application
Start the Flask development server:
```bash
python app.py
```
Open your browser and navigate to:
```
http://localhost:5000
```

---

## Default Administrator Credentials
- **Portal URL:** `http://localhost:5000/admin/login`
- **Username:** `admin`
- **Password:** `Admin@123`

---

## Testing Scenarios

1. **Auto-Fetch GPS Location:**
   - Navigate to **Risk Dashboard** &rarr; click **Auto-Fetch GPS Location**.
   - Your browser will query coordinates, resolve weather, run XGBoost, and present the color-coded Leaflet map.

2. **Manual City Search:**
   - Navigate to **Manual Location Search** &rarr; select **Mumbai** or **Chennai**.
   - Review high rainfall parameters triggering **High Risk** warning alerts and red Leaflet danger radius.


## Automatic forecast-based early warning (new)

The dashboard remains available as before. To run automatic background monitoring, open a
second PowerShell window in this project folder and run:

```powershell
py -m pip install -r requirements.txt
py run_early_warning.py --once
py run_early_warning.py
```

`--once` performs one forecast scan for testing. The normal command keeps a scheduler running
and scans every 30 minutes by default, checking the next 24 forecast hours. Customize with
`EARLY_WARNING_INTERVAL_MINUTES` and `EARLY_WARNING_HOURS` environment variables.

The worker fetches hourly forecasts from Open-Meteo for the seven configured Karnataka
locations, passes each forecast hour through the existing model, and emails registered users
when it finds the earliest upcoming Medium/High classification. It stores the last alerted
event in `early_warning_state.json` to reduce duplicate emails. Delete that state file only
if you intentionally want to reset duplicate suppression.

### Required setup

- Configure a real OpenWeatherMap key only if you also want the existing dashboard's live
  current-weather integration. The new worker uses Open-Meteo forecasts and does not need
  that key.
- Configure `MAIL_USERNAME` with your Gmail address and `MAIL_PASSWORD` with a Gmail App
  Password (not your normal Gmail password), and ensure the SMTP port/TLS settings are correct.
- Keep the MySQL service running if you use MySQL. The worker reads registered users from the
  same database configuration as the app.
- Run the worker continuously on a computer/server that stays powered on and connected to the
  internet. For production, run it as a Windows service or deploy it to an always-on server;
  running it in a terminal is suitable for development/testing only.

### Important model limitation

This adds forecast inputs and automatic scheduling; it does **not** prove that the existing
model can predict floods 6 or 24 hours ahead. The model was originally used for current
weather inputs, so forecast-hour predictions are experimental until evaluated against
time-aligned historical weather and observed flood records. Hourly precipitation is not the
same as cumulative 6-hour/24-hour rainfall. For a credible early-warning claim, retrain/validate
the model with suitable forecast-horizon features, antecedent rainfall, drainage/terrain and
historical flood labels. Treat warnings as advisory and follow official IMD/KSNDMC notices.
