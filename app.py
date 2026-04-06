import os
from flask import Flask, request, redirect, render_template, session, flash, g, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
import pandas as pd
import io

# =========================
# APP
# =========================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

# =========================
# DATABASE
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
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
    is_admin = db.Column(db.Boolean, default=False)

class Zakazka(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazev = db.Column(db.String(200))
    popis = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed = db.Column(db.Boolean, default=False)

class ZakazkaRadek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    zakazka_id = db.Column(db.Integer, db.ForeignKey("zakazka.id"), nullable=False)
    material = db.Column(db.String(200), nullable=False)
    kod_materialu = db.Column(db.String(100))
    dodavatel = db.Column(db.String(100))
    cislo_dokladu = db.Column(db.String(100))
    odprac_hodiny = db.Column(db.Float)
    datum = db.Column(db.Date)
    cas_na_ceste = db.Column(db.Float)
    km = db.Column(db.Float)

    zakazka = db.relationship("Zakazka", backref=db.backref("radky", lazy=True))

# =========================
# HELPERS
# =========================
def current_user():
    if "user_id" in session:
        return db.session.get(User, session["user_id"])
    return None

@app.before_request
def load_user():
    g.user = current_user()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user or not g.user.is_admin:
            flash("Nemáte oprávnění")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

# =========================
# ROUTES
# =========================
@app.route("/")
@login_required
def index():
    zakazky = Zakazka.query.order_by(Zakazka.created_at.desc()).all()
    return render_template("index.html", zakazky=zakazky)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password_raw = request.form.get("password")
        if not username or not password_raw:
            flash("Vyplň všechny údaje")
            return redirect("/register")
        if User.query.filter_by(username=username).first():
            flash("Uživatel existuje")
            return redirect("/register")
        password = generate_password_hash(password_raw)
        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Registrace OK")
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            flash("Vyplň údaje")
            return redirect("/login")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("index"))
        else:
            flash("Špatné údaje")
            return redirect("/login")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------
# Zakázky
# -------------------------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        nazev = request.form.get("nazev")
        popis = request.form.get("popis")
        if not nazev:
            flash("Zadej název")
            return redirect("/add")
        z = Zakazka(nazev=nazev, popis=popis)
        db.session.add(z)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("add_zakazka.html")

@app.route("/zakazka/<int:zakazka_id>", methods=["GET", "POST"])
@login_required
def zakazka_detail(zakazka_id):
    zakazka = db.session.get(Zakazka, zakazka_id)
    if not zakazka:
        flash("Zakázka nenalezena")
        return redirect(url_for("index"))
    if request.method == "POST":
        if zakazka.closed:
            flash("Zakázka je uzavřená, nelze upravovat")
            return redirect(request.url)
        radek = ZakazkaRadek(
            zakazka_id=zakazka.id,
            material=request.form.get("material"),
            kod_materialu=request.form.get("kod_materialu"),
            dodavatel=request.form.get("dodavatel"),
            cislo_dokladu=request.form.get("cislo_dokladu"),
            odprac_hodiny=float(request.form.get("odprac_hodiny") or 0),
            datum=request.form.get("datum"),
            cas_na_ceste=float(request.form.get("cas_na_ceste") or 0),
            km=float(request.form.get("km") or 0)
        )
        db.session.add(radek)
        db.session.commit()
        return redirect(request.url)
    return render_template("add_radek.html", zakazka=zakazka)

@app.route("/radek/<int:radek_id>/edit", methods=["GET", "POST"])
@login_required
def edit_radek(radek_id):
    radek = db.session.get(ZakazkaRadek, radek_id)
    if not radek:
        flash("Řádek nenalezen")
        return redirect(url_for("index"))
    if radek.zakazka.closed and not g.user.is_admin:
        flash("Zakázka je uzavřená, nelze upravovat")
        return redirect(url_for("zakazka_detail", zakazka_id=radek.zakazka.id))
    if request.method == "POST":
        radek.material = request.form.get("material")
        radek.kod_materialu = request.form.get("kod_materialu")
        radek.dodavatel = request.form.get("dodavatel")
        radek.cislo_dokladu = request.form.get("cislo_dokladu")
        radek.odprac_hodiny = float(request.form.get("odprac_hodiny") or 0)
        radek.datum = request.form.get("datum")
        radek.cas_na_ceste = float(request.form.get("cas_na_ceste") or 0)
        radek.km = float(request.form.get("km") or 0)
        db.session.commit()
        return redirect(url_for("zakazka_detail", zakazka_id=radek.zakazka.id))
    return render_template("edit_radek.html", radek=radek)

@app.route("/zakazka/<int:zakazka_id>/close")
@admin_required
def close_zakazka(zakazka_id):
    zakazka = db.session.get(Zakazka, zakazka_id)
    if zakazka:
        zakazka.closed = True
        db.session.commit()
        flash("Zakázka uzavřena")
    return redirect(url_for("zakazka_detail", zakazka_id=zakazka_id))

@app.route("/zakazka/<int:zakazka_id>/export")
@login_required
def export_zakazka(zakazka_id):
    zakazka = db.session.get(Zakazka, zakazka_id)
    if not zakazka:
        flash("Zakázka nenalezena")
        return redirect(url_for("index"))
    data = [{
        "Materiál": r.material,
        "Kód materiálu": r.kod_materialu,
        "Dodavatel": r.dodavatel,
        "Číslo dokladu": r.cislo_dokladu,
        "Odpracované hodiny": r.odprac_hodiny,
        "Datum": r.datum,
        "Čas na cestě": r.cas_na_ceste,
        "KM": r.km
    } for r in zakazka.radky]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name=f"zakazka_{zakazka_id}.xlsx", as_attachment=True)

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
