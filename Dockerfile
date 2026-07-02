FROM python:3.12-slim

# Evitar que Python escriba archivos .pyc y forzar salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema requeridas para GeoDjango (GDAL, PostGIS, etc.)
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    && rm -rf /var/lib/apt/lists/*

# Configurar el directorio de trabajo
WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el código del proyecto
COPY . /app/

# Directorio donde está manage.py
WORKDIR /app/aeropuertos_project

# Recolectar archivos estáticos
RUN python manage.py collectstatic --noinput

# Exponer el puerto
EXPOSE 8000

# Comando para ejecutar en producción usando Gunicorn
CMD ["gunicorn", "aeropuertos_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
