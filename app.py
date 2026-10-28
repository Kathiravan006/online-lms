"""Online Learning Management System - Flask + SQLite.
Run:  pip install -r requirements.txt  &&  python app.py   ->  http://127.0.0.1:5000
"""
import sqlite3
from functools import wraps
from flask import Flask, g, redirect, render_template_string, request, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
import os
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
DB = "lms.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, pw TEXT, role TEXT);
CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY, title TEXT, description TEXT, teacher_id INTEGER);
CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT, content TEXT);
CREATE TABLE IF NOT EXISTS enrollments(user_id INTEGER, course_id INTEGER, UNIQUE(user_id, course_id));
CREATE TABLE IF NOT EXISTS progress(user_id INTEGER, lesson_id INTEGER, UNIQUE(user_id, lesson_id));
"""

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, args=(), one=False):
    cur = db().execute(sql, args)
    db().commit()
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows

def login_required(role=None):
    def deco(f):
        @wraps(f)
        def wrap(*a, **k):
            if "uid" not in session:
                return redirect(url_for("login"))
            if role and session["role"] != role:
                flash("Not allowed."); return redirect(url_for("home"))
            return f(*a, **k)
        return wrap
    return deco

BASE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>LMS</title><style>
body{font-family:system-ui;max-width:800px;margin:0 auto;padding:1rem;line-height:1.5}
nav{display:flex;gap:1rem;border-bottom:1px solid #ccc;padding-bottom:.5rem;margin-bottom:1rem}
.card{border:1px solid #ccc;border-radius:8px;padding:1rem;margin:.5rem 0}
input,textarea,select{width:100%;padding:.5rem;margin:.25rem 0 .75rem;box-sizing:border-box}
button{padding:.5rem 1rem}.bar{background:#ddd;height:8px;border-radius:4px}.bar i{display:block;height:8px;background:#0f7f82;border-radius:4px}
.flash{background:#fff3cd;padding:.5rem;border-radius:6px}
</style>
<nav><b>Learnly</b><a href="/">Courses</a>
{% if session.uid %}{% if session.role=='teacher' %}<a href="/course/new">New course</a>{% endif %}
<span style="margin-left:auto">{{session.name}} ({{session.role}}) <a href="/logout">Logout</a></span>
{% else %}<a href="/login" style="margin-left:auto">Login</a><a href="/register">Register</a>{% endif %}</nav>
{% for m in get_flashed_messages() %}<p class=flash>{{m}}</p>{% endfor %}
"""

def page(body, **ctx):
    return render_template_string(BASE + body, **ctx)

@app.route("/")
def home():
    courses = q("""SELECT c.*, u.name teacher FROM courses c JOIN users u ON u.id=c.teacher_id""")
    return page("""<h2>Courses</h2>{% for c in courses %}<div class=card>
      <h3><a href="/course/{{c.id}}">{{c.title}}</a></h3><small>by {{c.teacher}}</small><p>{{c.description}}</p></div>
      {% else %}<p>No courses yet.</p>{% endfor %}""", courses=courses)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        role = "teacher" if f.get("role") == "teacher" else "student"
        try:
            q("INSERT INTO users(name,email,pw,role) VALUES(?,?,?,?)",
              (f["name"], f["email"].lower(), generate_password_hash(f["password"]), role))
        except sqlite3.IntegrityError:
            flash("Email already registered."); return redirect(url_for("register"))
        flash("Account created. Please log in."); return redirect(url_for("login"))
    return page("""<h2>Register</h2><form method=post>
      Name<input name=name required>Email<input type=email name=email required>
      Password<input type=password name=password minlength=6 required>
      Role<select name=role><option value=student>Student</option><option value=teacher>Teacher</option></select>
      <button>Create account</button></form>""")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE email=?", (request.form["email"].lower(),), one=True)
        if u and check_password_hash(u["pw"], request.form["password"]):
            session.update(uid=u["id"], name=u["name"], role=u["role"])
            return redirect(url_for("home"))
        flash("Wrong email or password.")
    return page("""<h2>Login</h2><form method=post>Email<input type=email name=email required>
      Password<input type=password name=password required><button>Login</button></form>""")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.route("/course/new", methods=["GET", "POST"])
