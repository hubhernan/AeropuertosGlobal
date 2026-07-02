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
from .models import Aeropuerto, VueloPNR


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


# ===========================================================================
# ADMIN: VueloPNR
# ===========================================================================

@admin.register(VueloPNR)
class VueloPNRAdmin(admin.ModelAdmin):
    """
    Admin para los registros de vuelos PNR3 Ene-Jun 2026.

    La tabla tiene ~223k registros, por lo que se deshabilita
    el conteo automático de filas para evitar queries lentas.
    """

    # Columnas visibles en la lista
    list_display = (
        'fecha_vuelo',
        'codigo_aerolinea',
        'nombre_corto_aerolinea',
        'numero_vuelo',
        'aeropuerto_salida',
        'aeropuerto_llegada',
        'ruta',
        'pasajeros',
        'apis',
        'pnr',
        'dcs',
        'num_segmentos',
    )

    # Campos por los que se puede buscar
    search_fields = (
        'codigo_aerolinea',
        'nombre_aerolinea',
        'numero_vuelo',
        'ruta',
        'aeropuerto_salida',
        'aeropuerto_llegada',
    )

    # Filtros en el panel lateral derecho
    list_filter = (
        'mes',
        'dia_semana',
        'codigo_aerolinea',
        'num_segmentos',
    )

    # Ordenamiento por defecto
    ordering = ('-fecha_vuelo',)

    # Registros por página (tabla grande → paginación más pequeña)
    list_per_page = 50

    # Deshabilitar el conteo total para no hacer COUNT(*) en 223k filas
    show_full_result_count = False

    # Campos de solo lectura (los derivados se calculan al cargar)
    readonly_fields = (
        'fecha',
        'hora_salida',
        'mes',
        'semana',
        'dia_semana',
        'codigo_aerolinea',
        'nombre_corto_aerolinea',
        'num_segmentos',
        'pasajeros',
        'cargado_en',
    )

    # Organización del formulario de detalle
    fieldsets = (
        ('Vuelo', {
            'fields': (
                ('fecha_vuelo', 'numero_vuelo'),
                ('nombre_aerolinea', 'codigo_aerolinea', 'nombre_corto_aerolinea'),
            )
        }),
        ('Ruta', {
            'fields': (
                'ruta',
                ('aeropuerto_salida', 'aeropuerto_llegada'),
                'num_segmentos',
            )
        }),
        ('Pasajeros (por sistema)', {
            'fields': (
                ('apis', 'pnr', 'dcs', 'pasajeros'),
            )
        }),
        ('Campos derivados (solo lectura)', {
            'classes': ('collapse',),
            'fields': (
                ('fecha', 'hora_salida'),
                ('mes', 'semana', 'dia_semana'),
                'cargado_en',
            )
        }),
    )
