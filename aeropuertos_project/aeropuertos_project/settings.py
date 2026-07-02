"""
Configuración de Django para el proyecto AeropuertosGlobal.

Estructura de este archivo:
  1. Importaciones y carga de variables de entorno (.env)
  2. Seguridad y modo de depuración
  3. Aplicaciones instaladas (incluyendo GeoDjango)
  4. Middleware (incluyendo WhiteNoise para archivos estáticos)
  5. Plantillas HTML
  6. Base de datos PostgreSQL + PostGIS
  7. Internacionalización (español / zona horaria México)
  8. Archivos estáticos
"""

from pathlib import Path
from dotenv import load_dotenv
import os
import dj_database_url

# =============================================================
# RUTAS BASE
# =============================================================
# BASE_DIR apunta a la carpeta que contiene manage.py
# Path(__file__) → este archivo (settings.py)
# .resolve()     → ruta absoluta real
# .parent        → carpeta aeropuertos_project/ (paquete de config)
# .parent        → carpeta aeropuertos_project/ (raíz del proyecto)
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================
# VARIABLES DE ENTORNO
# =============================================================
# Cargamos el archivo .env para leer valores secretos.
# Así nunca escribimos contraseñas directamente en el código.
load_dotenv(BASE_DIR / '.env')

# =============================================================
# SEGURIDAD
# =============================================================
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'clave-insegura-solo-para-desarrollo')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# =============================================================
# APLICACIONES INSTALADAS
# =============================================================
# Nota: El orden importa. 'django.contrib.gis' debe ir ANTES
# que cualquier app propia para que GeoDjango funcione.
INSTALLED_APPS = [
    # --- Apps de Django ---
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # --- GeoDjango: extiende Django con capacidades GIS ---
    # Habilita campos geográficos (PointField, PolygonField, etc.)
    # y funciones espaciales en el ORM de Django.
    'django.contrib.gis',

    # --- Nuestras apps ---
    'aeropuertos',  # App principal: modelos, vistas y URLs de aeropuertos

    # --- API REST ---
    'rest_framework',         # Django REST Framework: motor de la API
    'rest_framework_gis',     # Extensión GIS: serializa campos geográficos a GeoJSON
    'django_filters',         # Filtros avanzados para la API (?pais=Mexico, etc.)
]

# =============================================================
# MIDDLEWARE
# =============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # WhiteNoise: sirve archivos estáticos directamente desde Django.
    # Debe ir inmediatamente DESPUÉS de SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'aeropuertos_project.urls'

# =============================================================
# PLANTILLAS HTML
# =============================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # DIRS: lista de carpetas donde Django buscará plantillas.
        # BASE_DIR / 'templates' → aeropuertos_project/templates/
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,  # También busca en templates/ dentro de cada app
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'aeropuertos_project.wsgi.application'

# =============================================================
# BASE DE DATOS: PostgreSQL + PostGIS
# =============================================================
# Cambiamos el ENGINE estándar de Django por el de GeoDjango:
# 'django.db.backends.postgresql'     → solo PostgreSQL normal
# 'django.contrib.gis.db.backends.postgis' → PostgreSQL + PostGIS (GIS)
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DB_NAME', 'aeropuertos_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Si existe DATABASE_URL (ej. en Render), sobreescribir la configuración por defecto
if os.getenv("DATABASE_URL"):
    DATABASES['default'] = dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
        engine='django.contrib.gis.db.backends.postgis'
    )

# =============================================================
# VALIDACIÓN DE CONTRASEÑAS
# =============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================================================
# INTERNACIONALIZACIÓN
# =============================================================
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

# =============================================================
# ARCHIVOS ESTÁTICOS (CSS, JavaScript, Imágenes)
# =============================================================
STATIC_URL = '/static/'

# Carpeta donde collectstatic reúne todos los archivos para producción
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise comprime y cachea los archivos estáticos automáticamente
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =============================================================
# DJANGO REST FRAMEWORK
# =============================================================
REST_FRAMEWORK = {
    # Formato de respuesta por defecto: JSON puro
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        # BrowsableAPIRenderer permite explorar la API desde el navegador
        # (muy útil en desarrollo, se puede desactivar en producción)
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],

    # Paginación: limita cuántos registros devuelve cada petición
    # Sin paginación, una tabla con 100,000 filas romperia la API
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,  # Máximo 100 aeropuertos por página

    # Permisos por defecto: cualquiera puede leer (nuestra API es pública)
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

# =============================================================
# CLAVE DE API DE MAPTILER (para el mapa base)
# =============================================================
MAPTILER_API_KEY = os.getenv('MAPTILER_API_KEY', '')

# =============================================================
# OTROS
# =============================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
