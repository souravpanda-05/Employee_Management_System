import csv
import io
import os
import re
from datetime import date, datetime
from decimal import Decimal
from functools import wraps

import pymysql
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db, initialize_database

load_dotenv()

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EMPLOYEE_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{3,20}$")
PHONE_PATTERN = re.compile(r"^[0-9+() .-]{7,25}$")
STATUSES = {"Active", "On Leave", "Inactive"}


def api_error(message, status=400, errors=None):
    payload = {"success": False, "message": message}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), status


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return api_error("Your session has expired. Please sign in again.", 401)
        return view(*args, **kwargs)

    return wrapped


def page_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def serialise(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def serialise_row(row):
    return {key: serialise(value) for key, value in row.items()}


def validate_employee(data):
    """Return cleaned fields and a per-field validation-error dictionary."""
    fields = {
        "employee_id": str(data.get("employee_id", "")).strip().upper(),
        "full_name": str(data.get("full_name", "")).strip(),
        "email": str(data.get("email", "")).strip().lower(),
        "phone": str(data.get("phone", "")).strip(),
        "department": str(data.get("department", "")).strip(),
        "position": str(data.get("position", "")).strip(),
        "employment_status": str(data.get("employment_status", "Active")).strip(),
        "salary": str(data.get("salary", "")).strip(),
        "joining_date": str(data.get("joining_date", "")).strip(),
    }
    errors = {}
    if not EMPLOYEE_ID_PATTERN.fullmatch(fields["employee_id"]):
        errors["employee_id"] = "Use 3–20 letters, numbers, or hyphens."
    if not 2 <= len(fields["full_name"]) <= 100:
        errors["full_name"] = "Name must be between 2 and 100 characters."
    if not EMAIL_PATTERN.fullmatch(fields["email"]):
        errors["email"] = "Enter a valid email address."
    if fields["phone"] and not PHONE_PATTERN.fullmatch(fields["phone"]):
        errors["phone"] = "Enter a valid phone number."
    if not 2 <= len(fields["department"]) <= 80:
        errors["department"] = "Department is required."
    if not 2 <= len(fields["position"]) <= 100:
        errors["position"] = "Position is required."
    if fields["employment_status"] not in STATUSES:
        errors["employment_status"] = "Choose a valid employment status."
    try:
        salary = float(fields["salary"])
        if salary < 0 or salary > 9999999999.99:
            raise ValueError
        fields["salary"] = salary
    except (TypeError, ValueError):
        errors["salary"] = "Salary must be a positive number."
    try:
        fields["joining_date"] = date.fromisoformat(fields["joining_date"])
    except ValueError:
        errors["joining_date"] = "Choose a valid joining date."
    return fields, errors


def employee_query(filters):
    """Build a safe employee listing query and its bound parameters."""
    clauses, parameters = [], []
    search = filters.get("search", "").strip()
    department = filters.get("department", "").strip()
    status = filters.get("status", "").strip()
    if search:
        clauses.append("(employee_id LIKE %s OR full_name LIKE %s OR email LIKE %s OR position LIKE %s)")
        parameters.extend([f"%{search}%"] * 4)
    if department:
        clauses.append("department = %s")
        parameters.append(department)
    if status in STATUSES:
        clauses.append("employment_status = %s")
        parameters.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return f"SELECT * FROM employees{where} ORDER BY created_at DESC, id DESC", parameters


def fetch_employees(filters):
    connection = get_db()
    try:
        query, parameters = employee_query(filters)
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            return [serialise_row(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "change-this-secret-key-before-production"),
        MYSQL_HOST=os.getenv("MYSQL_HOST", "localhost"),
        MYSQL_PORT=int(os.getenv("MYSQL_PORT", "3306")),
        MYSQL_USER=os.getenv("MYSQL_USER", "root"),
        MYSQL_PASSWORD=os.getenv("MYSQL_PASSWORD", ""),
        MYSQL_DATABASE=os.getenv("MYSQL_DATABASE", "employee_management"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    @app.get("/")
    def index():
        return redirect(url_for("dashboard" if "user_id" in session else "login"))

    @app.get("/login")
    def login():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.get("/dashboard")
    @page_login_required
    def dashboard():
        return render_template("dashboard.html", user_name=session.get("user_name", "Manager"))

    @app.get("/employees")
    @page_login_required
    def employees():
        return render_template("employees.html", user_name=session.get("user_name", "Manager"))

    @app.post("/api/auth/signup")
    def signup():
        data = request.get_json(silent=True) or {}
        full_name = str(data.get("full_name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        errors = {}
        if not 2 <= len(full_name) <= 100:
            errors["full_name"] = "Name must be between 2 and 100 characters."
        if not EMAIL_PATTERN.fullmatch(email):
            errors["email"] = "Enter a valid email address."
        if len(password) < 8:
            errors["password"] = "Password must contain at least 8 characters."
        if errors:
            return api_error("Please correct the highlighted fields.", 422, errors)
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)",
                    (full_name, email, generate_password_hash(password)),
                )
                user_id = cursor.lastrowid
            connection.commit()
        except pymysql.err.IntegrityError:
            connection.rollback()
            return api_error("An account with this email already exists.", 409, {"email": "Email is already registered."})
        finally:
            connection.close()
        session.clear()
        session.update(user_id=user_id, user_name=full_name)
        return jsonify({"success": True, "message": "Account created successfully.", "user": {"name": full_name, "email": email}}), 201

    @app.post("/api/auth/login")
    def login_api():
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if not email or not password:
            return api_error("Email and password are required.", 422)
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, full_name, email, password_hash FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
        finally:
            connection.close()
        if not user or not check_password_hash(user["password_hash"], password):
            return api_error("Incorrect email or password.", 401)
        session.clear()
        session.update(user_id=user["id"], user_name=user["full_name"])
        return jsonify({"success": True, "message": "Welcome back!", "user": {"name": user["full_name"], "email": user["email"]}})

    @app.post("/api/auth/logout")
    @api_login_required
    def logout():
        session.clear()
        return jsonify({"success": True, "message": "You have been signed out."})

    @app.get("/api/auth/me")
    @api_login_required
    def current_user():
        return jsonify({"success": True, "user": {"id": session["user_id"], "name": session.get("user_name")}})

    @app.get("/api/dashboard/stats")
    @api_login_required
    def dashboard_stats():
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT COUNT(*) AS total, SUM(employment_status = 'Active') AS active,
                       SUM(employment_status = 'On Leave') AS on_leave,
                       SUM(employment_status = 'Inactive') AS inactive,
                       COUNT(DISTINCT department) AS departments FROM employees"""
                )
                stats = cursor.fetchone()
                cursor.execute(
                    "SELECT department, COUNT(*) AS count FROM employees GROUP BY department ORDER BY count DESC, department ASC LIMIT 6"
                )
                departments = cursor.fetchall()
                cursor.execute("SELECT * FROM employees ORDER BY created_at DESC, id DESC LIMIT 5")
                recent = [serialise_row(row) for row in cursor.fetchall()]
        finally:
            connection.close()
        return jsonify({
            "success": True,
            "stats": {key: int(value or 0) for key, value in stats.items()},
            "departments": [serialise_row(row) for row in departments],
            "recent": recent,
        })

    @app.get("/api/employees")
    @api_login_required
    def list_employees():
        employees_list = fetch_employees(request.args)
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT DISTINCT department FROM employees ORDER BY department")
                departments = [row["department"] for row in cursor.fetchall()]
        finally:
            connection.close()
        return jsonify({"success": True, "employees": employees_list, "departments": departments, "count": len(employees_list)})

    @app.get("/api/employees/<int:employee_db_id>")
    @api_login_required
    def get_employee(employee_db_id):
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM employees WHERE id = %s", (employee_db_id,))
                employee = cursor.fetchone()
        finally:
            connection.close()
        if not employee:
            return api_error("Employee not found.", 404)
        return jsonify({"success": True, "employee": serialise_row(employee)})

    @app.post("/api/employees")
    @api_login_required
    def add_employee():
        fields, errors = validate_employee(request.get_json(silent=True) or {})
        if errors:
            return api_error("Please correct the highlighted fields.", 422, errors)
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO employees
                    (employee_id, full_name, email, phone, department, position, employment_status, salary, joining_date)
                    VALUES (%(employee_id)s, %(full_name)s, %(email)s, %(phone)s, %(department)s, %(position)s,
                    %(employment_status)s, %(salary)s, %(joining_date)s)""",
                    fields,
                )
                new_id = cursor.lastrowid
            connection.commit()
        except pymysql.err.IntegrityError as error:
            connection.rollback()
            duplicate = "employee_id" if "employee_id" in str(error).lower() else "email"
            return api_error("Employee ID or email is already in use.", 409, {duplicate: "This value is already in use."})
        finally:
            connection.close()
        return jsonify({"success": True, "message": "Employee added successfully.", "id": new_id}), 201

    @app.put("/api/employees/<int:employee_db_id>")
    @api_login_required
    def update_employee(employee_db_id):
        fields, errors = validate_employee(request.get_json(silent=True) or {})
        if errors:
            return api_error("Please correct the highlighted fields.", 422, errors)
        fields["id"] = employee_db_id
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE employees SET employee_id=%(employee_id)s, full_name=%(full_name)s, email=%(email)s,
                    phone=%(phone)s, department=%(department)s, position=%(position)s,
                    employment_status=%(employment_status)s, salary=%(salary)s, joining_date=%(joining_date)s
                    WHERE id=%(id)s""",
                    fields,
                )
                updated = cursor.rowcount
            connection.commit()
        except pymysql.err.IntegrityError as error:
            connection.rollback()
            duplicate = "employee_id" if "employee_id" in str(error).lower() else "email"
            return api_error("Employee ID or email is already in use.", 409, {duplicate: "This value is already in use."})
        finally:
            connection.close()
        if not updated:
            return api_error("Employee not found.", 404)
        return jsonify({"success": True, "message": "Employee updated successfully."})

    @app.delete("/api/employees/<int:employee_db_id>")
    @api_login_required
    def delete_employee(employee_db_id):
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM employees WHERE id = %s", (employee_db_id,))
                deleted = cursor.rowcount
            connection.commit()
        finally:
            connection.close()
        if not deleted:
            return api_error("Employee not found.", 404)
        return jsonify({"success": True, "message": "Employee deleted successfully."})

    @app.get("/api/employees/export.csv")
    @api_login_required
    def export_employees():
        employees_list = fetch_employees(request.args)
        output = io.StringIO()
        headings = ["Employee ID", "Full Name", "Email", "Phone", "Department", "Position", "Status", "Salary", "Joining Date"]
        writer = csv.writer(output)
        writer.writerow(headings)
        for employee in employees_list:
            writer.writerow([
                employee["employee_id"], employee["full_name"], employee["email"], employee["phone"],
                employee["department"], employee["position"], employee["employment_status"],
                f'{employee["salary"]:.2f}', employee["joining_date"],
            ])
        filename = f"employees-{date.today().isoformat()}.csv"
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})

    @app.errorhandler(pymysql.MySQLError)
    def database_error(error):
        app.logger.exception("Database error: %s", error)
        if request.path.startswith("/api/"):
            return api_error("Could not reach MySQL. Check your database settings and try again.", 503)
        return "Database connection unavailable. Please check your MySQL configuration.", 503

    return app


app = create_app()

if __name__ == "__main__":
    try:
        with app.app_context():
            initialize_database()
        print("Database is ready.")
    except pymysql.MySQLError as error:
        print(f"Database setup warning: {error}")
        print("Start MySQL and check your .env settings, then reload the app.")
    app.run(debug=True)
