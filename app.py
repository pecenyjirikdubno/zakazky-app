import os
from flask import Flask, request, redirect, render_template_string, send_file, session
from openpyxl import Workbook
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage

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
    datum = Column(DateTime, default=datetime.now)


Base.metadata.create_all(engine)

# =========================
# HELPERS
# =========================
def current_user():
    return session.get("user")


def is_admin():
    return users.get(current_user(), {}).get("role") == "admin"


def export_to_excel(zakazky, polozky_dict, filename):
    wb = Workbook()
    ws = wb.active
    for z in zakazky:
        ws.append([f"Zakázka: {z.nazev}"])
        ws.append([])
        ws.append(["Název", "Materiál", "Cena materiálu", "Hodiny", "Sazba", "Datum", "Cena"])
        for p in polozky_dict.get(z.id, []):
            cena = p.cena_materialu + (p.hodiny * p.sazba)
            ws.append([
                p.nazev,
                p.material,
                p.cena_materialu,
                p.hodiny,
                p.sazba,
                p.datum.strftime("%Y-%m-%d"),
                cena
            ])
        ws.append([])
    wb.save(filename)
    return filename


def send_email(subject, body, attachment_path, to_email):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("EMAIL_USER")
    msg["To"] = to_email
    msg.set_content(body)
    with open(attachment_path, "rb") as f:
        data = f.read()
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=os.path.basename(attachment_path))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.environ.get("EMAIL_USER"), os.environ.get("EMAIL_PASSWORD"))
        smtp.send_message(msg)

# =========================
# HTML
# =========================
BOOTSTRAP = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
"""

LOGIN_HTML = BOOTSTRAP + """
<div class="container mt-5">
<h2>Přihlášení</h2>
<form method='post'>
<input name='user' class="form-control mb-2" placeholder='Uživatel'>
<input name='password' type='password' class="form-control mb-2" placeholder='Heslo'>
<button class="btn btn-primary">Přihlásit</button>
<a href='/register' class="btn btn-link">Registrovat nový účet</a>
</form>
</div>
"""

REGISTER_HTML = BOOTSTRAP + """
<div class="container mt-5">
<h2>Registrace</h2>
<form method='post'>
<input name='user' class="form-control mb-2" placeholder='Uživatelské jméno'>
<input name='password' type='password' class="form-control mb-2" placeholder='Heslo'>
<select name='role' class="form-control mb-2">
  <option value="user">Uživatel</option>
  <option value="admin">Admin</option>
</select>
<button class="btn btn-success">Registrovat</button>
<a href='/login' class="btn btn-link">Zpět na přihlášení</a>
</form>
</div>
"""

INDEX_HTML = BOOTSTRAP + """
<div class="container mt-4">
<h1 class="mb-4">Zakázky ({{user}})</h1>

<a href='/logout' class="btn btn-danger mb-3">Odhlásit</a>

<form method='post' action='/nova' class="mb-4">
  <div class="input-group">
    <input name='nazev' class="form-control" placeholder='Nová zakázka'>
    <button class="btn btn-primary">Vytvořit</button>
  </div>
</form>

<div class="list-group">
{% for z in zakazky %}
  <a href='/zakazka/{{z.id}}' class="list-group-item list-group-item-action">
    {{z.nazev}} <small class="text-muted">({{z.owner}})</small>
    <a href='/edit_zakazka/{{z.id}}' class='btn btn-sm btn-outline-warning float-end'>Editovat</a>
  </a>
{% endfor %}
</div>
</div>
"""

DETAIL_HTML = BOOTSTRAP + """
<div class="container mt-4">
<h2 class="mb-3">{{z.nazev}}</h2>
<a href='/' class="btn btn-secondary mb-3">Zpět</a>

<form method='post' action='/pridat/{{z.id}}' class="card p-3 mb-4">
  <div class="row g-2">
    <div class="col"><input name='nazev' class="form-control" placeholder='Název'></div>
    <div class="col"><input name='material' class="form-control" placeholder='Materiál'></div>
    <div class="col"><input name='cena_materialu' class="form-control" placeholder='Cena'></div>
    <div class="col"><input name='hodiny' class="form-control" placeholder='Hodiny'></div>
    <div class="col"><input name='sazba' class="form-control" placeholder='Sazba'></div>
    <div class="col"><input name='datum' type='date' class="form-control"></div>
  </div>
  <button class="btn btn-success mt-2">Přidat</button>
</form>

<table class="table table-striped">
<tr>
<th>Název</th><th>Materiál</th><th>Cena mat.</th><th>Hodiny</th><th>Sazba</th><th>Datum</th><th>Akce</th>
</tr>

{% for p in polozky %}
<tr>
<td>{{p.nazev}}</td>
<td>{{p.material}}</td>
<td>{{p.cena_materialu}}</td>
<td>{{p.hodiny}}</td>
<td>{{p.sazba}}</td>
<td>{{p.datum.strftime("%Y-%m-%d")}}</td>
<td>
  <a href='/edit_polozka/{{p.id}}' class='btn btn-sm btn-outline-warning'>Editovat</a>
</td>
</tr>
{% endfor %}
</table>

