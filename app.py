import os
from flask import Flask, request, redirect, render_template, session, flash, send_file, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
import pandas as pd
from io import BytesIO

# =========================
# APP
# =========================
app = Flask(__name__)

# SECRET KEY
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

# FIX pro Render (proxy + HTTPS)
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
    radky = db.relationship("Radek", backref="zakazka", cascade="all, delete-orphan")


class Radek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    zakazka_id = db.Column(db.Integer, db.ForeignKey("zakazka.id"))
    material = db.Column(db.String(200))
    kod_materialu = db.Column(db.String(100))
    dodavatel = db.Column(db.String(100))
    cislo_dokladu = db.Column(db.String(100))
    odprac_hodiny = db.Column(db.Float)
    datum = db.Column(db.Date)
    cas_na_ceste = db.Column(db.Float)
    km = db.Column(db.Float)

# =========================
# HELPER
# =========================
@app.before_request
def load_user():
    g.user = None
    if "user_id" in session:
        g.user = db.session.get(User, session["user_id"])


def current_user():
    return g.user

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
            return redirect("/")
        else:
            flash("Špatné údaje")
            return redirect("/login")
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
        nazev = request.form.get("nazev")
        popis = request.form.get("popis")
        if not nazev:
            flash("Zadej název")
            return redirect("/add")
        z = Zakazka(nazev=nazev, popis=popis)
        db.session.add(z)
        db.session.commit()
        return redirect("/")
    return render_template("add_zakazka.html")


@app.route("/zakazka/<int:zakazka_id>", methods=["GET", "POST"])
def zakazka_detail(zakazka_id):
    if not current_user():
        return redirect("/login")
    zakazka = db.session.get(Zakazka, zakazka_id)
    if not zakazka:
        flash("Zakázka nenalezena")
        return redirect("/")
    if request.method == "POST" and not zakazka.closed:
        radek = Radek(
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
        return redirect(f"/zakazka/{zakazka.id}")
    return render_template("add_radek.html", zakazka=zakazka)


@app.route("/radek/<int:radek_id>/edit", methods=["GET", "POST"])
def edit_radek(radek_id):
    radek = db.session.get(Radek, radek_id)
    if not radek or (radek.zakazka.closed and not current_user().is_admin):
        flash("Nepovolený přístup")
        return redirect("/")
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
        return redirect(f"/zakazka/{radek.zakazka.id}")
    return render_template("edit_radek.html", radek=radek)


@app.route("/zakazka/<int:zakazka_id>/export")
def export_zakazka(zakazka_id):
    if not current_user() or not current_user().is_admin:
        flash("Nepovolený přístup")
        return redirect("/")
    zakazka = db.session.get(Zakazka, zakazka_id)
    data = [{
        "Material": r.material,
        "Kód materiálu": r.kod_materialu,
        "Dodavatel": r.dodavatel,
        "Číslo dokladu": r.cislo_dokladu,
        "Odpracované hodiny": r.odprac_hodiny,
        "Datum": r.datum,
        "Čas na cestě": r.cas_na_ceste,
        "Km": r.km
    } for r in zakazka.radky]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name=f"{zakazka.nazev}.xlsx", as_attachment=True)


@app.route("/zakazka/<int:zakazka_id>/close")
def close_zakazka(zakazka_id):
    if not current_user() or not current_user().is_admin:
        flash("Nepovolený přístup")
        return redirect("/")
    zakazka = db.session.get(Zakazka, zakazka_id)
    zakazka.closed = True
    db.session.commit()
    flash("Zakázka uzavřena")
    return redirect(f"/zakazka/{zakazka.id}")


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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
