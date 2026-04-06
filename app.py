import os
from flask import Flask, request, redirect, render_template, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import openpyxl

# =========================
# APP + DB
# =========================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret123")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELY
# =========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(100))
    password = db.Column(db.String(200))


class Zakazka(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazev = db.Column(db.String(200))
    popis = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# HELPER
# =========================
def current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None

# =========================
# EXPORT
# =========================
def export_to_excel(filename, rows):
    wb = openpyxl.Workbook()
    ws = wb.active

    for r in rows:
        ws.append(r)

    wb.save(filename)


def daily_backup():
    with app.app_context():
        zakazky = Zakazka.query.all()
        rows = [[z.id, z.nazev, z.popis, z.created_at] for z in zakazky]

        filename = f"daily_{datetime.now().strftime('%Y%m%d')}.xlsx"
        export_to_excel(filename, rows)
        print("Daily backup created")


def weekly_backup():
    with app.app_context():
        zakazky = Zakazka.query.all()
        rows = [[z.id, z.nazev, z.popis, z.created_at] for z in zakazky]

        filename = f"weekly_{datetime.now().strftime('%Y%m%d')}.xlsx"
        export_to_excel(filename, rows)
        print("Weekly backup created")

# =========================
# SCHEDULER (OPRAVA)
# =========================
scheduler = BackgroundScheduler()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(daily_backup, "cron", hour=6)
        scheduler.add_job(weekly_backup, "cron", day_of_week="sun", hour=6)
        scheduler.start()
        print("Scheduler started")

# 👉 DŮLEŽITÉ: spustí se jen na Renderu (gunicorn)
if __name__ != "__main__":
    start_scheduler()

# =========================
# ROUTES
# =========================
@app.route("/")
def index():
    if not current_user():
        return redirect("/login")

    zakazky = Zakazka.query.all()
    return render_template("index.html", zakazky=zakazky)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        if User.query.filter_by(username=username).first():
            flash("Uživatel existuje")
            return redirect("/register")

        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()

        flash("Registrace OK")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect("/")
        else:
            flash("Špatné údaje")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/add", methods=["GET", "POST"])
def add():
    if not current_user():
        return redirect("/login")

    if request.method == "POST":
        nazev = request.form["nazev"]
        popis = request.form["popis"]

        z = Zakazka(nazev=nazev, popis=popis)
        db.session.add(z)
        db.session.commit()

        return redirect("/")

    return render_template("add_zakazka.html")


@app.route("/delete/<int:id>")
def delete(id):
    z = Zakazka.query.get(id)
    db.session.delete(z)
    db.session.commit()
    return redirect("/")

# =========================
# INIT DB
# =========================
with app.app_context():
    db.create_all()

# =========================
# RUN (jen lokálně)
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
import logging
logging.basicConfig(level=logging.DEBUG)
