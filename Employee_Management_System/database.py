"""Small MySQL connection and schema helpers for the application."""

from flask import current_app
import pymysql
from pymysql.cursors import DictCursor


def _settings(include_database=True):
    settings = {
        "host": current_app.config["MYSQL_HOST"],
        "port": current_app.config["MYSQL_PORT"],
        "user": current_app.config["MYSQL_USER"],
        "password": current_app.config["MYSQL_PASSWORD"],
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }
    if include_database:
        settings["database"] = current_app.config["MYSQL_DATABASE"]
    return settings


def get_db():
    """Return a fresh connection. Callers should close it in a finally block."""
    return pymysql.connect(**_settings())


def initialize_database():
    """Create the database and its tables if the MySQL user has permission."""
    database_name = current_app.config["MYSQL_DATABASE"]
    server = pymysql.connect(**_settings(include_database=False))
    try:
        with server.cursor() as cursor:
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS `{}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci".format(
                    database_name.replace("`", "")
                )
            )
        server.commit()
    finally:
        server.close()

    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(120) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    employee_id VARCHAR(20) NOT NULL UNIQUE,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(120) NOT NULL UNIQUE,
                    phone VARCHAR(25) DEFAULT '',
                    department VARCHAR(80) NOT NULL,
                    position VARCHAR(100) NOT NULL,
                    employment_status ENUM('Active', 'On Leave', 'Inactive') NOT NULL DEFAULT 'Active',
                    salary DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
                    joining_date DATE NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_employee_department (department),
                    INDEX idx_employee_status (employment_status),
                    INDEX idx_employee_name (full_name)
                ) ENGINE=InnoDB
                """
            )
        connection.commit()
    finally:
        connection.close()
