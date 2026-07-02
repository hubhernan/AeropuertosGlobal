"""
Vistas de la app 'aeropuertos'.

Una vista en Django es una función (o clase) que:
  1. Recibe una petición HTTP del navegador
  2. Consulta la base de datos si es necesario
  3. Prepara los datos
  4. Devuelve una respuesta (generalmente un HTML renderizado)
"""

import json
from django.shortcuts import render
from django.conf import settings
from .models import Aeropuerto


def mapa_aeropuertos(request):
    """
    Vista principal: renderiza el mapa con todos los aeropuertos.

    Flujo:
      1. Consulta todos los aeropuertos activos en la BD
      2. Los convierte a formato GeoJSON (estándar para datos geográficos en web)
      3. Pasa el GeoJSON y la API key al template HTML
    """

    # --- 1. Consultar aeropuertos en la base de datos ---
    # .filter(activo=True) → solo aeropuertos activos
    # .values() → devuelve diccionarios en lugar de objetos Python (más eficiente)
    aeropuertos = Aeropuerto.objects.filter(activo=True)

    # --- 2. Convertir a GeoJSON ---
    # GeoJSON es el formato estándar que MapLibre entiende para datos geográficos.
    # Estructura: {"type": "FeatureCollection", "features": [...]}
    features = []
    for a in aeropuertos:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [a.longitud, a.latitud]  # [lon, lat] — orden GeoJSON
            },
            "properties": {
                "id": a.id,
                "nombre": a.nombre,
                "ciudad": a.ciudad,
                "pais": a.pais,
                "iata": a.codigo_iata,
                "icao": a.codigo_icao or "",
            }
        }
        features.append(feature)

    geojson_aeropuertos = json.dumps({
        "type": "FeatureCollection",
        "features": features
    })

    # --- 3. Pasar datos al template ---
    # El diccionario 'context' hace que las variables estén disponibles
    # en el template HTML como {{ variable }}
    context = {
        "geojson_aeropuertos": geojson_aeropuertos,
        "maptiler_key": settings.MAPTILER_API_KEY,
        "total_aeropuertos": aeropuertos.count(),
    }

    return render(request, "aeropuertos/mapa.html", context)

def mapa_view(request):
    """Renderiza el mapa principal con MapLibre GL JS."""
    return render(request, 'aeropuertos/mapa.html', {
        'maptiler_key': settings.MAPTILER_API_KEY
    })

def dashboard_view(request):
    """Renderiza el dashboard alterno con Apache ECharts."""
    return render(request, 'aeropuertos/dashboard.html', {})
