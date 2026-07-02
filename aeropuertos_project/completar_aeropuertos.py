import os
import django
import pandas as pd

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aeropuertos_project.settings')
django.setup()

from aeropuertos.models import Aeropuerto, VueloPNR
from django.contrib.gis.geos import Point

print("Identificando aeropuertos faltantes en el catálogo...")
pnr_sal = set(VueloPNR.objects.values_list('aeropuerto_salida', flat=True).distinct())
pnr_lle = set(VueloPNR.objects.values_list('aeropuerto_llegada', flat=True).distinct())
pnr_all = pnr_sal | pnr_lle
cat = set(Aeropuerto.objects.values_list('codigo_iata', flat=True))

faltantes = pnr_all - cat

if not faltantes:
    print("No hay aeropuertos faltantes.")
    exit()

print(f"Faltan {len(faltantes)} aeropuertos. Descargando datos de OurAirports...")
url = "https://davidmegginson.github.io/ourairports-data/airports.csv"
try:
    df_oa = pd.read_csv(url)
except Exception as e:
    print(f"Error descargando datos: {e}")
    exit()

df_oa = df_oa[df_oa['iata_code'].notna()]
df_oa = df_oa[df_oa['iata_code'].isin(faltantes)]

nuevos = []
encontrados = set()
for _, row in df_oa.iterrows():
    iata = row['iata_code']
    if iata in encontrados:
        continue
    encontrados.add(iata)
    
    nombre = row['name'] if pd.notna(row['name']) else iata
    municipio = row['municipality'] if pd.notna(row['municipality']) else ''
    pais_iso = row['iso_country'] if pd.notna(row['iso_country']) else ''
    
    # En GeoDjango es Point(longitud, latitud)
    geom = Point(float(row['longitude_deg']), float(row['latitude_deg']), srid=4326)
    
    nuevos.append(Aeropuerto(
        codigo_iata=iata,
        nombre=nombre,
        ciudad=municipio,
        pais=pais_iso,
        geom=geom
    ))

if nuevos:
    Aeropuerto.objects.bulk_create(nuevos, ignore_conflicts=True)
    print(f"Se insertaron {len(nuevos)} aeropuertos exitosamente.")
else:
    print("No se encontraron los aeropuertos faltantes en OurAirports.")

aun_faltan = faltantes - encontrados
if aun_faltan:
    print(f"\nAún faltan {len(aun_faltan)} aeropuertos que no están en la BD pública:")
    print(aun_faltan)