@login_required("teacher")
def new_course():
    if request.method == "POST":
        cur = db().execute("INSERT INTO courses(title,description,teacher_id) VALUES(?,?,?)",
                           (request.form["title"], request.form["description"], session["uid"]))
        db().commit()
        return redirect(url_for("course", cid=cur.lastrowid))
    return page("""<h2>New course</h2><form method=post>Title<input name=title required>
      Description<textarea name=description rows=3></textarea><button>Create</button></form>""")

@app.route("/course/<int:cid>")
def course(cid):
    c = q("SELECT c.*, u.name teacher FROM courses c JOIN users u ON u.id=c.teacher_id WHERE c.id=?", (cid,), one=True)
    if not c: return "Not found", 404
    lessons = q("SELECT * FROM lessons WHERE course_id=?", (cid,))
    uid = session.get("uid")
    enrolled = bool(uid and q("SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?", (uid, cid), one=True))
    done = {r["lesson_id"] for r in q("SELECT lesson_id FROM progress WHERE user_id=?", (uid,))} if uid else set()
    pct = round(100 * len([l for l in lessons if l["id"] in done]) / len(lessons)) if lessons else 0
    owner = uid == c["teacher_id"]
    return page("""<h2>{{c.title}}</h2><small>by {{c.teacher}}</small><p>{{c.description}}</p>
      {% if session.role=='student' and not enrolled %}<form method=post action="/course/{{c.id}}/enroll"><button>Enroll</button></form>{% endif %}
      {% if enrolled %}<div class=bar><i style="width:{{pct}}%"></i></div><small>{{pct}}% complete</small>{% endif %}
      <h3>Lessons</h3>{% for l in lessons %}<div class=card><b>{{loop.index}}. {{l.title}}</b>
        {% if enrolled or owner %}<p>{{l.content}}</p>{% endif %}
        {% if enrolled %}{% if l.id in done %}Done{% else %}<form method=post action="/lesson/{{l.id}}/done"><button>Mark done</button></form>{% endif %}{% endif %}
      </div>{% else %}<p>No lessons yet.</p>{% endfor %}
      {% if owner %}<h3>Add lesson</h3><form method=post action="/course/{{c.id}}/lesson">Title<input name=title required>
        Content<textarea name=content rows=4></textarea><button>Add lesson</button></form>
        <p>{{q_count}} student(s) enrolled.</p>{% endif %}""",
        c=c, lessons=lessons, enrolled=enrolled, done=done, pct=pct, owner=owner,
        q_count=q("SELECT COUNT(*) n FROM enrollments WHERE course_id=?", (cid,), one=True)["n"])

@app.post("/course/<int:cid>/enroll")
@login_required("student")
def enroll(cid):
    q("INSERT OR IGNORE INTO enrollments VALUES(?,?)", (session["uid"], cid))
    return redirect(url_for("course", cid=cid))

@app.post("/course/<int:cid>/lesson")
@login_required("teacher")
def add_lesson(cid):
    c = q("SELECT * FROM courses WHERE id=? AND teacher_id=?", (cid, session["uid"]), one=True)
    if c: q("INSERT INTO lessons(course_id,title,content) VALUES(?,?,?)", (cid, request.form["title"], request.form["content"]))
    return redirect(url_for("course", cid=cid))

@app.post("/lesson/<int:lid>/done")
@login_required("student")
def lesson_done(lid):
    l = q("SELECT course_id FROM lessons WHERE id=?", (lid,), one=True)
    if l and q("SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?", (session["uid"], l["course_id"]), one=True):
        q("INSERT OR IGNORE INTO progress VALUES(?,?)", (session["uid"], lid))
        return redirect(url_for("course", cid=l["course_id"]))
    return redirect(url_for("home"))

if __name__ == "__main__":
    with sqlite3.connect(DB) as con:
        con.executescript(SCHEMA)
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
