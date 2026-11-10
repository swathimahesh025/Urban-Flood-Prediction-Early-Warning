import logging
import sqlite3
import socket
import mysql.connector
from mysql.connector import pooling
from werkzeug.security import generate_password_hash
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module-level connection pool & backend tracker
_pool = None
_use_sqlite_fallback = False

def get_db_pool():
    """Initializes or returns existing MySQL Connection Pool."""
    global _pool, _use_sqlite_fallback
    if _use_sqlite_fallback:
        return None

    if _pool is None:
        try:
            # Fast socket check to ensure MySQL port is accepting connections
            with socket.create_connection((Config.MYSQL_HOST, Config.MYSQL_PORT), timeout=0.8):
                pass

            # Try connecting to ensure database exists
            temp_conn = mysql.connector.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                port=Config.MYSQL_PORT,
                connection_timeout=2
            )
            cursor = temp_conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.close()
            temp_conn.close()

            # Create connection pool
            _pool = pooling.MySQLConnectionPool(
                pool_name=Config.MYSQL_POOL_NAME,
                pool_size=Config.MYSQL_POOL_SIZE,
                pool_reset_session=True,
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                port=Config.MYSQL_PORT
            )
            logger.info("Successfully initialized MySQL Connection Pool.")
        except Exception as e:
            logger.warning(f"Could not connect to MySQL ({e}). Activating SQLite fallback at {Config.SQLITE_FALLBACK_PATH}")
            _use_sqlite_fallback = True
            _pool = None
    return _pool

def get_connection():
    """Returns a connection from the pool or opens an SQLite connection."""
    global _use_sqlite_fallback
    if not _use_sqlite_fallback:
        try:
            pool = get_db_pool()
            if pool:
                return pool.get_connection()
        except Exception as e:
            logger.warning(f"Failed to acquire connection from MySQL pool: {e}. Switching to SQLite fallback.")
            _use_sqlite_fallback = True

    # SQLite fallback connection
    conn = sqlite3.connect(Config.SQLITE_FALLBACK_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=None, commit=True):
    """
    Executes an INSERT, UPDATE, or DELETE query with automatic cursor and connection cleanup.
    Returns the lastrowid or rowcount.
    """
    conn = get_connection()
    cursor = None
    try:
        is_sqlite = isinstance(conn, sqlite3.Connection)
        if is_sqlite:
            # SQLite uses '?' placeholder instead of '%s'
            query = query.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            if commit:
                conn.commit()
            return cursor.lastrowid
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            if commit:
                conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error executing query: {e} | Query: {query} | Params: {params}")
        if conn and commit:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def fetch_one(query, params=None):
    """
    Executes a SELECT query and returns a single dictionary/row or None.
    """
    conn = get_connection()
    cursor = None
    try:
        is_sqlite = isinstance(conn, sqlite3.Connection)
        if is_sqlite:
            query = query.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            row = cursor.fetchone()
            return dict(row) if row else None
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error fetching one: {e} | Query: {query}")
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def fetch_all(query, params=None):
    """
    Executes a SELECT query and returns a list of dictionaries.
    """
    conn = get_connection()
    cursor = None
    try:
        is_sqlite = isinstance(conn, sqlite3.Connection)
        if is_sqlite:
            query = query.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching all: {e} | Query: {query}")
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def init_db():
    """
    Initializes required tables (users, admin, predictions) and seeds the initial admin account.
    """
    conn = get_connection()
    is_sqlite = isinstance(conn, sqlite3.Connection)
    cursor = conn.cursor()

    try:
        if is_sqlite:
            # SQLite Table definitions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                location_name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                rainfall REAL NOT NULL,
                humidity REAL NOT NULL,
                temperature REAL NOT NULL,
                wind_speed REAL NOT NULL,
                pressure REAL NOT NULL,
                risk_level TEXT NOT NULL,
                probability REAL NOT NULL,
                alert_triggered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                prediction_id INTEGER NULL,
                recipient_email TEXT NOT NULL,
                location_name TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                rainfall REAL NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE
            );
            """)
            conn.commit()

            # Seed default admin if missing
            cursor.execute("SELECT id FROM admin WHERE username = ?", ("admin",))
            if not cursor.fetchone():
                admin_pw_hash = generate_password_hash("Admin@123")
                cursor.execute(
                    "INSERT INTO admin (username, email, password_hash) VALUES (?, ?, ?)",
                    ("admin", "admin@urbanflood.org", admin_pw_hash)
                )
                conn.commit()
                logger.info("Default admin user created in SQLite: admin / Admin@123")
        else:
            # MySQL Table definitions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(120) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) NOT NULL UNIQUE,
                email VARCHAR(120) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                location_name VARCHAR(255) NOT NULL,
                latitude DECIMAL(10, 7) NOT NULL,
                longitude DECIMAL(10, 7) NOT NULL,
                rainfall FLOAT NOT NULL,
                humidity FLOAT NOT NULL,
                temperature FLOAT NOT NULL,
                wind_speed FLOAT NOT NULL,
                pressure FLOAT NOT NULL,
                risk_level VARCHAR(50) NOT NULL,
                probability FLOAT NOT NULL,
                alert_triggered BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_pred_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                prediction_id INT NULL,
                recipient_email VARCHAR(120) NOT NULL,
                location_name VARCHAR(100) NOT NULL,
                risk_level VARCHAR(50) NOT NULL,
                rainfall FLOAT NOT NULL,
                status VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_alert_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                CONSTRAINT fk_alert_pred FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            conn.commit()

            # Seed default admin if missing
            cursor.execute("SELECT id FROM admin WHERE username = %s", ("admin",))
            if not cursor.fetchone():
                admin_pw_hash = generate_password_hash("Admin@123")
                cursor.execute(
                    "INSERT INTO admin (username, email, password_hash) VALUES (%s, %s, %s)",
                    ("admin", "admin@urbanflood.org", admin_pw_hash)
                )
                conn.commit()
                logger.info("Default admin user created in MySQL: admin / Admin@123")
    except Exception as e:
        logger.error(f"Error during init_db: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()
