import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Application configuration loaded from environment variables."""
    # Flask settings
    SECRET_KEY = os.getenv("SECRET_KEY", "urban-flood-super-secret-key-2026")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

    # MySQL database settings
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB = os.getenv("MYSQL_DB", "urban_flood")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_POOL_NAME = "urban_flood_pool"
    MYSQL_POOL_SIZE = int(os.getenv("MYSQL_POOL_SIZE", 5))

    # OpenWeatherMap API settings
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"

    # Email & SMTP Alert Configuration
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "alerts@urbanflood.org")
    ALERT_RECIPIENT_EMAIL = os.getenv("ALERT_RECIPIENT_EMAIL", "")

    # Machine Learning Model & Dataset paths
    MODEL_PATH = os.path.join(BASE_DIR, "models", "flood_model.pkl")
    DATASET_PATH = os.path.join(BASE_DIR, "dataset", "flood.csv")

    # Fallback SQLite DB path (ensures zero-crash testing when MySQL daemon is unconfigured)
    SQLITE_FALLBACK_PATH = os.path.join(BASE_DIR, "database", "urban_flood_fallback.db")
