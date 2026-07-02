"""
URLs de la app 'aeropuertos'.

Tenemos dos grupos de URLs:
  1. HTML → la página del mapa (para el navegador humano)
  2. API  → endpoints JSON/GeoJSON (para JavaScript y otras apps)

DRF Router genera automáticamente estas rutas desde los ViewSets:

  Aeropuertos (catálogo GIS):
    /api/aeropuertos/               → lista de aeropuertos (JSON)
    /api/aeropuertos/{iata}/        → detalle de un aeropuerto (GeoJSON)
    /api/aeropuertos/geojson/       → FeatureCollection GeoJSON completo
    /api/aeropuertos/por-pais/      → resumen por país

  Vuelos PNR (análisis Ene-Jun 2026):
    /api/pnr/resumen/               → estadísticas globales
    /api/pnr/por-aeropuerto/        → vuelos/pax por aeropuerto (para el mapa)
    /api/pnr/rutas/                 → pares OD con conteos (para líneas en el mapa)
    /api/pnr/por-aerolinea/         → ranking de aerolíneas
    /api/pnr/serie-tiempo/          → serie temporal (dia/semana/mes)
    /api/pnr/{iata}/detalle/        → análisis completo de un aeropuerto
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api_views import AeropuertoViewSet
from .pnr_views import PNRViewSet

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
router.register(
    r'pnr',               # prefijo de URL: /api/pnr/
    PNRViewSet,           # ViewSet de análisis PNR
    basename='pnr'
)

urlpatterns = [
    # --- Vista HTML del mapa ---
    path('', views.mapa_aeropuertos, name='mapa'),
    
    # --- Vista HTML del Dashboard ---
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # --- API REST (todas las rutas generadas por el router) ---
    # Quedan disponibles bajo /api/
    path('api/', include(router.urls)),
]
