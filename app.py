import os
from flask import Flask, request, redirect, render_template_string, send_file, session
from openpyxl import Workbook
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

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
# EMAIL SETTINGS
# =========================
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_TO_DAILY = "pecenyjirik@gmail.com"
EMAIL_TO_WEEKLY = "pecenyjiri@gmail.com"

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
    users = {"admin": {"password": "admin", "role": "admin"}}
    return users.get(current_user(), {}).get("role") == "admin"


def export_to_excel(zakazky, filename):
    wb = Workbook()
    ws = wb.active
    for zakazka in zakazky:
        ws.append([f"Zakázka: {zakazka.nazev}"])
        ws.append(["Název", "Materiál", "Cena materiálu", "Hodiny", "Sazba", "Datum", "Cena"])
        polozky = db.query(Polozka).filter_by(zakazka_id=zakazka.id).all()
        total = 0
        for p in polozky:
            cena = p.cena_materialu + (p.hodiny * p.sazba)
            total += cena
            ws.append([p.nazev, p.material, p.cena_materialu, p.hodiny, p.sazba, p.datum, cena])
        ws.append([])
        ws.append(["", "", "", "", "", "Celkem", total])
        ws.append([])
    wb.save(filename)
    return filename


def send_email(subject, body, filename, to_email):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg.set_content(body)

    with open(filename, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=os.path.basename(filename))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASSWORD)
        smtp.send_message(msg)
    print(f"Email sent to {to_email} with {filename}")


# =========================
# SCHEDULER
# =========================
scheduler = BackgroundScheduler()

def daily_backup():
    yesterday = datetime.now() - timedelta(days=1)
    polozky = db.query(Polozka).filter(Polozka.datum >= yesterday.strftime("%Y-%m-%d")).all()
    zak_ids = set(p.zakazka_id for p in polozky)
    zakazky = db.query(Zakazka).filter(Zakazka.id.in_(zak_ids)).all()
    if zakazky:
        filename = f"daily_backup_{datetime.now().strftime('%Y%m%d')}.xlsx"
        export_to_excel(zakazky, filename)
        send_email("Denní záloha zakázek", "Denní záloha nových položek", filename, EMAIL_TO_DAILY)

def weekly_backup():
    zakazky = db.query(Zakazka).all()
    if zakazky:
        filename = f"weekly_backup_{datetime.now().strftime('%Y%m%d')}.xlsx"
        export_to_excel(zakazky, filename)
        send_email("Týdenní záloha zakázek", "Kompletní záloha zakázek", filename, EMAIL_TO_WEEKLY)

# Spuštění scheduleru
scheduler.add_job(daily_backup, "cron", hour=6, minute=0)  # každý den v 6:00
scheduler.add_job(weekly_backup, "cron", day_of_week="mon", hour=6, minute=0)  # každý pondělí v 6:00
scheduler.start()

# =========================
# ROUTES - jen pro testování scheduleru
# =========================
@app.route("/daily_backup")
def trigger_daily():
    daily_backup()
    return "Denní záloha odeslána"

@app.route("/weekly_backup")
def trigger_weekly():
    weekly_backup()
    return "Týdenní záloha odeslána"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
