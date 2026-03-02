from flask import Flask, request, redirect, jsonify, session
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)

NETLIFY_URL = os.environ.get("NETLIFY_URL", "https://your-site.netlify.app")
app.secret_key = os.environ.get("SECRET_KEY", "studyflow_secret_2024")

CORS(app,
     supports_credentials=True,
     origins=[
         NETLIFY_URL,
         "http://127.0.0.1:5500",
         "http://localhost:5500",
         "http://127.0.0.1:3000",
         "http://localhost:3000",
     ])

DATABASE = "studyflow.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            course TEXT NOT NULL,
            marks INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'Pending',
            user_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print("Database is ready!")


# ⭐ IMPORTANT — initialize DB AFTER function definition
with app.app_context():
    init_db()
     
def redirect_to(page, msg="", msg_type="success"):
    url = f"{NETLIFY_URL}/{page}.html"
    if msg:
        safe_msg = msg.replace(" ", "+")
        url += f"?msg={safe_msg}&type={msg_type}"
    return redirect(url, code=302)


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



@app.route("/logout")
def logout():
    session.clear()
    return redirect_to("login", "Logged out successfully.", "success")



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



@app.route("/students", methods=["GET"])
def get_students():
    conn     = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    return jsonify([dict(s) for s in students])



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

@app.route("/delete_task/<int:id>")
def delete_task(id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect_to("tasks", "Task deleted!", "success")



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
     
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"StudyFlow API running on port {port}")
    print(f"Frontend URL: {NETLIFY_URL}")
    app.run(host="0.0.0.0", port=port, debug=False)
