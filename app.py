# ============================================================
# app.py — StudyFlow API Backend
# Deploy this on: Render.com
# Frontend runs on: Netlify (static HTML/CSS/JS)
# ============================================================
# HOW TO RUN LOCALLY:
#   pip install flask flask-cors
#   python app.py
#   API runs at: http://127.0.0.1:5000
#
# HOW TO DEPLOY ON RENDER:
#   1. Push this file + requirements.txt to GitHub
#   2. Create new Web Service on Render
#   3. Build command:  pip install -r requirements.txt
#   4. Start command:  python app.py
#   5. Add Environment Variables on Render:
#      NETLIFY_URL = https://your-site.netlify.app
#      SECRET_KEY  = any-random-string
# ============================================================

from flask import Flask, request, redirect, jsonify, session
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# Set NETLIFY_URL in Render environment variables
# ============================================================
NETLIFY_URL = os.environ.get("NETLIFY_URL", "https://your-site.netlify.app")
app.secret_key = os.environ.get("SECRET_KEY", "studyflow_secret_2024")

# ============================================================
# CORS — Allows your Netlify frontend to talk to this backend
# Without CORS, browser will block all requests!
# ============================================================
CORS(app,
     supports_credentials=True,
     origins=[
         NETLIFY_URL,
         "http://127.0.0.1:5500",    # VS Code Live Server
         "http://localhost:5500",
         "http://127.0.0.1:3000",
         "http://localhost:3000",
     ])

DATABASE = "studyflow.db"


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_db():
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row   # lets us use column names like dict
    return conn


def init_db():
    """Create all tables when the server starts."""
    conn = get_db()
    cur  = conn.cursor()

    # --- Users table ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            email      TEXT    NOT NULL UNIQUE,
            password   TEXT    NOT NULL,
            created_at TEXT    DEFAULT (datetime('now'))
        )
    """)

    # --- Students table ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name   TEXT    NOT NULL,
            email  TEXT    NOT NULL,
            course TEXT    NOT NULL,
            marks  INTEGER NOT NULL
        )
    """)

    # --- Tasks table ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            description TEXT,
            status      TEXT    DEFAULT 'Pending',
            user_id     INTEGER,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print("Database is ready!")


# ============================================================
# HELPER FUNCTION
# Redirects user back to a Netlify page with a message.
# The message is passed in the URL as ?msg=...&type=success/error
# Your HTML page reads this with JavaScript and shows the message.
# ============================================================
def redirect_to(page, msg="", msg_type="success"):
    url = f"{NETLIFY_URL}/{page}.html"
    if msg:
        safe_msg = msg.replace(" ", "+")
        url += f"?msg={safe_msg}&type={msg_type}"
    return redirect(url, code=302)


# ============================================================
# ROUTE 1: Health Check
# Visit your Render URL in browser to confirm API is live
# Example: https://studyflow-api.onrender.com/
# ============================================================
@app.route("/")
def home():
    return jsonify({
        "status":  "StudyFlow API is running!",
        "frontend": NETLIFY_URL,
        "routes": {
            "POST /register":           "Register new user",
            "POST /login":              "Login user",
            "GET  /logout":             "Logout user",
            "GET  /dashboard":          "Get dashboard stats",
            "GET  /students":           "Get all students (JSON)",
            "POST /add_student":        "Add new student",
            "POST /edit_student/<id>":  "Edit student",
            "GET  /delete_student/<id>":"Delete student",
            "GET  /tasks":              "Get all tasks (JSON)",
            "POST /add_task":           "Add new task",
            "POST /edit_task/<id>":     "Edit task",
            "GET  /delete_task/<id>":   "Delete task",
            "POST /calculator":         "Do arithmetic (returns JSON)",
        }
    })


# ============================================================
# ROUTE 2: REGISTER
# HTML form on Netlify sends POST to this route
#
# Your register.html form should look like:
#   <form method="POST" action="https://your-api.onrender.com/register">
#     <input name="name" />
#     <input name="email" />
#     <input name="password" />
#     <input name="confirm_password" />
#   </form>
# ============================================================
@app.route("/register", methods=["POST"])
def register():
    name     = request.form.get("name",             "").strip()
    email    = request.form.get("email",            "").strip()
    password = request.form.get("password",         "").strip()
    confirm  = request.form.get("confirm_password", "").strip()

    # Validate inputs
    if not name or not email or not password:
        return redirect_to("register", "All fields are required!", "error")

    if password != confirm:
        return redirect_to("register", "Passwords do not match!", "error")

    if len(password) < 6:
        return redirect_to("register", "Password must be at least 6 characters!", "error")

    # Save to database
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password)
        )
        conn.commit()
        conn.close()
        # Success — go to login page
        return redirect_to("login", "Registration successful! Please login.", "success")

    except sqlite3.IntegrityError:
        # Email already exists
        return redirect_to("register", "Email already registered! Try logging in.", "error")


