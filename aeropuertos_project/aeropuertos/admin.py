"""
Configuración del panel de administración de Django para la app 'aeropuertos'.

El admin de Django genera automáticamente una interfaz web completa para
gestionar los modelos registrados aquí. Con ModelAdmin puedes personalizar:
  - Qué columnas se muestran en la lista
  - Por qué campos se puede buscar/filtrar
  - Cómo se organiza el formulario de edición
  - Y mucho más
"""

from django.contrib.gis import admin
from .models import Aeropuerto


@admin.register(Aeropuerto)
class AeropuertoAdmin(admin.GISModelAdmin):
    """
    Configuración del admin para el modelo Aeropuerto.

    Hereda de GISModelAdmin (en lugar del ModelAdmin estándar) para que
    el campo 'ubicacion' (PointField) se muestre como un mapa interactivo
    con OpenLayers donde puedes hacer clic para elegir coordenadas.
    """

    # ------------------------------------------------------------------
    # VISTA DE LISTA (la tabla principal del admin)
    # ------------------------------------------------------------------

    # Columnas visibles en la tabla de aeropuertos
    list_display = (
        'codigo_iata',
        'nombre',
        'ciudad',
        'pais',
        'codigo_icao',
        'altitud_msnm',
        'activo',
        'creado_en',
    )

    # Campos por los que se puede hacer clic para ordenar la tabla
    list_display_links = ('codigo_iata', 'nombre')

    # Filtros en el panel derecho de la lista
    list_filter = (
        'activo',
        'pais',
    )

    # Campos en los que actúa el buscador (la barra de búsqueda superior)
    search_fields = (
        'codigo_iata',
        'codigo_icao',
        'nombre',
        'ciudad',
        'pais',
    )

    # Ordenamiento por defecto: por código IATA ascendente
    ordering = ('codigo_iata',)

    # Cuántos registros mostrar por página
    list_per_page = 25

    # Campos que se pueden editar directamente desde la lista (sin entrar al registro)
    list_editable = ('activo',)

    # ------------------------------------------------------------------
    # FORMULARIO DE EDICIÓN (cuando abres un aeropuerto individual)
    # ------------------------------------------------------------------

    # Fieldsets: agrupa los campos en secciones con títulos dentro del formulario
    fieldsets = (
        ('Identificación', {
            'description': 'Códigos oficiales de identificación del aeropuerto.',
            'fields': (
                ('codigo_iata', 'codigo_icao'),
                'nombre',
            )
        }),
        ('Ubicación', {
            'description': 'Ciudad, país y coordenadas geográficas.',
            'fields': (
                ('ciudad', 'pais'),
                'altitud_msnm',
                'ubicacion',   # ← Este campo se renderiza como mapa interactivo
            )
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
        ('Metadatos (solo lectura)', {
            'classes': ('collapse',),   # Esta sección empieza colapsada
            'fields': ('creado_en', 'actualizado_en'),
        }),
    )

    # Campos que se muestran pero no se pueden editar (son automáticos)
    readonly_fields = ('creado_en', 'actualizado_en')

    # ------------------------------------------------------------------
    # OPCIONES ESPECÍFICAS DE GISModelAdmin (mapa OpenLayers)
    # ------------------------------------------------------------------

    # Zoom inicial del mapa cuando creas un aeropuerto nuevo
    map_width = 700
    map_height = 400
