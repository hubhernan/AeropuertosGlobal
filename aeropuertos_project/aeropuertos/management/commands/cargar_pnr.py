"""
Management command: cargar_pnr
===============================
Carga el archivo PNR3_Jan-June_2026.xlsx en la tabla 'vuelos_pnr' de PostgreSQL.

Uso:
    python manage.py cargar_pnr
    python manage.py cargar_pnr --archivo /ruta/al/archivo.xlsx
    python manage.py cargar_pnr --limpiar    # borra los datos existentes antes de cargar
    python manage.py cargar_pnr --lote 2000  # tamaño de lote para bulk_create

Proceso de limpieza y normalización:
  1. Elimina la fila "Gran Total" (última fila del Excel)
  2. Elimina filas con datos críticos nulos
  3. Parsea la fecha "DD-MM-YYYY HH:MM" → DateTimeField
  4. Extrae fecha (date) y hora (time) por separado
  5. Calcula mes, semana ISO y día de semana
  6. Separa código y nombre de la aerolínea del formato "UA - UNITED AIRLINES"
  7. Cuenta segmentos de ruta (guiones en la ruta)
  8. Calcula 'pasajeros' = max(APIS, PNR, DCS)
  9. Inserta en lotes (bulk_create) para máxima velocidad
"""

import sys
import warnings
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from aeropuertos.models import VueloPNR

# Zona horaria local de las operaciones de vuelo (CDMX = UTC-6 / UTC-5 en verano)
TZ_LOCAL = ZoneInfo("America/Mexico_City")

# Silenciar warnings de datetime naive (se resuelven con zoneinfo abajo)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="django")


# ---------------------------------------------------------------------------
# Ruta por defecto al archivo Excel (relativa a manage.py)
# ---------------------------------------------------------------------------
EXCEL_DEFAULT = Path(__file__).resolve().parents[4] / "Aeropuertos" / "PNR3_Jan-June_2026.xlsx"


def _parsear_aerolinea(valor: str) -> tuple[str, str]:
    """
    Descompone el campo 'Nombre de Aerolinea' en (código, nombre).

    Formatos posibles:
      'UA - UNITED AIRLINES'  → ('UA',  'UNITED AIRLINES')
      'Y4 - VOLARIS'          → ('Y4',  'VOLARIS')
      '2D'                    → ('2D',  '')
      'AMF'                   → ('AMF', '')
    """
    if not isinstance(valor, str):
        return ("", "")
    valor = valor.strip()
    if " - " in valor:
        partes = valor.split(" - ", 1)
        return partes[0].strip(), partes[1].strip()
    return valor, ""


def _construir_objeto(fila: pd.Series) -> VueloPNR | None:
    """
    Transforma una fila del DataFrame en un objeto VueloPNR (sin guardar).
    Retorna None si la fila no es válida.
    """
    try:
        fecha_vuelo_naive = fila["fecha_dt"]
        if pd.isna(fecha_vuelo_naive):
            return None

        # Convertir datetime naive → aware con zona horaria CDMX
        fecha_vuelo = fecha_vuelo_naive.to_pydatetime().replace(tzinfo=TZ_LOCAL)

        codigo_al, nombre_al = _parsear_aerolinea(fila["Nombre de Aerolinea"])
        ruta = str(fila["Ruta"]).strip()
        segmentos = ruta.count("-")          # 'MEX-CUN' → 1 guión → 2 segmentos ≈ 1 salto
        num_seg = segmentos if segmentos > 0 else 1

        apis = int(fila["APIS"])
        pnr  = int(fila["PNR"])
        dcs  = int(fila["DCS"])

        return VueloPNR(
            # --- Campos originales ---
            fecha_vuelo        = fecha_vuelo,
            nombre_aerolinea   = str(fila["Nombre de Aerolinea"]).strip(),
            numero_vuelo       = str(fila["No. Vuelo"]).strip(),
            ruta               = ruta,
            aeropuerto_salida  = str(fila["Aeropuerto de Salida"]).strip().upper(),
            aeropuerto_llegada = str(fila["Aeropuerto de Llegada"]).strip().upper(),
            apis               = apis,
            pnr                = pnr,
            dcs                = dcs,
            # --- Campos derivados ---
            fecha                  = fecha_vuelo.date(),
            hora_salida            = fecha_vuelo.time(),
            mes                    = fecha_vuelo.month,
            semana                 = fecha_vuelo.isocalendar().week,
            dia_semana             = fecha_vuelo.weekday(),   # 0=Lun … 6=Dom
            codigo_aerolinea       = codigo_al,
            nombre_corto_aerolinea = nombre_al,
            num_segmentos          = num_seg,
            pasajeros              = max(apis, pnr, dcs),
        )
    except Exception:
        return None


