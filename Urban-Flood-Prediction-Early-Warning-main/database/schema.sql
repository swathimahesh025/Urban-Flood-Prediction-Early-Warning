-- Urban Flood Prediction and Early Warning System
-- Database Schema Definition

CREATE DATABASE IF NOT EXISTS urban_flood CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE urban_flood;

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table: admin
CREATE TABLE IF NOT EXISTS admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table: predictions
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
    CONSTRAINT fk_prediction_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Initial default admin user (Username: admin, Password: Admin@123)
-- Hash generated via werkzeug.security.generate_password_hash('Admin@123')
INSERT IGNORE INTO admin (id, username, email, password_hash)
VALUES (1, 'admin', 'admin@urbanflood.org', 'scrypt:32768:8:1$u7zQf3xKLaP3mG2$a1c7eb12a4413e1176b5d92dfae48f065a20165c71d60dfb5b8c9f0b182d8c304d9c7590807096e252a1cfcecf87635c91e1d2c676d05bfdbe3099908cf6741b');
