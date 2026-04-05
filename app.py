import os
from flask import Flask, request, redirect, render_template_string, send_file, session
from openpyxl import Workbook

# DB
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# =========================
# DB SETUP
# =========================
Base = declarative_base()
engine = create_engine("sqlite:///data.db")
SessionDB = sessionmaker(bind=engine)
db = SessionDB()

# =========================
# APP
# =========================
app = Flask(__name__)
app.secret_key = "secret123"

# =========================
# USERS
# =========================
users = {"admin": {"password": "admin", "role": "admin"}}

# =========================
# DB MODELY
# =========================
class Zakazka(Base):
    __tablename__ = "zakazky"

    id = Column(Integer, primary_key=True)
    nazev = Column(String)
    owner = Column(String)


class Polozka(Base):
    __tablename__ = "polozky"

    id = Column(Integer, primary_key=True)
    zakazka_id = Column(Integer)
    nazev = Column(String)
    material = Column(String)
    cena_materialu = Column(Float)
    hodiny = Column(Float)
    sazba = Column(Float)
    datum = Column(String)


Base.metadata.create_all(engine)

# =========================
# HELPERS
# =========================
def current_user():
    return session.get("user")


def is_admin():
    return users.get(current_user(), {}).get("role") == "admin"

# =========================
# EXCEL
# =========================
def export_to_excel(zakazka_id):
    wb = Workbook()
    ws = wb.active

    ws.append(["Název", "Materiál", "Cena materiálu", "Hodiny", "Sazba", "Datum"])

    polozky = db.query(Polozka).filter_by(zakazka_id=zakazka_id).all()

    total = 0
    for p in polozky:
        cena = p.cena_materialu + (p.hodiny * p.sazba)
        total += cena
        ws.append([p.nazev, p.material, p.cena_materialu, p.hodiny, p.sazba, p.datum])

    ws.append(["", "", "", "", "Celkem", total])

    filename = f"zakazka_{zakazka_id}.xlsx"
    wb.save(filename)
    return filename

# =========================
# HTML
# =========================
LOGIN_HTML = """
<h2>Přihlášení</h2>
<form method='post'>
<input name='user' placeholder='Uživatel'><br>
<input name='password' type='password' placeholder='Heslo'><br>
<button>Přihlásit</button>
</form>
"""

INDEX_HTML = """
<h1>Zakázky ({{user}})</h1>
<a href='/logout'>Odhlásit</a>

<form method='post' action='/nova'>
<input name='nazev' placeholder='Nová zakázka'>
<button>Vytvořit</button>
</form>

{% for z in zakazky %}
<div>
<a href='/zakazka/{{z.id}}'>{{z.nazev}}</a> ({{z.owner}})
</div>
{% endfor %}
"""

DETAIL_HTML = """
<h2>{{z.nazev}}</h2>
<a href='/'>Zpět</a>

<form method='post' action='/pridat/{{z.id}}'>
<input name='nazev' placeholder='Název položky'><br>
<input name='material' placeholder='Materiál'><br>
<input name='cena_materialu' placeholder='Cena materiálu'><br>
<input name='hodiny' placeholder='Hodiny'><br>
<input name='sazba' placeholder='Sazba'><br>
<input name='datum' type='date'><br>
<button>Přidat</button>
</form>

{% for p in polozky %}
<div>
{{p.nazev}} | {{p.material}} | {{p.cena_materialu}} Kč | {{p.hodiny}} h | {{p.sazba}} Kč/h
</div>
{% endfor %}

<a href='/export/{{z.id}}'>Export do Excelu</a>
"""

# =========================
# ROUTES
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["user"]
        p = request.form["password"]
        if u in users and users[u]["password"] == p:
            session["user"] = u
            return redirect("/")
    return render_template_string(LOGIN_HTML)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
def index():
    if not current_user():
        return redirect("/login")

    if is_admin():
        zakazky = db.query(Zakazka).all()
    else:
        zakazky = db.query(Zakazka).filter_by(owner=current_user()).all()

    return render_template_string(INDEX_HTML, zakazky=zakazky, user=current_user())


@app.route("/zakazka/<int:id>")
def detail(id):
    z = db.query(Zakazka).get(id)
    polozky = db.query(Polozka).filter_by(zakazka_id=id).all()

    if not is_admin() and z.owner != current_user():
        return "Access denied"

    return render_template_string(DETAIL_HTML, z=z, polozky=polozky)


@app.route("/nova", methods=["POST"])
def nova():
    z = Zakazka(nazev=request.form["nazev"], owner=current_user())
    db.add(z)
    db.commit()
    return redirect("/")


@app.route("/pridat/<int:id>", methods=["POST"])
def pridat(id):
    try:
        p = Polozka(
            zakazka_id=id,
            nazev=request.form["nazev"],
            material=request.form["material"],
            cena_materialu=float(request.form["cena_materialu"].replace(",", ".")),
            hodiny=float(request.form["hodiny"].replace(",", ".")),
            sazba=float(request.form["sazba"].replace(",", ".")),
            datum=request.form["datum"]
        )
        db.add(p)
        db.commit()
    except ValueError:
        return "Chyba: čísla nejsou správně"

    return redirect(f"/zakazka/{id}")


@app.route("/export/<int:id>")
def export(id):
    filename = export_to_excel(id)
    return send_file(filename, as_attachment=True)

# =========================
# START
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