# ============================================================
# ROUTE 3: LOGIN
# On success  → redirects to dashboard.html?user=Name&id=1
# On failure  → redirects back to login.html with error msg
#
# Your login.html form:
#   <form method="POST" action="https://your-api.onrender.com/login">
#     <input name="email" />
#     <input name="password" />
#   </form>
# ============================================================
@app.route("/login", methods=["POST"])
def login():
    email    = request.form.get("email",    "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return redirect_to("login", "Email and password are required!", "error")

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (email, password)
    ).fetchone()
    conn.close()

    if user:
        # Store in session
        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]

        # Redirect to Netlify dashboard page with user info in URL
        # JavaScript on dashboard.html reads these values
        name_safe = user["name"].replace(" ", "+")
        url = f"{NETLIFY_URL}/dashboard.html?user={name_safe}&id={user['id']}"
        return redirect(url, code=302)
    else:
        return redirect_to("login", "Invalid email or password!", "error")


# ============================================================
# ROUTE 4: LOGOUT
# ============================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect_to("login", "Logged out successfully.", "success")


# ============================================================
# ROUTE 5: DASHBOARD STATS (JSON API)
# Your dashboard.html uses fetch() to call this
#
# JavaScript example in dashboard.html:
#   const params = new URLSearchParams(window.location.search);
#   const userId = params.get('id');
#   fetch(`https://your-api.onrender.com/dashboard?user_id=${userId}`)
#     .then(r => r.json())
#     .then(data => {
#       document.getElementById('studentCount').textContent = data.students;
#       document.getElementById('taskCount').textContent    = data.tasks;
#     });
# ============================================================
@app.route("/dashboard", methods=["GET"])
def dashboard():
    user_id = request.args.get("user_id")

    conn = get_db()
    student_count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    user_count    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    task_count    = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,)
    ).fetchone()[0] if user_id else 0
    conn.close()

    return jsonify({
        "students": student_count,
        "users":    user_count,
        "tasks":    task_count
    })


# ============================================================
# ROUTE 6: GET ALL STUDENTS (JSON)
# Your students.html calls this with fetch() to show the table
#
# JavaScript example in students.html:
#   fetch('https://your-api.onrender.com/students')
#     .then(r => r.json())
#     .then(students => {
#       students.forEach(s => {
#         // build table rows dynamically
#       });
#     });
# ============================================================
@app.route("/students", methods=["GET"])
def get_students():
    conn     = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    return jsonify([dict(s) for s in students])


# ============================================================
# ROUTE 7: ADD STUDENT
# Your add_student.html form POSTs here
#
# HTML form:
#   <form method="POST" action="https://your-api.onrender.com/add_student">
#     <input name="name" />
#     <input name="email" />
#     <input name="course" />
#     <input name="marks" type="number" />
#   </form>
# ============================================================
@app.route("/add_student", methods=["POST"])
def add_student():
    name   = request.form.get("name",   "").strip()
    email  = request.form.get("email",  "").strip()
    course = request.form.get("course", "").strip()
    marks  = request.form.get("marks",  "").strip()

    if not name or not email or not course or not marks:
        return redirect_to("add_student", "All fields are required!", "error")

    try:
        marks_int = int(marks)
        if not (0 <= marks_int <= 100):
            return redirect_to("add_student", "Marks must be between 0 and 100!", "error")
    except ValueError:
        return redirect_to("add_student", "Marks must be a valid number!", "error")

    conn = get_db()
    conn.execute(
        "INSERT INTO students (name, email, course, marks) VALUES (?, ?, ?, ?)",
        (name, email, course, marks_int)
    )
    conn.commit()
    conn.close()
    return redirect_to("students", "Student added successfully!", "success")


# ============================================================
# ROUTE 8: EDIT STUDENT
# GET  → returns student data as JSON (to pre-fill edit form)
# POST → saves updated data
# ============================================================
@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    if request.method == "GET":
        conn    = get_db()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (id,)).fetchone()
        conn.close()
        if student:
            return jsonify(dict(student))
        return jsonify({"error": "Student not found"}), 404

    # POST — update record
    name   = request.form.get("name",   "").strip()
    email  = request.form.get("email",  "").strip()
    course = request.form.get("course", "").strip()
    marks  = request.form.get("marks",  "").strip()

    if not name or not email or not course or not marks:
        return redirect_to("edit_student", "All fields are required!", "error")

    try:
        marks_int = int(marks)
    except ValueError:
        return redirect_to("edit_student", "Marks must be a number!", "error")

    conn = get_db()
    conn.execute(
        "UPDATE students SET name=?, email=?, course=?, marks=? WHERE id=?",
        (name, email, course, marks_int, id)
    )
    conn.commit()
    conn.close()
    return redirect_to("students", "Student updated successfully!", "success")


