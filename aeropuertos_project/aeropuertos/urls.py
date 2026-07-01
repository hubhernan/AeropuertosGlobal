"""
URLs de la app 'aeropuertos'.

Tenemos dos grupos de URLs:
  1. HTML → la página del mapa (para el navegador humano)
  2. API  → endpoints JSON/GeoJSON (para JavaScript y otras apps)

DRF Router genera automáticamente estas rutas desde el ViewSet:
  /api/aeropuertos/               → lista de aeropuertos (JSON)
  /api/aeropuertos/{iata}/        → detalle de un aeropuerto (GeoJSON)
  /api/aeropuertos/geojson/       → FeatureCollection GeoJSON completo
  /api/aeropuertos/por-pais/      → resumen por país
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api_views import AeropuertoViewSet

app_name = 'aeropuertos'

# --- Router de DRF ---
# El router inspecciona el ViewSet y genera todas las URLs automáticamente.
# Sin router tendríamos que definir cada URL manualmente.
router = DefaultRouter()
router.register(
    r'aeropuertos',       # prefijo de URL: /api/aeropuertos/
    AeropuertoViewSet,    # ViewSet que maneja las peticiones
    basename='aeropuerto' # nombre base para reverse URLs
)

urlpatterns = [
    # --- Vista HTML del mapa ---
    path('', views.mapa_aeropuertos, name='mapa'),

    # --- API REST (todas las rutas generadas por el router) ---
    # Quedan disponibles bajo /api/
    path('api/', include(router.urls)),
]
