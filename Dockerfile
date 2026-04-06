# Dockerfile pro Flask aplikaci Zakázky App

# Základní image s Pythonem 3.14
FROM python:3.14-slim

# Nastavení pracovní složky
WORKDIR /app

# Kopírování requirements a instalace závislostí
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopírování celého projektu do containeru
COPY . .

# Otevření portu, který Render používá
EXPOSE 5000

# Spuštění aplikace přes gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "1"]