<a href='/export/{{z.id}}' class="btn btn-outline-primary">Export do Excelu</a>
</div>
"""

EDIT_ZAK_HTML = BOOTSTRAP + """
<div class="container mt-5">
<h2>Editace zakázky</h2>
<form method='post'>
<input name='nazev' value='{{z.nazev}}' class="form-control mb-2">
<button class="btn btn-success">Uložit</button>
<a href='/' class='btn btn-secondary'>Zpět</a>
</form>
</div>
"""

EDIT_POLOZ_HTML = BOOTSTRAP + """
<div class="container mt-5">
<h2>Editace položky</h2>
<form method='post'>
<input name='nazev' value='{{p.nazev}}' class="form-control mb-2">
<input name='material' value='{{p.material}}' class="form-control mb-2">
<input name='cena_materialu' value='{{p.cena_materialu}}' class="form-control mb-2">
<input name='hodiny' value='{{p.hodiny}}' class="form-control mb-2">
<input name='sazba' value='{{p.sazba}}' class="form-control mb-2">
<input name='datum' type='date' value='{{p.datum.strftime("%Y-%m-%d")}}' class="form-control mb-2">
<button class="btn btn-success">Uložit</button>
<a href='/zakazka/{{p.zakazka_id}}' class='btn btn-secondary'>Zpět</a>
</form>
</div>
"""

# =========================
# ROUTES
# =========================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["user"]
        p=request.form["password"]
        if u in users and users[u]["password"]==p:
            session["user"]=u
            return redirect("/")
    return render_template_string(LOGIN_HTML)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        u = request.form["user"]
        p = request.form["password"]
        r = request.form["role"]
        if u not in users:
            users[u] = {"password": p, "role": r}
            return redirect("/login")
        return "Uživatel již existuje"
    return render_template_string(REGISTER_HTML)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    if not current_user(): return redirect("/login")
    if is_admin(): zakazky = db.query(Zakazka).all()
    else: zakazky = db.query(Zakazka).filter_by(owner=current_user()).all()
    return render_template_string(INDEX_HTML, zakazky=zakazky, user=current_user())

@app.route("/zakazka/<int:id>")
def detail(id):
    z=db.query(Zakazka).get(id)
    polozky=db.query(Polozka).filter_by(zakazka_id=id).all()
    if not is_admin() and z.owner!=current_user(): return "Access denied"
    return render_template_string(DETAIL_HTML, z=z, polozky=polozky)

@app.route("/nova", methods=["POST"])
def nova():
    z=Zakazka(nazev=request.form["nazev"], owner=current_user())
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
            datum=datetime.strptime(request.form["datum"], "%Y-%m-%d")
        )
        db.add(p)
        db.commit()
    except ValueError:
        return "Chyba: čísla nejsou správně"
    return redirect(f"/zakazka/{id}")

@app.route("/edit_zakazka/<int:id>", methods=["GET","POST"])
def edit_zakazka(id):
    z=db.query(Zakazka).get(id)
    if request.method=="POST":
        z.nazev=request.form["nazev"]
        db.commit()
        return redirect("/")
    return render_template_string(EDIT_ZAK_HTML, z=z)

@app.route("/edit_polozka/<int:id>", methods=["GET","POST"])
def edit_polozka(id):
    p=db.query(Polozka).get(id)
    if request.method=="POST":
        p.nazev=request.form["nazev"]
        p.material=request.form["material"]
        p.cena_materialu=float(request.form["cena_materialu"].replace(",", "."))
        p.hodiny=float(request.form["hodiny"].replace(",", "."))
        p.sazba=float(request.form["sazba"].replace(",", "."))
        p.datum=datetime.strptime(request.form["datum"], "%Y-%m-%d")
        db.commit()
        return redirect(f"/zakazka/{p.zakazka_id}")
    return render_template_string(EDIT_POLOZ_HTML, p=p)

@app.route("/export/<int:id>")
def export(id):
    zakazka=db.query(Zakazka).get(id)
    polozky=db.query(Polozka).filter_by(zakazka_id=id).all()
    filename=f"{zakazka.nazev}.xlsx"
    export_to_excel([zakazka], {zakazka.id: polozky}, filename)
    return send_file(filename, as_attachment=True)

# =========================
# BACKUP ENDPOINTS
# =========================
@app.route("/daily_backup")
def daily_backup():
    yesterday=datetime.now()-timedelta(days=1)
    polozky=db.query(Polozka).filter(Polozka.datum>=yesterday).all()
    zakazky_ids={p.zakazka_id for p in polozky}
    zakazky=db.query(Zakazka).filter(Zakazka.id.in_(zakazky_ids)).all()
    polozky_dict={z.id:[] for z in zakazky}
    for p in polozky: polozky_dict[p.zakazka_id].append(p)
    filename=f"daily_backup_{datetime.now().strftime('%Y%m%d')}.xlsx"
    export_to_excel(zakazky,polozky_dict,filename)
    send_email("Denní záloha zakázek","Denní záloha nových položek.",filename,"pecenyjirik@gmail.com")
    return f"Daily backup sent: {filename}"

@app.route("/weekly_backup")
def weekly_backup():
    polozky=db.query(Polozka).all()
    zakazky=db.query(Zakazka).all()
    polozky_dict={z.id:[] for z in zakazky}
    for p in polozky: polozky_dict[p.zakazka_id].append(p)
    filename=f"weekly_backup_{datetime.now().strftime('%Y%m%d')}.xlsx"
    export_to_excel(zakazky,polozky_dict,filename)
    send_email("Týdenní záloha zakázek","Týdenní kompletní záloha.",filename,"pecenyjiri@gmail.com")
    return f"Weekly backup sent: {filename}"

# =========================
# START
# =========================
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)
