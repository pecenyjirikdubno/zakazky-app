import os
from flask import Flask, request, redirect, url_for, render_template, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import smtplib
from email.message import EmailMessage
import openpyxl

# ---------------------------
# Flask a DB setup
# ---------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///zakazky.db"  # nebo jiná DB
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------------------------
# MODELY
# ---------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class Zakazka(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazev = db.Column(db.String(200), nullable=False)
    popis = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------------------
# EMAIL FUNKCE
# ---------------------------
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

def send_email(subject, body, to, attachment_path=None):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = to
    msg.set_content(body)

    if attachment_path:
        with open(attachment_path, "rb") as f:
            data = f.read()
            msg.add_attachment(data, maintype="application",
                               subtype="octet-stream",
                               filename=os.path.basename(attachment_path))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASSWORD)
        smtp.send_message(msg)

# ---------------------------
# EXPORT FUNKCE
# ---------------------------
def export_to_excel(filename, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(filename)

def daily_backup():
    rows = [[z.id, z.nazev, z.popis, z.created_at] for z in Zakazka.query.all()]
    filename = f"daily_backup_{datetime.now().strftime('%Y%m%d')}.xlsx"
    export_to_excel(filename, rows)
    send_email("Denní záloha zakázek", "Denní záloha byla vytvořena.",
               os.getenv("DAILY_BACKUP_EMAIL"), filename)

def weekly_backup():
    rows = [[z.id, z.nazev, z.popis, z.created_at] for z in Zakazka.query.all()]
    filename = f"weekly_backup_{datetime.now().strftime('%Y%m%d')}.xlsx"
    export_to_excel(filename, rows)
    send_email("Týdenní záloha zakázek", "Týdenní záloha byla vytvořena.",
               os.getenv("WEEKLY_BACKUP_EMAIL"), filename)

# ---------------------------
# SCHEDULER
# ---------------------------
scheduler = BackgroundScheduler()
scheduler.add_job(daily_backup, "cron", hour=6)
scheduler.add_job(weekly_backup, "cron", day_of_week="sun", hour=6)
scheduler.start()

# ---------------------------
# ROUTES
# ---------------------------
@app.route("/")
def index():
    return "Aplikace běží!"

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        if User.query.filter_by(username=username).first():
            flash("Uživatel již existuje")
            return redirect(url_for("register"))
        hashed = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed)
        db.session.add(new_user)
        db.session.commit()
        flash("Registrace úspěšná! Přihlaste se.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash("Přihlášení úspěšné")
            return redirect(url_for("index"))
        else:
            flash("Špatné přihlašovací údaje")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Byl jste odhlášen")
    return redirect(url_for("index"))

@app.route("/add_zakazka", methods=["GET", "POST"])
def add_zakazka():
    if request.method == "POST":
        nazev = request.form["nazev"]
        popis = request.form.get("popis")
        zakazka = Zakazka(nazev=nazev, popis=popis)
        db.session.add(zakazka)
        db.session.commit()
        flash("Zakázka byla přidána")
        return redirect(url_for("index"))
    return render_template("add_zakazka.html")

# ---------------------------
# RUN APP
# ---------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
