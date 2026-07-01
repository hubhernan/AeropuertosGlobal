"""
Vistas de la API REST para la app 'aeropuertos'.

Separamos las vistas de la API en este archivo (api_views.py) para
mantener el código organizado:
  - views.py      → vistas HTML (páginas para el navegador)
  - api_views.py  → vistas API (respuestas JSON/GeoJSON para JavaScript)

Usamos ViewSets de DRF: clases que agrupan automáticamente las operaciones
CRUD (Create, Read, Update, Delete) en un solo lugar.
"""

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Aeropuerto
from .serializers import AeropuertoGeoSerializer, AeropuertoListSerializer


class AeropuertoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API de Aeropuertos — solo lectura (GET).

    ReadOnlyModelViewSet genera automáticamente dos endpoints:
      GET /api/aeropuertos/          → lista todos los aeropuertos
      GET /api/aeropuertos/{iata}/   → detalle de un aeropuerto

    Endpoints adicionales (custom actions):
      GET /api/aeropuertos/geojson/           → FeatureCollection GeoJSON completo
      GET /api/aeropuertos/por_pais/          → aeropuertos agrupados por país
    """

    # QuerySet base: todos los aeropuertos activos, ordenados por IATA
    queryset = Aeropuerto.objects.filter(activo=True).order_by('codigo_iata')

    # El lookup_field define qué campo se usa en la URL para buscar un registro.
    # Por defecto DRF usa 'pk' (número de id). Nosotros usamos 'codigo_iata'
    # para que la URL sea /api/aeropuertos/MEX/ en lugar de /api/aeropuertos/1/
    lookup_field = 'codigo_iata'

    # --- FILTROS Y BÚSQUEDA ---
    filter_backends = [
        DjangoFilterBackend,           # Filtros exactos: ?pais=Mexico
        filters.SearchFilter,          # Búsqueda de texto: ?search=ciudad
        filters.OrderingFilter,        # Ordenamiento: ?ordering=ciudad
    ]
    filterset_fields  = ['pais', 'activo']     # ?pais=Mexico&activo=true
    search_fields     = ['codigo_iata', 'nombre', 'ciudad', 'pais']
    ordering_fields   = ['codigo_iata', 'ciudad', 'pais']

    def get_serializer_class(self):
        """
        Selecciona el serializer según el endpoint que se esté usando.

        - Para la acción 'geojson' → usa el GeoSerializer (produce GeoJSON)
        - Para el detalle de un aeropuerto → usa el GeoSerializer
        - Para la lista simple → usa el ListSerializer (más ligero)
        """
        if self.action in ('retrieve', 'geojson'):
            return AeropuertoGeoSerializer
        return AeropuertoListSerializer

    # ------------------------------------------------------------------
    # ENDPOINTS PERSONALIZADOS (custom actions)
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'], url_path='geojson')
    def geojson(self, request):
        """
        GET /api/aeropuertos/geojson/

        Devuelve un GeoJSON FeatureCollection con TODOS los aeropuertos.
        Este endpoint es el que usará el mapa de MapLibre para cargar
        los datos directamente desde la API (en lugar del HTML).

        Acepta los mismos filtros:
          /api/aeropuertos/geojson/?pais=Mexico
          /api/aeropuertos/geojson/?search=guadalajara
        """
        # Aplicar los mismos filtros que en la lista
        queryset = self.filter_queryset(self.get_queryset())
        serializer = AeropuertoGeoSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        # GeoFeatureModelSerializer con many=True produce automáticamente
        # un FeatureCollection: {"type": "FeatureCollection", "features": [...]}
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='por-pais')
    def por_pais(self, request):
        """
        GET /api/aeropuertos/por-pais/

        Devuelve un resumen de cuántos aeropuertos hay por país.
        Útil para estadísticas y filtros en el mapa.
        """
        from django.db.models import Count

        resumen = (
            Aeropuerto.objects
            .filter(activo=True)
            .values('pais')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        return Response(list(resumen))
