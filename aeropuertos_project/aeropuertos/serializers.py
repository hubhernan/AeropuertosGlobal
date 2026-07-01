"""
Serializers de la app 'aeropuertos'.

Un serializer en DRF hace dos cosas:
  1. SERIALIZACIÓN:   Objeto Python (Aeropuerto) → JSON/GeoJSON (para la respuesta)
  2. DESERIALIZACIÓN: JSON (del cliente)          → Objeto Python (para guardar en BD)

Usamos GeoFeatureModelSerializer (de djangorestframework-gis) en lugar del
ModelSerializer estándar porque queremos que el campo 'ubicacion' (PointField)
se convierta automáticamente en formato GeoJSON Feature:
  {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-99.07, 19.43]},
    "properties": {"iata": "MEX", "ciudad": "Ciudad de Mexico", ...}
  }
"""

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import Aeropuerto


class AeropuertoGeoSerializer(GeoFeatureModelSerializer):
    """
    Serializer GeoJSON completo para el mapa.

    Produce un GeoJSON Feature con:
      - geometry: el PointField (longitud, latitud)
      - properties: todos los campos seleccionados abajo

    Ideal para alimentar directamente a MapLibre como fuente de datos.
    """

    # Campos calculados (propiedades del modelo que no son columnas directas)
    latitud  = serializers.FloatField(read_only=True)
    longitud = serializers.FloatField(read_only=True)

    class Meta:
        model = Aeropuerto
        # geo_field: le dice al serializer cuál campo es la geometría
        geo_field = 'ubicacion'
        # fields: qué campos incluir en "properties" del GeoJSON
        fields = [
            'id',
            'codigo_iata',
            'codigo_icao',
            'nombre',
            'ciudad',
            'pais',
            'altitud_msnm',
            'activo',
            'latitud',
            'longitud',
        ]


class AeropuertoListSerializer(serializers.ModelSerializer):
    """
    Serializer ligero para listados (sin geometría).

    Devuelve JSON plano (no GeoJSON). Es más ligero que el GeoSerializer
    porque no incluye el campo de geometría. Útil para listas, tablas,
    autocompletado, etc.
    """

    class Meta:
        model = Aeropuerto
        fields = [
            'id',
            'codigo_iata',
            'codigo_icao',
            'nombre',
            'ciudad',
            'pais',
            'altitud_msnm',
            'activo',
        ]
