# Použijeme oficiální Python image
FROM python:3.14-slim

# Nastavíme pracovní adresář
WORKDIR /app

# Zkopíruj requirements a nainstaluj závislosti
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Zkopíruj celý projekt
COPY . .

# Environment proměnné
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Spustíme Flask přes Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:$PORT", "app:app"]