class Command(BaseCommand):
    help = "Carga el archivo PNR3_Jan-June_2026.xlsx en la base de datos PostgreSQL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--archivo",
            type=str,
            default=str(EXCEL_DEFAULT),
            help="Ruta completa al archivo .xlsx (por defecto usa Aeropuertos/PNR3_Jan-June_2026.xlsx)",
        )
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Elimina todos los registros existentes antes de cargar",
        )
        parser.add_argument(
            "--lote",
            type=int,
            default=5000,
            help="Número de registros por lote en bulk_create (default: 5000)",
        )

    def handle(self, *args, **options):
        archivo = Path(options["archivo"])
        tam_lote = options["lote"]

        # ------------------------------------------------------------------
        # 1. Verificar que el archivo existe
        # ------------------------------------------------------------------
        if not archivo.exists():
            raise CommandError(f"Archivo no encontrado: {archivo}")

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.MIGRATE_HEADING("  CARGA DE DATOS PNR3"))
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"  Archivo : {archivo}")
        self.stdout.write(f"  Lote    : {tam_lote:,} registros")

        # ------------------------------------------------------------------
        # 2. Leer el Excel
        # ------------------------------------------------------------------
        self.stdout.write("\n⏳ Leyendo Excel...")
        try:
            df = pd.read_excel(str(archivo), dtype={"No. Vuelo": str})
        except Exception as e:
            raise CommandError(f"Error al leer el Excel: {e}")

        self.stdout.write(f"   Filas brutas leídas: {len(df):,}")

        # ------------------------------------------------------------------
        # 3. Limpieza básica
        # ------------------------------------------------------------------

        # 3a. Eliminar filas con Nombre de Aerolinea nulo
        #     (incluye la fila "Gran Total" al final del Excel)
        antes = len(df)
        df = df.dropna(subset=["Nombre de Aerolinea"])
        self.stdout.write(f"   Filas eliminadas (nulas/totales): {antes - len(df)}")

        # 3b. Eliminar filas donde Aeropuerto de Salida o Llegada estén vacíos
        df = df.dropna(subset=["Aeropuerto de Salida", "Aeropuerto de Llegada", "Ruta"])

        # 3c. Parsear fecha "DD-MM-YYYY HH:MM" → datetime
        df["fecha_dt"] = pd.to_datetime(
            df["Fecha Vuelo"],
            format="%d-%m-%Y %H:%M",
            errors="coerce",
        )
        fechas_invalidas = df["fecha_dt"].isna().sum()
        if fechas_invalidas:
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  {fechas_invalidas} fechas inválidas (se omitirán)")
            )
        df = df.dropna(subset=["fecha_dt"])

        self.stdout.write(f"   Filas limpias para cargar: {len(df):,}")

        # ------------------------------------------------------------------
        # 4. Limpiar tabla si se pidió
        # ------------------------------------------------------------------
        if options["limpiar"]:
            self.stdout.write("\n🗑️  Eliminando registros existentes...")
            count_borrado = VueloPNR.objects.count()
            VueloPNR.objects.all().delete()
            self.stdout.write(f"   {count_borrado:,} registros eliminados.")

        # ------------------------------------------------------------------
        # 5. Construcción y carga por lotes
        # ------------------------------------------------------------------
        self.stdout.write("\n📦 Construyendo objetos e insertando en lotes...")

        total_filas = len(df)
        total_insertados = 0
        total_errores    = 0
        lote_objetos     = []

        for i, (_, fila) in enumerate(df.iterrows(), start=1):
            obj = _construir_objeto(fila)
            if obj is None:
                total_errores += 1
                continue

            lote_objetos.append(obj)

            # Insertar cuando el lote está lleno o es la última fila
            if len(lote_objetos) >= tam_lote or i == total_filas:
                with transaction.atomic():
                    VueloPNR.objects.bulk_create(lote_objetos, ignore_conflicts=False)
                total_insertados += len(lote_objetos)
                lote_objetos = []

                # Progreso
                pct = i / total_filas * 100
                self.stdout.write(
                    f"\r   {total_insertados:>8,} insertados  |  "
                    f"{i:>8,}/{total_filas:,} procesados  |  "
                    f"{pct:5.1f}%",
                    ending="",
                )
                sys.stdout.flush()

        self.stdout.write("")  # nueva línea tras el progreso

        # ------------------------------------------------------------------
        # 6. Resumen final
        # ------------------------------------------------------------------
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS("  ✅ CARGA COMPLETADA"))
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"  Registros insertados : {total_insertados:>10,}")
        self.stdout.write(f"  Registros con error  : {total_errores:>10,}")
        self.stdout.write(
            f"  Total en BD          : {VueloPNR.objects.count():>10,}"
        )

        # Estadísticas rápidas
        self.stdout.write("\n📊 Vista previa estadísticas:")
        from django.db.models import Sum, Avg, Count
        stats = VueloPNR.objects.aggregate(
            total_vuelos   = Count("id"),
            total_pasajeros= Sum("pasajeros"),
            pax_promedio   = Avg("pasajeros"),
        )
        self.stdout.write(
            f"  Vuelos totales       : {stats['total_vuelos']:>10,}"
        )
        self.stdout.write(
            f"  Pasajeros totales    : {stats['total_pasajeros']:>10,}"
        )
        self.stdout.write(
            f"  Pasajeros por vuelo  : {stats['pax_promedio']:>10.1f}"
        )
        self.stdout.write(f"{'='*60}\n")
