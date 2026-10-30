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
    # curl: lo usa el healthcheck HTTP de Coolify (GET /healthz) dentro del contenedor;
    # la imagen slim no lo trae y sin él el chequeo falla con «curl: not found» → Degraded.
    curl \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libgl1 \
    # WeasyPrint (PDF ejecutivo del papel de trabajo NIIF): render nativo Pango/cairo
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    fonts-dejavu-core \
    # Nómina (RQ-005): comprobantes de pago del IESS en PDF → texto con `pdftotext -layout`
    poppler-utils \
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
