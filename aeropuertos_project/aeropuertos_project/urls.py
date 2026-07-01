"""
Configuración principal de URLs del proyecto AeropuertosGlobal.

Este archivo es el "enrutador maestro": recibe cada petición HTTP
y decide qué app la va a manejar.

Flujo de una petición:
  Navegador → urls.py (proyecto) → urls.py (app) → views.py → template HTML
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Panel de administración de Django
    # URL: http://localhost:8000/admin/
    path('admin/', admin.site.urls),

    # App de aeropuertos: delega a aeropuertos/urls.py
    # El '' significa que la app responde desde la raíz del sitio
    # URL: http://localhost:8000/
    path('', include('aeropuertos.urls')),
]
