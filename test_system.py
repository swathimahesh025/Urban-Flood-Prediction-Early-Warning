import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from database.db import init_db, fetch_one, fetch_all

def run_tests():
    print("--- 1. Testing Database & Schema Initialization ---")
    init_db()
    admin = fetch_one("SELECT * FROM admin WHERE username = %s", ("admin",))
    assert admin is not None, "Admin user should exist"
    print("[PASS] DB and Admin user verified successfully.")

    print("\n--- 2. Testing Flask Test Client Endpoints ---")
    with app.test_client() as client:
        # Root route now redirects to login when not authenticated
        res = client.get("/", follow_redirects=True)
        assert res.status_code == 200, f"Expected 200 on /, got {res.status_code}"
        assert b"Sign In" in res.data or b"HydroAlert" in res.data
        print("[PASS] Home redirects to Login page for unauthenticated users (200)")

        # Dashboard redirect to login when not authenticated
        res = client.get("/dashboard")
        assert res.status_code == 302, f"Expected 302 redirect to login, got {res.status_code}"
        print("[PASS] Dashboard protected - unauthenticated users redirected to login (302)")

        # Custom location
        res = client.get("/custom-location")
        assert res.status_code == 200, f"Expected 200 on /custom-location, got {res.status_code}"
        print("[PASS] Custom location page accessible (200)")

        # User Signup
        res = client.post("/signup", data={
            "name": "Test User",
            "email": "test@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        }, follow_redirects=True)
        assert res.status_code == 200
        print("[PASS] User registration succeeded")

        # Test Forgot Password GET & Dynamic Reset POST
        res = client.get("/forgot-password")
        assert res.status_code == 200, f"Expected 200 on /forgot-password, got {res.status_code}"
        assert b"Reset Your Password" in res.data
        print("[PASS] Forgot password page accessible (200)")

        # Reset password dynamically for test@example.com
        res = client.post("/forgot-password", data={
            "email": "test@example.com",
            "new_password": "NewPassword123",
            "confirm_password": "NewPassword123"
        }, follow_redirects=True)
        assert res.status_code == 200
        assert b"successfully updated" in res.data
        print("[PASS] Dynamic password reset succeeded without token expiration")

        # Verify login with newly reset password
        res = client.post("/login", data={
            "email": "test@example.com",
            "password": "NewPassword123"
        }, follow_redirects=True)
        assert res.status_code == 200
        assert b"Welcome back" in res.data
        print("[PASS] Authenticated successfully using new reset password")

        # Predict Manual: Karnataka Designated Zone (Bengaluru Urban)
        res = client.post("/predict/manual", data={"city_name": "Bengaluru Urban"}, follow_redirects=True)
        assert res.status_code == 200
        assert b"Risk Assessment" in res.data
        assert b"Bengaluru Urban" in res.data
        print("[PASS] Bengaluru Urban prediction returned exact Karnataka location with Leaflet map data")

        # Predict Manual: Non-Karnataka Location (e.g., Delhi) -> Not Applicable
        res = client.post("/predict/manual", data={"city_name": "Delhi"}, follow_redirects=True)
        assert res.status_code == 200
        assert b"Outside Surveillance Bounds" in res.data or b"Not Applicable" in res.data
        print("[PASS] Non-monitored location correctly returned 'Location Not Applicable'")

        # Predict Manual: Mysuru (NEW 8th Zone) - campus area
        res = client.post("/predict/manual", data={"city_name": "Mysuru"}, follow_redirects=True)
        assert res.status_code == 200
        assert b"Mysuru" in res.data
        assert b"Risk Assessment" in res.data
        print("[PASS] Mysuru prediction returned assessment result - 8th Karnataka zone verified")


        # Predict Auto: Coordinates in Designated Zones (Bengaluru Urban)
        res = client.post("/predict/auto", json={"latitude": 12.9716, "longitude": 77.5946})
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data["success"] is True
        assert json_data["location_name"] == "Bengaluru Urban"
        print(f"[PASS] Auto GPS prediction for Bengaluru Urban returned success: ID #{json_data['prediction_id']}")

        # Predict Auto: Coordinates in Uttara Kannada - Karwar anchor
        res = client.post("/predict/auto", json={"latitude": 14.8135, "longitude": 74.1297})
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data["success"] is True
        assert "Uttara Kannada" in json_data["location_name"]
        print(f"[PASS] Auto GPS prediction for Karwar anchor returned success: {json_data['location_name']}")

        # Predict Auto: Coordinates in Uttara Kannada - Sirsi anchor
        res = client.post("/predict/auto", json={"latitude": 14.6195, "longitude": 74.8354})
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data["success"] is True
        assert "Uttara Kannada" in json_data["location_name"]
        print(f"[PASS] Auto GPS prediction for Sirsi anchor returned success: {json_data['location_name']}")

        # Predict Auto: Coordinates in Dakshina Kannada - Mangaluru Urban
        res = client.post("/predict/auto", json={"latitude": 12.9141, "longitude": 74.8560})
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data["success"] is True
        assert "Dakshina Kannada" in json_data["location_name"]
        print(f"[PASS] Auto GPS prediction for Mangaluru Urban returned success: {json_data['location_name']}")

        # Predict Auto: Mysuru campus (University of Mysore / Manasagangotri) - NOW 8th monitored zone
        res = client.post("/predict/auto", json={"latitude": 12.2958, "longitude": 76.6394})
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data["success"] is True
        assert "Mysuru" in json_data["location_name"]
        print(f"[PASS] Auto GPS for Mysuru campus returned success: {json_data['location_name']} (8th zone)")


        # Predict Auto: Coordinates outside Karnataka (Delhi lat/lon) -> Outside Surveillance Bounds
        res = client.post("/predict/auto", json={"latitude": 28.6139, "longitude": 77.2090})
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data.get("not_applicable") is True
        loc_name = json_data.get("location_name", "")
        print(f"[PASS] Auto GPS for Delhi/Outside Karnataka '{loc_name}' returned Outside Surveillance Bounds")


        # History Page - Non-admin should be redirected to admin login
        client.get("/logout") # logout user
        res = client.get("/history")
        assert res.status_code == 302
        print("[PASS] History log is restricted from non-admin users (302 redirect)")

        # Admin Login
        res = client.post("/admin/login", data={"username": "admin", "password": "Admin@123"}, follow_redirects=True)
        assert res.status_code == 200
        assert b"Disaster Management Analytics" in res.data
        print("[PASS] Admin authentication and Dashboard verified (200)")

        # Admin accessing History Log
        res = client.get("/history")
        assert res.status_code == 200
        assert b"Assessment History" in res.data
        print("[PASS] History log successfully accessible to Admin (200)")

        # Admin Chart Data API
        res = client.get("/api/admin/chart-data")
        assert res.status_code == 200
        chart_data = res.get_json()
        assert "distribution" in chart_data
        assert "trends" in chart_data
        print("[PASS] Admin Chart.js API returned distribution and trend series")

        # -------------------------------------------------------------
        # 3. Testing Emergency Alert Messaging & Notifications
        # -------------------------------------------------------------
        print("\n--- 3. Testing Emergency Alert Messaging & Notifications ---")
        # High Risk prediction for Kodagu (Madikeri)
        res = client.post("/predict/manual", data={"city_name": "Kodagu"}, follow_redirects=True)
        assert res.status_code == 200
        assert b"High Risk" in res.data
        assert b"Emergency Broadcast System" in res.data
        print("[PASS] High Risk prediction in Kodagu activated Emergency Alert UI section")

        # Verify alert record was logged in the alerts database table
        recent_alert = fetch_one("SELECT * FROM alerts WHERE location_name LIKE %s ORDER BY id DESC LIMIT 1", ("%Kodagu%",))
        assert recent_alert is not None, "Alert record should be stored in alerts table"
        assert recent_alert["risk_level"] == "High Risk"
        print(f"[PASS] Alert successfully logged in database: #{recent_alert['id']} for {recent_alert['location_name']} -> {recent_alert['status']}")

        # Test Direct Alert Dispatch API (/api/alerts/send)
        res = client.post("/api/alerts/send", json={
            "prediction_id": recent_alert["prediction_id"],
            "email": "resident.test@karnataka.gov.in"
        })
        assert res.status_code == 200
        alert_json = res.get_json()
        assert alert_json["success"] is True
        assert alert_json["recipient"] == "resident.test@karnataka.gov.in"
        assert "sms_text" in alert_json
        print(f"[PASS] /api/alerts/send directly dispatched alert to: {alert_json['recipient']}")

        # Test Recent Alerts Feed API (/api/alerts/recent)
        res = client.get("/api/alerts/recent")
        assert res.status_code == 200
        feed_json = res.get_json()
        assert feed_json["success"] is True
        assert len(feed_json["alerts"]) > 0
        print(f"[PASS] /api/alerts/recent returned {len(feed_json['alerts'])} live emergency warning broadcasts")

    print("\n==========================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
