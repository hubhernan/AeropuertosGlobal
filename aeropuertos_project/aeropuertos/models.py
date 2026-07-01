"""
Modelos de la app 'aeropuertos'.

Un modelo en Django es la representación en Python de una tabla en la base de datos.
GeoDjango extiende el ORM de Django con campos geográficos (PointField, etc.)
y funciones espaciales (distancia, intersección, etc.).
"""

from django.contrib.gis.db import models


class Aeropuerto(models.Model):
    """
    Modelo que representa un aeropuerto con sus datos básicos y ubicación.

    Hereda de 'models.Model' de django.contrib.gis (no del django estándar)
    para tener acceso a los campos y funciones GIS.

    Cada atributo de clase = una columna en la tabla 'aeropuertos_aeropuerto'.
    """

    # ------------------------------------------------------------------
    # CAMPOS DE TEXTO
    # ------------------------------------------------------------------

    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del aeropuerto",
        help_text="Ej: Aeropuerto Internacional Benito Juárez"
    )
    # CharField = columna de tipo VARCHAR en PostgreSQL.
    # max_length es obligatorio y define el tamaño máximo del texto.

    ciudad = models.CharField(
        max_length=100,
        verbose_name="Ciudad"
    )

    pais = models.CharField(
        max_length=100,
        verbose_name="País",
        default="México"
    )

    codigo_iata = models.CharField(
        max_length=3,
        unique=True,           # No puede haber dos aeropuertos con el mismo código
        verbose_name="Código IATA",
        help_text="Código de 3 letras. Ej: MEX, GDL, MTY"
    )

    codigo_icao = models.CharField(
        max_length=4,
        unique=True,
        blank=True,            # El campo puede estar vacío en formularios
        null=True,             # La columna puede ser NULL en la base de datos
        verbose_name="Código ICAO",
        help_text="Código de 4 letras. Ej: MMMX, MMGL"
    )

    # ------------------------------------------------------------------
    # CAMPO GEOGRÁFICO ← El corazón de GeoDjango
    # ------------------------------------------------------------------

    ubicacion = models.PointField(
        srid=4326,             # Sistema de Referencia: WGS84 (el estándar de GPS/Web)
        verbose_name="Ubicación geográfica",
        help_text="Punto geográfico (longitud, latitud) del aeropuerto"
    )
    # PointField almacena un punto (lon, lat) en PostGIS como tipo GEOMETRY(Point, 4326).
    # srid=4326 = WGS84, el mismo sistema que usan Google Maps, OpenStreetMap, MapLibre.
    # IMPORTANTE: PostGIS guarda (longitud, latitud), no (latitud, longitud).

    # ------------------------------------------------------------------
    # CAMPOS ADICIONALES ÚTILES
    # ------------------------------------------------------------------

    altitud_msnm = models.IntegerField(
        blank=True,
        null=True,
        verbose_name="Altitud (msnm)",
        help_text="Altitud en metros sobre el nivel del mar"
    )

    activo = models.BooleanField(
        default=True,
        verbose_name="¿Aeropuerto activo?"
    )

    # ------------------------------------------------------------------
    # METADATOS AUTOMÁTICOS
    # ------------------------------------------------------------------

    creado_en = models.DateTimeField(
        auto_now_add=True,     # Se rellena automáticamente al crear el registro
        verbose_name="Fecha de creación"
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,         # Se actualiza automáticamente en cada guardado
        verbose_name="Última actualización"
    )

    # ------------------------------------------------------------------
    # CONFIGURACIÓN DEL MODELO
    # ------------------------------------------------------------------

    class Meta:
        verbose_name = "Aeropuerto"
        verbose_name_plural = "Aeropuertos"
        ordering = ['codigo_iata']   # Ordena por defecto por código IATA (A-Z)
        db_table = 'aeropuertos'     # Nombre explícito de la tabla en PostgreSQL

    def __str__(self):
        """Representación legible del objeto (se usa en el admin de Django)."""
        return f"{self.codigo_iata} — {self.nombre} ({self.ciudad})"

    @property
    def latitud(self):
        """Propiedad conveniente para acceder a la latitud del punto."""
        return self.ubicacion.y  # En PostGIS/GEOS: y = latitud

    @property
    def longitud(self):
        """Propiedad conveniente para acceder a la longitud del punto."""
        return self.ubicacion.x  # En PostGIS/GEOS: x = longitud
