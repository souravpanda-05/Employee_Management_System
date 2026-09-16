# PeopleFlow — Employee Management System

A portfolio-ready employee management application built with **Python, Flask, MySQL, HTML, CSS, and vanilla JavaScript**. It has a responsive interface, secure account authentication, an employee REST API, live dashboard statistics, search/filtering, and CSV export.

## Features

- Account signup, login, logout, and password hashing
- Add, edit, and delete employee records
- Employee search plus department and status filters
- Responsive dashboard with live workforce statistics and department breakdown
- CSV export that respects the current filters
- Field-level validation, duplicate handling, protected API routes, and friendly error states
- Automatic MySQL database/table creation when the app starts

## Project structure

```text
Employee_Management_System/
├── app.py                    # Flask routes and REST API
├── database.py               # MySQL setup and connection helpers
├── requirements.txt
├── .env.example
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   └── employees.html
└── static/
    ├── style.css
    └── script.js
```

## Quick start

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure MySQL

Start your MySQL server, then copy `.env.example` to `.env` and update the credentials:

```powershell
Copy-Item .env.example .env
```

The MySQL user must have permission to create the configured database (by default, `employee_management`). If it does not, create the database yourself and grant it access.

### 4. Run the app

```powershell
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000), create the first account, and start adding employees.

## API overview

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/signup` | Create an account |
| `POST` | `/api/auth/login` | Sign in |
| `POST` | `/api/auth/logout` | Sign out |
| `GET` | `/api/dashboard/stats` | Dashboard data |
| `GET` / `POST` | `/api/employees` | List / add employees |
| `GET` / `PUT` / `DELETE` | `/api/employees/<id>` | Read / update / remove an employee |
| `GET` | `/api/employees/export.csv` | Export filtered records |

`GET /api/employees` accepts optional `search`, `department`, and `status` query parameters.

## Interview talking points

- Flask sessions protect all management and reporting endpoints; passwords are never stored as plain text.
- SQL parameter binding is used for all employee input to prevent SQL injection.
- The frontend is intentionally dependency-free: the responsive UI and REST integration are written in semantic HTML, CSS, and modern browser JavaScript.
- The data model indexes common filtering fields (`department`, `employment_status`, and employee name) for faster directory queries.

## Production note

Before deployment, use a strong `SECRET_KEY`, set `debug=False`, use a restricted MySQL application user, enable HTTPS, and run Flask behind a production WSGI server such as Waitress or Gunicorn.
