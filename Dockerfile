# Imagen base de Python optimizada para producción
FROM python:3.12-slim

# Directorio de trabajo
WORKDIR /app

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Instalamos dependencias del sistema necesarias para compilar librerías pesadas
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    git \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copiamos dependencias y las instalamos
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Copiamos el resto del proyecto
COPY . .

# Exponemos el puerto (Render usa variables de entorno, pero definimos uno por compatibilidad)
EXPOSE 10000

# Comando de inicio del servidor FastAPI con Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
