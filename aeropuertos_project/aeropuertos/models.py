"""
Modelos de la app 'aeropuertos'.

Un modelo en Django es la representación en Python de una tabla en la base de datos.
GeoDjango extiende el ORM de Django con campos geográficos (PointField, etc.)
y funciones espaciales (distancia, intersección, etc.).

  Modelos:
    - Aeropuerto  : catálogo de aeropuertos con geometría GIS (PointField)
    - VueloPNR    : registros PNR3 Ene-Jun 2026 (APIS / PNR / DCS)
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


# ===========================================================================
# MODELO: VueloPNR
# ===========================================================================

class VueloPNR(models.Model):
    """
    Registro de vuelo proveniente del archivo PNR3_Jan-June_2026.xlsx.

    Cada fila representa UN VUELO con sus conteos de pasajeros según
    tres sistemas diferentes de captura:
      - APIS : Advance Passenger Information (manifiesto previo al vuelo)
      - PNR  : Passenger Name Record        (reservación del pasajero)
      - DCS  : Departure Control System     (check-in y embarque real)

    Además de los campos originales del Excel, se almacenan campos
    derivados (fecha, hora, mes, etc.) para acelerar consultas y
    análisis sin necesidad de procesar strings en cada consulta.
    """

    # ------------------------------------------------------------------
    # CAMPOS ORIGINALES (del Excel, normalizados)
    # ------------------------------------------------------------------

    fecha_vuelo = models.DateTimeField(
        verbose_name="Fecha y hora de salida",
        help_text="Fecha y hora de salida del vuelo (UTC-6 CDMX)",
        db_index=True,
    )

    nombre_aerolinea = models.CharField(
        max_length=120,
        verbose_name="Nombre de aerolínea",
        help_text="Código IATA y nombre de la aerolínea. Ej: 'UA - UNITED AIRLINES'",
    )

    numero_vuelo = models.CharField(
        max_length=20,
        verbose_name="Número de vuelo",
        help_text="Número de vuelo tal como lo registra la aerolínea",
    )

    ruta = models.CharField(
        max_length=120,
        verbose_name="Ruta completa",
        help_text="Secuencia de aeropuertos separados por guión. Ej: 'MEX-CUN' o 'DFW-MEX-BOG'",
        db_index=True,
    )

    aeropuerto_salida = models.CharField(
        max_length=10,
        verbose_name="Aeropuerto de salida (IATA)",
        help_text="Código IATA del aeropuerto de origen del viaje",
        db_index=True,
    )

    aeropuerto_llegada = models.CharField(
        max_length=10,
        verbose_name="Aeropuerto de llegada (IATA)",
        help_text="Código IATA del aeropuerto de destino final del viaje",
        db_index=True,
    )

    apis = models.IntegerField(
        default=0,
        verbose_name="Pasajeros APIS",
        help_text="Conteo de pasajeros según el sistema APIS (manifiesto previo al vuelo)",
    )

    pnr = models.IntegerField(
        default=0,
        verbose_name="Pasajeros PNR",
        help_text="Conteo de pasajeros según el sistema PNR (registro de reserva)",
    )

    dcs = models.IntegerField(
        default=0,
        verbose_name="Pasajeros DCS",
        help_text="Conteo de pasajeros según el sistema DCS (check-in y embarque real)",
    )

    # ------------------------------------------------------------------
    # CAMPOS DERIVADOS (calculados al momento de cargar los datos)
    # Almacenarlos evita procesar strings en cada consulta SQL.
    # ------------------------------------------------------------------

    fecha = models.DateField(
        verbose_name="Fecha de salida",
        help_text="Solo la fecha (sin hora), útil para agrupaciones diarias",
        db_index=True,
    )

    hora_salida = models.TimeField(
        verbose_name="Hora de salida",
        help_text="Solo la hora de salida, útil para análisis de franjas horarias",
    )

    mes = models.PositiveSmallIntegerField(
        verbose_name="Mes",
        help_text="Número de mes (1=Enero … 6=Junio)",
        db_index=True,
    )

    semana = models.PositiveSmallIntegerField(
        verbose_name="Semana del año",
        help_text="Número de semana ISO (1-53)",
    )

    dia_semana = models.PositiveSmallIntegerField(
        verbose_name="Día de la semana",
        help_text="0=Lunes, 1=Martes, … 6=Domingo",
    )

    codigo_aerolinea = models.CharField(
        max_length=10,
        verbose_name="Código IATA de aerolínea",
        help_text="Primeras 2 (o 3) letras del código de aerolínea. Ej: 'UA', 'AM', 'Y4'",
        db_index=True,
    )

    nombre_corto_aerolinea = models.CharField(
        max_length=100,
        verbose_name="Nombre corto de aerolínea",
        help_text="Solo el nombre, sin el código. Ej: 'UNITED AIRLINES'. Vacío si no disponible.",
        blank=True,
    )

    num_segmentos = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Número de segmentos",
        help_text="Cantidad de tramos en la ruta. 1=directo, 2=una escala, etc.",
    )

    pasajeros = models.IntegerField(
        default=0,
        verbose_name="Pasajeros (mejor estimación)",
        help_text=(
            "Máximo entre APIS, PNR y DCS. "
            "DCS es el más preciso (pasajeros que abordaron), "
            "pero no siempre está disponible; el máximo es la estimación más conservadora."
        ),
        db_index=True,
    )

    # ------------------------------------------------------------------
    # METADATOS
    # ------------------------------------------------------------------

    cargado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de carga al sistema",
    )

    # ------------------------------------------------------------------
    # CONFIGURACIÓN DEL MODELO
    # ------------------------------------------------------------------

    class Meta:
        verbose_name = "Vuelo PNR"
        verbose_name_plural = "Vuelos PNR"
        db_table = "vuelos_pnr"
        ordering = ["fecha_vuelo"]
        indexes = [
            # Índice compuesto para análisis de rutas origen-destino
            models.Index(
                fields=["aeropuerto_salida", "aeropuerto_llegada"],
                name="idx_pnr_od_pair",
            ),
            # Índice compuesto para series de tiempo por aerolínea
            models.Index(
                fields=["codigo_aerolinea", "fecha"],
                name="idx_pnr_aerolinea_fecha",
            ),
            # Índice para análisis mensual
            models.Index(
                fields=["mes", "aeropuerto_salida"],
                name="idx_pnr_mes_salida",
            ),
        ]

    def __str__(self):
        return (
            f"{self.codigo_aerolinea}{self.numero_vuelo} | "
            f"{self.ruta} | "
            f"{self.fecha_vuelo.strftime('%Y-%m-%d %H:%M')}"
        )

    @property
    def par_od(self):
        """Par Origen-Destino normalizado (siempre orden alfabético)."""
        a, b = self.aeropuerto_salida, self.aeropuerto_llegada
        return f"{min(a,b)}-{max(a,b)}"

    @property
    def es_vuelo_directo(self):
        """True si la ruta es de un solo tramo (sin escalas)."""
        return self.num_segmentos == 1
