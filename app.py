import collections, collections.abc

# --- Compatibility shim for Python 3.13+ ---
try:
    # Python <3.13 still has collections.abc.Deque
    collections.Deque = collections.abc.Deque
except (AttributeError, ImportError):
    # In 3.13+, only 'collections.deque' exists
    from collections import deque as Deque
    collections.Deque = Deque

import os
import glob
import hashlib
import warnings
import sqlite3
import random
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask import g

# --- Processing imports ---
import docx2txt
try:
    import PyPDF2
except Exception:
    PyPDF2 = None
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.utils import secure_filename

from screen import res as screen_res  # your screening function
from search import res as search_res    # keep as is if you have search.py

warnings.filterwarnings("ignore")

app = Flask(__name__)

# --- Mail and DB (OTP) configuration ---
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')

#app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
#app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
#app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') in ['True','true','1']
#app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False') in ['True','true','1']
#app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
#app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

#mail = Mail(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'users.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password_hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    #cur.execute("""
    #CREATE TABLE IF NOT EXISTS otps (
     #   email TEXT,
      #  otp TEXT,
       # expires_at TIMESTAMP
    #)
    #""")
    conn.commit()
    conn.close()

init_db()

# --- Config ---
UPLOAD_FOLDER = os.path.join(os.getcwd(), "Original_Resumes")
JOB_FOLDER = os.path.join(os.getcwd(), "Job_Description")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(JOB_FOLDER, exist_ok=True)

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    USERNAME="testuser",
    PASSWORD=hashlib.md5("pass".encode("utf-8")).hexdigest(),
)

# --- Helper class for job descriptions ---
class JD:
    def __init__(self, name):
        self.name = name

# --- Routes ---

# ---------- Registration, Login (OTP), and Verification routes ----------

#def generate_otp():
    #return f"{random.randint(100000,999999)}"

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        if not (name and email and password):
            flash('Please fill all fields.', 'warning')
            return render_template('register.html')
        password_hash = generate_password_hash(password)
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)', (name, email, password_hash))
            conn.commit()
            conn.close()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('This email is already registered.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT password_hash FROM users WHERE email = ?', (email,))
        row = cur.fetchone()
        conn.close()
        if row is None or not check_password_hash(row[0], password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')
        session['logged_in'] = True
        session['user_email'] = email
        flash('Logged in successfully.', 'success')
        return redirect(url_for('home'))
    return render_template('login.html')

#@app.route('/verify-otp', methods=['GET','POST'])
#def verify_otp():
    email = session.get('otp_email')
    if not email:
        flash('No login attempt in progress. Please login first.', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        entered = request.form.get('otp')
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT otp, expires_at FROM otps WHERE email = ?', (email,))
        row = cur.fetchone()
        conn.close()
        if not row:
            flash('No OTP found; please request login again.', 'danger')
            return redirect(url_for('login'))
        otp_stored, expires = row
        expires_dt = datetime.fromisoformat(expires)
        if datetime.utcnow() > expires_dt:
            flash('OTP expired. Please login again.', 'warning')
            return redirect(url_for('login'))
        if entered == otp_stored:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('DELETE FROM otps WHERE email = ?', (email,))
            conn.commit()
            conn.close()
            session['logged_in'] = True
            session['user_email'] = email
            flash('OTP verified. You are now logged in.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid OTP. Try again.', 'danger')
    return render_template('otp_verify.html')

@app.route('/logout_all')
def logout_all():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

# ----------------------------------------------------------------------

# @app.route("/login", methods=["GET", "POST"])
# def login():
#     """Login page."""
#     error = None
#     if request.method == "POST":
#         username = request.form.get("username")
#         password = hashlib.md5(request.form.get("password", "").encode("utf-8")).hexdigest()

#         if username != app.config["USERNAME"]:
#             error = "Invalid username"
#         elif password != app.config["PASSWORD"]:
#             error = "Invalid password"
#         else:
#             session["logged_in"] = True
#             flash("You were logged in successfully!", "success")
#             return redirect(url_for("home"))

#     return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    """Logout."""
    session.pop("logged_in", None)
    #flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/")
def home():
    """Show job descriptions on homepage."""
    jobs = []
    for file in glob.glob(os.path.join(JOB_FOLDER, "*.txt")):
        jobs.append(JD(os.path.basename(file)))
    return render_template("index.html", results=jobs)

@app.route('/results', methods=['POST'])
def res():
    jobfile = None
    try:
        jobfile = request.form.get('des')
        if not jobfile:
            flash('Please select a job description.', 'warning')
            return redirect(url_for('home'))

        resumes = request.files.getlist('resumes_upload')
        if not resumes or resumes[0].filename == '':
            flash('Please upload at least one resume.', 'warning')
            return redirect(url_for('home'))

        # process resumes, jobfile here...

        results = screen_res(jobfile)  # Example screening function
    except Exception as e:
        flash(f'Error processing resumes: {e}', 'danger')
        results = []

    return render_template('result.html', results=results, title=f"Screening Results for {jobfile}")

@app.route("/Original_Resumes/<path:filename>")
def serve_resumes(filename):
    """Serve uploaded resumes."""
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed = hashlib.md5(password.encode('utf-8')).hexdigest() if password else ''

        if username != app.config['USERNAME']:
            error = "Invalid username"
        elif hashed != app.config['PASSWORD']:
            error = "Invalid password"
        else:
            session['logged_in'] = True
            #flash("Admin logged in successfully!", "success")
            return redirect(url_for('home'))
    return render_template('login.html', error=error)

# --- helper to extract text from uploaded files ---
def extract_text(file_path):
    path = file_path.lower()
    try:
        if path.endswith(".pdf") and PyPDF2 is not None:
            text = []
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    pg = page.extract_text()
                    if pg:
                        text.append(pg)
            return " ".join(text)
        elif path.endswith(".docx"):
            return docx2txt.process(file_path) or ""
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception:
        return ""

@app.route("/process", methods=["POST"])
def process():
    # Handle JD upload
    jd_file = request.files.get("jd_file")
    if not jd_file or jd_file.filename == "":
        flash("Please upload a Job Description file.", "warning")
        return redirect(url_for("home"))
    jd_filename = secure_filename(jd_file.filename)
    jd_path = os.path.join(JOB_FOLDER, jd_filename)
    jd_file.save(jd_path)

    # Handle resumes upload (multiple)
    resumes = request.files.getlist("resumes")
    if not resumes or len([r for r in resumes if r.filename]) == 0:
        flash("Please upload at least one resume.", "warning")
        return redirect(url_for("home"))

    resume_texts = []
    resume_names = []
    for r in resumes:
        if r and r.filename:
            name = secure_filename(r.filename)
            save_path = os.path.join(UPLOAD_FOLDER, name)
            r.save(save_path)
            resume_names.append(name)
            txt = extract_text(save_path)
            resume_texts.append(txt)

    jd_text = extract_text(jd_path)

    # Vectorize and compute cosine similarity
    corpus = [jd_text] + resume_texts
    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        matrix = vectorizer.fit_transform(corpus)
        scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten().tolist()
    except Exception as e:
        flash(f"Error during vectorization/similarity: {e}", "danger")
        return redirect(url_for("home"))

    results = list(zip(resume_names, scores))
    results.sort(key=lambda x: x[1], reverse=True)

    return render_template("result.html", results=results, jobfile=jd_filename)

if __name__ == "__main__":
    app.run(debug=True, threaded=True)