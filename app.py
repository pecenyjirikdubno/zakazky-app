import os
from flask import Flask, request, redirect, render_template, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import openpyxl

# =========================
# APP + DB
# =========================
app = Flask(__name__)

# ✅ SECRET KEY
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

# ✅ FIX PRO RENDER (cookies přes HTTPS)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_HTTPONLY"] = True

# 🔥 PostgreSQL z Renderu
DATABASE_URL = os.getenv("DATABASE_URL")

# oprava postgres://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or "sqlite:///data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELY
# =========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100))
    password = db.Column(db.String(200), nullable=False)


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
        return db.session.get(User, session["user_id"])
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
    z = db.session.get(Zakazka, id)
    if z:
        db.session.delete(z)
        db.session.commit()
    return redirect("/")

# =========================
# INIT DB
# =========================
with app.app_context():
    db.create_all()

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
