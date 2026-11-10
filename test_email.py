
import sys
import os
from config import Config
from services.alerts import send_smtp_alert_email, format_alert_email_html
from datetime import datetime

def test_mail(target_email):
    print("=" * 60)
    print("  HYDROALERT SMTP CONFIGURATION VERIFIER")
    print("=" * 60)
    print(f"MAIL_SERVER:         {Config.MAIL_SERVER}")
    print(f"MAIL_PORT:           {Config.MAIL_PORT}")
    print(f"MAIL_USE_TLS:        {Config.MAIL_USE_TLS}")
    print(f"MAIL_USERNAME:       {Config.MAIL_USERNAME if Config.MAIL_USERNAME else '[NOT SET]'}")
    print(f"MAIL_PASSWORD:       {'*' * len(Config.MAIL_PASSWORD) if Config.MAIL_PASSWORD else '[NOT SET]'}")
    print(f"Target Recipient:    {target_email}")
    print("-" * 60)

    if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        print("\n[FAILED] SMTP Credentials are missing in your .env file!")
        print("Steps to fix:")
        print("  1. Open .env file in E:\\MajorProject\\.env")
        print("  2. Set MAIL_USERNAME=your_gmail_id@gmail.com")
        print("  3. Set MAIL_PASSWORD=your_16_character_app_password")
        print("     (Generate this at: https://myaccount.google.com/apppasswords)")
        print("  4. Save the file and re-run this script: python test_email.py " + target_email)
        print("=" * 60)
        return False

    print("\nAttempting to connect to SMTP server and dispatch test alert...")
    sample_params = {
        "humidity": 88.5,
        "pressure": 1008.2
    }
    html_body = format_alert_email_html(
        location="Kodagu (Madikeri) - Test Diagnostic",
        rainfall=115.4,
        probability=94.2,
        parameters=sample_params,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    subject = "HYDROALERT TEST: Flood Early Warning System Verification"

    success, msg = send_smtp_alert_email(target_email, subject, html_body)
    if success:
        print("\n[SUCCESS] Direct test email sent successfully to " + target_email + "!")
        print("Please check your Gmail inbox or Spam folder.")
    else:
        print(f"\n[FAILED] SMTP Dispatch error: {msg}")
        print("\nCommon Causes:")
        print("  1. Using your personal Gmail password instead of a 16-character App Password.")
        print("  2. 2-Step Verification is not turned ON on your Google account.")
        print("  3. Typing error in the 16-character password (remove spaces if any).")
    print("=" * 60)
    return success

if __name__ == "__main__":
    recipient = sys.argv[1] if len(sys.argv) > 1 else "swathimahesh025@gmail.com"
    test_mail(recipient)
