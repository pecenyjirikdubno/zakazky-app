import json
import os
from flask import Flask, request, redirect, render_template_string, send_file, session
from openpyxl import Workbook

DATA_FILE = "zakazky.json"
USERS_FILE = "users.json"

app = Flask(__name__)
app.secret_key = "secret123"

# =========================
# UŽIVATELÉ
# =========================
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"admin": {"password": "admin", "role": "admin"}}

users = load_users()

# =========================
# MODEL
# =========================
class Polozka:
    def __init__(self, nazev, material, cena_materialu, hodiny, sazba, datum):
        self.nazev = nazev
        self.material = material  # TEXT
        self.cena_materialu = float(cena_materialu)
        self.hodiny = float(hodiny)
        self.sazba = float(sazba)
        self.datum = datum

    def cena(self):
        return self.cena_materialu + (self.hodiny * self.sazba)

    def to_dict(self):
        return self.__dict__


class Zakazka:
    def __init__(self, nazev, owner):
        self.nazev = nazev
        self.owner = owner
        self.polozky = []

    def pridat(self, p):
        self.polozky.append(p)

    def celkem(self):
        return sum(p.cena() for p in self.polozky)

    def to_dict(self):
        return {
            "nazev": self.nazev,
            "owner": self.owner,
            "polozky": [p.to_dict() for p in self.polozky]
        }

# =========================
# DATA
# =========================
def save(zakazky):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([z.to_dict() for z in zakazky], f, ensure_ascii=False, indent=2)


def load():
    zakazky = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
            for z in data:
                zak = Zakazka(z["nazev"], z.get("owner", "admin"))
                for p in z["polozky"]:
                    zak.pridat(Polozka(**p))
                zakazky.append(zak)
    return zakazky


zakazky = load()

# =========================
# HELPERS
# =========================
def current_user():
    return session.get("user")


def is_admin():
    return users.get(current_user(), {}).get("role") == "admin"


def visible_zakazky():
    if is_admin():
        return zakazky
    return [z for z in zakazky if z.owner == current_user()]

# =========================
# EXCEL
# =========================
def export_to_excel(zakazka):
    wb = Workbook()
    ws = wb.active

    ws.append(["Název", "Materiál", "Cena materiálu", "Hodiny", "Sazba", "Datum", "Cena"])

    for p in zakazka.polozky:
        ws.append([p.nazev, p.material, p.cena_materialu, p.hodiny, p.sazba, p.datum, p.cena()])

    ws.append(["", "", "", "", "", "Celkem", zakazka.celkem()])

    filename = f"{zakazka.nazev}.xlsx"
    wb.save(filename)
    return filename

# =========================
# HTML
# =========================
LOGIN_HTML = """
<h2>Přihlášení</h2>
<form method='post'>
<input name='user' placeholder='Uživatel'><br>
<input name='password' placeholder='Heslo' type='password'><br>
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
<a href='/zakazka/{{loop.index0}}'>{{z.nazev}}</a> ({{z.owner}})
</div>
{% endfor %}
"""

DETAIL_HTML = """
<h2>{{z.nazev}}</h2>
<a href='/'>Zpět</a>

<form method='post' action='/pridat/{{zi}}'>
<input name='nazev' placeholder='Název položky'><br>
<input name='material' placeholder='Název materiálu'><br>
<input name='cena_materialu' placeholder='Cena materiálu'><br>
<input name='hodiny' placeholder='Hodiny'><br>
<input name='sazba' placeholder='Sazba'><br>
<input name='datum' type='date'><br>
<button>Přidat</button>
</form>

{% for p in z.polozky %}
<div>
{{p.nazev}} | {{p.material}} | {{p.cena_materialu}} Kč | {{p.hodiny}} h | {{p.sazba}} Kč/h → {{p.cena()}} Kč
</div>
{% endfor %}

<a href='/export/{{zi}}'>Export do Excelu</a>
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
    return render_template_string(INDEX_HTML, zakazky=visible_zakazky(), user=current_user())


@app.route("/zakazka/<int:i>")
def detail(i):
    z = zakazky[i]
    if not is_admin() and z.owner != current_user():
        return "Access denied"
    return render_template_string(DETAIL_HTML, z=z, zi=i)


@app.route("/nova", methods=["POST"])
def nova():
    zakazky.append(Zakazka(request.form["nazev"], current_user()))
    save(zakazky)
    return redirect("/")


@app.route("/pridat/<int:i>", methods=["POST"])
def pridat(i):
    z = zakazky[i]

    if not is_admin() and z.owner != current_user():
        return "Access denied"

    try:
        p = Polozka(
            request.form["nazev"],
            request.form["material"],
            request.form["cena_materialu"].replace(",", "."),
            request.form["hodiny"].replace(",", "."),
            request.form["sazba"].replace(",", "."),
            request.form["datum"]
        )

        z.pridat(p)
        save(zakazky)

    except ValueError:
        return "Chyba: Cena materiálu, hodiny a sazba musí být čísla"

    return redirect(f"/zakazka/{i}")


@app.route("/export/<int:i>")
def export(i):
    z = zakazky[i]
    if not is_admin() and z.owner != current_user():
        return "Access denied"
    filename = export_to_excel(z)
    return send_file(filename, as_attachment=True)


# =========================
# START
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
