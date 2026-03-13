from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "smart_pole_secret_key"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- DATABASE ----------
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    conn = get_db_connection()

    # Complaints table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        pole_id TEXT,
        complaint_type TEXT,
        description TEXT,
        latitude TEXT,
        longitude TEXT,
        image TEXT,
        status TEXT DEFAULT 'Pending',
        issue_date TEXT,
        updated_at TEXT
    )
    """)

    # Users table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()

create_table()

# ---------- ROUTES ----------
@app.route('/')
def home():
    return render_template('home.html')

# ---------- SUBMIT COMPLAINT ----------
@app.route('/complaint', methods=['GET', 'POST'])
def complaint():
    pole_id = request.args.get('pole_id')

    if request.method == 'POST':
        pole_id = request.form['pole_id']
        complaint_type = request.form['complaint_type']
        description = request.form['description']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        image = request.files['image']
        filename = None

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(UPLOAD_FOLDER, filename))

        issue_date = datetime.now().strftime("%Y-%m-%d")
        user_id = session.get('user_id')

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO complaints
            (user_id, pole_id, complaint_type, description,
             latitude, longitude, image, status, issue_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, pole_id, complaint_type, description,
            latitude, longitude, filename, "Pending", issue_date
        ))

        conn.commit()
        conn.close()

        return redirect(url_for('success'))

    return render_template('complaint.html', pole_id=pole_id)

@app.route('/success')
def success():
    return render_template('success.html')

# ---------- USER AUTH ----------
@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (name,email,password) VALUES (?,?,?)",
            (name,email,password)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email,password)
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('my_complaints'))

    return render_template('login.html')

@app.route('/user_logout')
def user_logout():
    session.clear()
    return redirect(url_for('home'))

# ---------- USER COMPLAINT HISTORY ----------
@app.route('/my_complaints')
def my_complaints():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    complaints = conn.execute("""
        SELECT * FROM complaints
        WHERE user_id=?
        ORDER BY id DESC
    """, (session['user_id'],)).fetchall()
    conn.close()

    return render_template('my_complaints.html', complaints=complaints)

# ---------- ADMIN LOGIN ----------
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))

    return render_template('admin_login.html')

# ---------- ADMIN DASHBOARD ----------
@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    complaints = conn.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()

    total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0]
    progress = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'").fetchone()[0]
    resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]

    conn.close()

    return render_template(
        'admin_dashboard.html',
        complaints=complaints,
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved
    )

# ---------- UPDATE STATUS ----------
@app.route('/update_status/<int:id>/<string:new_status>')
def update_status(id, new_status):
    updated_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    conn.execute("""
        UPDATE complaints
        SET status=?, updated_at=?
        WHERE id=?
    """, (new_status, updated_date, id))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

# ---------- ADMIN LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ---------- RUN ----------
if __name__ == '__main__':
    app.run(debug=True)
