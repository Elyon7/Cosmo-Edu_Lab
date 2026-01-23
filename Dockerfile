# Usa un'immagine base leggera con Python 3.10 (NiceGUI testato fino a 3.10)
FROM python:3.10-slim

# Evita interattività e problemi di permessi
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Installa dipendenze di sistema necessarie per Matplotlib, FastAPI e NiceGUI
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copia i file nella container
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Esponi la porta standard di Spaces
EXPOSE 7860

# Avvia l’app NiceGUI
CMD ["python", "App/main.py"]