# ============================================================
# ROUTE 9: DELETE STUDENT
# ============================================================
@app.route("/delete_student/<int:id>")
def delete_student(id):
    conn = get_db()
    conn.execute("DELETE FROM students WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect_to("students", "Student deleted!", "success")


# ============================================================
# ROUTE 10: GET ALL TASKS (JSON)
# Pass ?user_id=1 to get tasks for a specific user
# ============================================================
@app.route("/tasks", methods=["GET"])
def get_tasks():
    user_id = request.args.get("user_id")
    conn    = get_db()

    if user_id:
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
    else:
        tasks = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()

    conn.close()
    return jsonify([dict(t) for t in tasks])


# ============================================================
# ROUTE 11: ADD TASK
# HTML form:
#   <form method="POST" action="https://your-api.onrender.com/add_task">
#     <input name="title" />
#     <input name="description" />
#     <select name="status">...</select>
#     <input name="user_id" type="hidden" value="1" />
#   </form>
# ============================================================
@app.route("/add_task", methods=["POST"])
def add_task():
    title       = request.form.get("title",       "").strip()
    description = request.form.get("description", "").strip()
    status      = request.form.get("status",      "Pending")
    user_id     = request.form.get("user_id",     "").strip()

    if not title:
        return redirect_to("add_task", "Task title is required!", "error")

    conn = get_db()
    conn.execute(
        "INSERT INTO tasks (title, description, status, user_id) VALUES (?, ?, ?, ?)",
        (title, description, status, user_id or None)
    )
    conn.commit()
    conn.close()
    return redirect_to("tasks", "Task added successfully!", "success")


# ============================================================
# ROUTE 12: EDIT TASK
# ============================================================
@app.route("/edit_task/<int:id>", methods=["GET", "POST"])
def edit_task(id):
    if request.method == "GET":
        conn = get_db()
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        conn.close()
        if task:
            return jsonify(dict(task))
        return jsonify({"error": "Task not found"}), 404

    title       = request.form.get("title",       "").strip()
    description = request.form.get("description", "").strip()
    status      = request.form.get("status",      "Pending")

    if not title:
        return redirect_to("edit_task", "Title is required!", "error")

    conn = get_db()
    conn.execute(
        "UPDATE tasks SET title=?, description=?, status=? WHERE id=?",
        (title, description, status, id)
    )
    conn.commit()
    conn.close()
    return redirect_to("tasks", "Task updated successfully!", "success")


# ============================================================
# ROUTE 13: DELETE TASK
# ============================================================
@app.route("/delete_task/<int:id>")
def delete_task(id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect_to("tasks", "Task deleted!", "success")


# ============================================================
# ROUTE 14: CALCULATOR (JSON API)
# Frontend uses fetch() — no page reload needed
#
# JavaScript example in calculator.html:
#   fetch('https://your-api.onrender.com/calculator', {
#     method: 'POST',
#     headers: { 'Content-Type': 'application/json' },
#     body: JSON.stringify({ num1: 10, num2: 3, operation: 'add' })
#   })
#   .then(r => r.json())
#   .then(data => {
#     document.getElementById('result').textContent = data.expression;
#   });
# ============================================================
@app.route("/calculator", methods=["POST"])
def calculator():
    # Accept both JSON body and HTML form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    try:
        num1      = float(data.get("num1", 0))
        num2      = float(data.get("num2", 0))
        operation = data.get("operation", "")
    except (ValueError, TypeError):
        return jsonify({"error": "Please enter valid numbers."}), 400

    result = None
    symbol = ""

    if operation == "add":
        result, symbol = num1 + num2, "+"
    elif operation == "subtract":
        result, symbol = num1 - num2, "−"
    elif operation == "multiply":
        result, symbol = num1 * num2, "×"
    elif operation == "divide":
        if num2 == 0:
            return jsonify({"error": "Cannot divide by zero!"}), 400
        result, symbol = num1 / num2, "÷"
    elif operation == "modulus":
        if num2 == 0:
            return jsonify({"error": "Cannot use modulus with zero!"}), 400
        result, symbol = num1 % num2, "mod"
    elif operation == "power":
        result, symbol = num1 ** num2, "^"
    else:
        return jsonify({"error": "Invalid operation!"}), 400

    display = int(result) if result == int(result) else round(result, 6)

    return jsonify({
        "num1":       num1,
        "num2":       num2,
        "operation":  operation,
        "symbol":     symbol,
        "result":     display,
        "expression": f"{num1} {symbol} {num2} = {display}"
    })


# ============================================================
# START SERVER
# ============================================================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"StudyFlow API running on port {port}")
    print(f"Frontend URL: {NETLIFY_URL}")
    app.run(host="0.0.0.0", port=port, debug=False)
