"""
API REST de análisis PNR — aeropuertos/pnr_views.py
=====================================================
Endpoints de análisis sobre los 223,248 registros de vuelos PNR3 Ene-Jun 2026.

Todos los endpoints son de solo lectura (GET) y devuelven JSON.
Soportan filtros opcionales mediante query params (?mes=1, ?aerolinea=AM, etc.)

Endpoints disponibles (prefijo /api/pnr/):
  GET resumen/           → Estadísticas globales del dataset
  GET por-aeropuerto/    → Vuelos y pasajeros agrupados por aeropuerto (para el mapa)
  GET rutas/             → Pares Origen-Destino con conteos (para líneas en el mapa)
  GET por-aerolinea/     → Ranking de aerolíneas por vuelos y pasajeros
  GET serie-tiempo/      → Serie temporal (granularidad: dia / semana / mes)
  GET {iata}/detalle/    → Análisis completo de un aeropuerto específico

Filtros comunes disponibles en la mayoría de endpoints:
  ?mes=1..6              → Filtrar por mes (1=Enero, 6=Junio)
  ?aerolinea=UA          → Filtrar por código IATA de aerolínea
  ?aeropuerto=MEX        → Filtrar por aeropuerto (salida O llegada)
  ?top=N                 → Limitar a los N primeros resultados

Filtros específicos de rutas:
  ?origen=MEX            → Solo rutas que salen de MEX
  ?destino=CUN           → Solo rutas que llegan a CUN
  ?min_vuelos=10         → Filtrar rutas con al menos 10 vuelos
"""

from django.db.models import Sum, Count, Min, Max, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from .models import VueloPNR, Aeropuerto


# ---------------------------------------------------------------------------
# Constante de nombres de mes en español
# ---------------------------------------------------------------------------
MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo",
    4: "Abril", 5: "Mayo",   6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre",
    10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles",
    3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_round(valor, decimales=1):
    """Redondea un valor que puede ser None."""
    return round(valor, decimales) if valor is not None else 0.0


def _aplicar_filtros_base(qs, request):
    """
    Aplica los filtros más comunes a un queryset de VueloPNR.

    Filtros soportados:
      ?mes=1..6         → filtra por mes
      ?aerolinea=UA     → filtra por código de aerolínea
      ?aeropuerto=MEX   → filtra donde MEX sea origen O destino
    """
    mes = request.query_params.get("mes")
    aerolinea = request.query_params.get("aerolinea")
    aeropuerto = request.query_params.get("aeropuerto")

    if mes:
        try:
            qs = qs.filter(mes=int(mes))
        except ValueError:
            pass

    if aerolinea:
        qs = qs.filter(codigo_aerolinea=aerolinea.strip().upper())

    if aeropuerto:
        iata = aeropuerto.strip().upper()
        qs = qs.filter(
            Q(aeropuerto_salida=iata) | Q(aeropuerto_llegada=iata)
        )

    return qs


# ---------------------------------------------------------------------------
# ViewSet principal
# ---------------------------------------------------------------------------

class PNRViewSet(viewsets.ViewSet):
    """
    ViewSet de análisis de datos PNR3 Ene-Jun 2026.

    Es un ViewSet 'puro': no implementa list/retrieve/create/update/delete.
    Todos los endpoints son acciones personalizadas (@action).

    El router DRF genera automáticamente las URLs al registrar este ViewSet.
    """

    # -----------------------------------------------------------------------
    # ENDPOINT 1: Resumen global
    # -----------------------------------------------------------------------

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        """
        GET /api/pnr/resumen/

        Devuelve las estadísticas globales del dataset.
        Útil para poblar el header/dashboard del mapa.

        Filtros opcionales: ?mes, ?aerolinea, ?aeropuerto
        """
        qs = _aplicar_filtros_base(VueloPNR.objects.all(), request)

        # Agregaciones principales
        stats = qs.aggregate(
            total_vuelos    = Count("id"),
            total_pasajeros = Sum("pasajeros"),
            total_apis      = Sum("apis"),
            total_pnr       = Sum("pnr"),
            total_dcs       = Sum("dcs"),
            fecha_min       = Min("fecha"),
            fecha_max       = Max("fecha"),
        )

        # Promedio calculado en Python para evitar colisión de nombre con el campo 'pasajeros'
        stats["pax_promedio"] = (
            round(stats["total_pasajeros"] / stats["total_vuelos"], 1)
            if (stats["total_vuelos"] or 0) > 0
            else 0.0
        )

        # Conteos de valores únicos
        stats["total_aerolineas"] = (
            qs.values("codigo_aerolinea").distinct().count()
        )
        stats["total_pares_od"] = (
            qs.values("aeropuerto_salida", "aeropuerto_llegada").distinct().count()
        )

        # Aeropuertos únicos (unión de orígenes y destinos)
        origenes  = set(qs.values_list("aeropuerto_salida", flat=True).distinct())
        destinos  = set(qs.values_list("aeropuerto_llegada", flat=True).distinct())
        stats["total_aeropuertos"] = len(origenes | destinos)

        # Formatear valores
        stats["pax_promedio"] = _safe_round(stats["pax_promedio"])
        stats["fecha_min"]    = str(stats["fecha_min"]) if stats["fecha_min"] else None
        stats["fecha_max"]    = str(stats["fecha_max"]) if stats["fecha_max"] else None

        return Response(stats)

    # -----------------------------------------------------------------------
    # ENDPOINT 2: Por aeropuerto (para el mapa)
    # -----------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="por-aeropuerto")
    def por_aeropuerto(self, request):
        """
        GET /api/pnr/por-aeropuerto/

        Devuelve vuelos y pasajeros agrupados por aeropuerto.
        Este endpoint alimenta directamente los marcadores del mapa:
        cuanto mayor el volumen, mayor puede ser el marcador.

        Filtros opcionales: ?mes, ?aerolinea, ?top=N
        """
        mes       = request.query_params.get("mes")
        aerolinea = request.query_params.get("aerolinea")
        top       = request.query_params.get("top")

        base_qs = VueloPNR.objects.all()
        if mes:
            base_qs = base_qs.filter(mes=int(mes))
        if aerolinea:
            base_qs = base_qs.filter(codigo_aerolinea=aerolinea.strip().upper())

        # Calcular salidas por aeropuerto
        salidas = {
            row["aeropuerto_salida"]: {
                "vuelos_salida": row["vuelos_salida"],
                "pax_salida":    row["pax_salida"] or 0,
            }
            for row in base_qs
            .values("aeropuerto_salida")
            .annotate(
                vuelos_salida = Count("id"),
                pax_salida    = Sum("pasajeros"),
            )
        }

        # Calcular llegadas por aeropuerto
        llegadas = {
            row["aeropuerto_llegada"]: {
                "vuelos_llegada": row["vuelos_llegada"],
                "pax_llegada":    row["pax_llegada"] or 0,
            }
            for row in base_qs
            .values("aeropuerto_llegada")
            .annotate(
                vuelos_llegada = Count("id"),
                pax_llegada    = Sum("pasajeros"),
            )
        }

        # Combinar salidas + llegadas en un solo objeto por aeropuerto
        todos = set(salidas.keys()) | set(llegadas.keys())
        resultado = []
        for iata in todos:
            s = salidas.get(iata,  {"vuelos_salida": 0, "pax_salida": 0})
            l = llegadas.get(iata, {"vuelos_llegada": 0, "pax_llegada": 0})
            vuelos_total = s["vuelos_salida"] + l["vuelos_llegada"]
            pax_total    = s["pax_salida"]    + l["pax_llegada"]
            resultado.append({
                "iata":           iata,
                "vuelos_salida":  s["vuelos_salida"],
                "vuelos_llegada": l["vuelos_llegada"],
                "vuelos_total":   vuelos_total,
                "pax_salida":     s["pax_salida"],
                "pax_llegada":    l["pax_llegada"],
                "pax_total":      pax_total,
            })

        # Ordenar por volumen total descendente
        resultado.sort(key=lambda x: x["vuelos_total"], reverse=True)

        if top:
            resultado = resultado[: int(top)]

        return Response(resultado)

    # -----------------------------------------------------------------------
    # ENDPOINT 3: Rutas OD (para líneas en el mapa)
    # -----------------------------------------------------------------------

    @action(detail=False, methods=["get"])
    def rutas(self, request):
        """
        GET /api/pnr/rutas/

        Devuelve los pares Origen-Destino con su conteo de vuelos y pasajeros.
        Ideal para dibujar líneas de rutas en el mapa (MapLibre LineLayer).

        Filtros opcionales:
          ?mes, ?aerolinea
          ?origen=MEX       → solo rutas que parten de MEX
          ?destino=CUN      → solo rutas que llegan a CUN
          ?top=N            → limitar a N rutas (default: 50)
          ?min_vuelos=N     → mínimo N vuelos para aparecer (default: 1)
        """
        qs         = VueloPNR.objects.all()
        mes        = request.query_params.get("mes")
        aerolinea  = request.query_params.get("aerolinea")
        origen     = request.query_params.get("origen")
        destino    = request.query_params.get("destino")
        top        = int(request.query_params.get("top", 50))
        min_vuelos = int(request.query_params.get("min_vuelos", 1))

        if mes:
            qs = qs.filter(mes=int(mes))
        if aerolinea:
            qs = qs.filter(codigo_aerolinea=aerolinea.strip().upper())
        if origen:
            qs = qs.filter(aeropuerto_salida=origen.strip().upper())
        if destino:
            qs = qs.filter(aeropuerto_llegada=destino.strip().upper())

        rutas = (
            qs
            .values("aeropuerto_salida", "aeropuerto_llegada")
            .annotate(
                vuelos    = Count("id"),
                pax_total = Sum("pasajeros"),    # nombre distinto evita colisión con el campo
            )
            .filter(vuelos__gte=min_vuelos)
            .order_by("-vuelos")[: top]
        )

        return Response([
            {
                "origen":    r["aeropuerto_salida"],
                "destino":   r["aeropuerto_llegada"],
                "vuelos":    r["vuelos"],
                "pasajeros": r["pax_total"] or 0,
                # Promedio calculado en Python: evita Avg() sobre campo ya anotado
                "pax_prom":  round((r["pax_total"] or 0) / r["vuelos"], 1) if r["vuelos"] else 0,
            }
            for r in rutas
        ])

    # -----------------------------------------------------------------------
    # ENDPOINT 4: Por aerolínea
    # -----------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="por-aerolinea")
    def por_aerolinea(self, request):
        """
        GET /api/pnr/por-aerolinea/

        Ranking de aerolíneas por vuelos y pasajeros.
        Útil para gráficas de barras, filtros y leyendas del mapa.

        Filtros opcionales: ?mes, ?aeropuerto, ?top=N
        """
        qs        = VueloPNR.objects.all()
        mes       = request.query_params.get("mes")
        aeropuerto = request.query_params.get("aeropuerto")
        top       = request.query_params.get("top")

        if mes:
            qs = qs.filter(mes=int(mes))
        if aeropuerto:
            iata = aeropuerto.strip().upper()
            qs = qs.filter(
                Q(aeropuerto_salida=iata) | Q(aeropuerto_llegada=iata)
            )

        datos = (
            qs
            .values("codigo_aerolinea", "nombre_corto_aerolinea")
            .annotate(
                vuelos    = Count("id"),
                pax_total = Sum("pasajeros"),    # nombre distinto al campo del modelo
            )
            .order_by("-vuelos")
        )

        if top:
            datos = datos[: int(top)]

        return Response([
            {
                "codigo":       d["codigo_aerolinea"],
                "nombre":       d["nombre_corto_aerolinea"],
                "vuelos":       d["vuelos"],
                "pasajeros":    d["pax_total"] or 0,
                # Promedio calculado en Python
                "pax_promedio": round((d["pax_total"] or 0) / d["vuelos"], 1) if d["vuelos"] else 0,
                "pct_vuelos":   None,
            }
            for d in datos
        ])

    # -----------------------------------------------------------------------
    # ENDPOINT 5: Serie de tiempo
    # -----------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="serie-tiempo")
    def serie_tiempo(self, request):
        """
        GET /api/pnr/serie-tiempo/

        Serie temporal de vuelos y pasajeros.
        Útil para gráficas de líneas / barras en el dashboard.

        Filtros opcionales: ?mes, ?aerolinea, ?aeropuerto
        Parámetro especial:
          ?granularidad=dia|semana|mes  (default: mes)
          ?dia_semana=true              → incluir desglose por día de semana
        """
        qs            = _aplicar_filtros_base(VueloPNR.objects.all(), request)
        granularidad  = request.query_params.get("granularidad", "mes").lower()
        por_dia_semana = request.query_params.get("dia_semana", "false").lower() == "true"

        if granularidad == "dia":
            datos = list(
                qs
                .values("fecha")
                .annotate(vuelos=Count("id"), pasajeros=Sum("pasajeros"))
                .order_by("fecha")
            )
            return Response({
                "granularidad": "dia",
                "datos": [
                    {
                        "periodo":   str(d["fecha"]),
                        "vuelos":    d["vuelos"],
                        "pasajeros": d["pasajeros"] or 0,
                    }
                    for d in datos
                ],
            })

        elif granularidad == "semana":
            datos = list(
                qs
                .values("semana", "mes")
                .annotate(vuelos=Count("id"), pasajeros=Sum("pasajeros"))
                .order_by("mes", "semana")
            )
            return Response({
                "granularidad": "semana",
                "datos": [
                    {
                        "semana":    d["semana"],
                        "mes":       d["mes"],
                        "mes_nombre": MESES.get(d["mes"], ""),
                        "vuelos":    d["vuelos"],
                        "pasajeros": d["pasajeros"] or 0,
                    }
                    for d in datos
                ],
            })

        else:  # mes (default)
            datos = list(
                qs
                .values("mes")
                .annotate(
                    vuelos     = Count("id"),
                    pax_total  = Sum("pasajeros"),
                    total_apis = Sum("apis"),
                    total_pnr  = Sum("pnr"),
                    total_dcs  = Sum("dcs"),
                )
                .order_by("mes")
            )

            respuesta = {
                "granularidad": "mes",
                "datos": [
                    {
                        "mes":          d["mes"],
                        "nombre":       MESES.get(d["mes"], ""),
                        "vuelos":       d["vuelos"],
                        "pasajeros":    d["pax_total"] or 0,
                        "pax_promedio": round((d["pax_total"] or 0) / d["vuelos"], 1) if d["vuelos"] else 0,
                        "apis":         d["total_apis"] or 0,
                        "pnr":          d["total_pnr"] or 0,
                        "dcs":          d["total_dcs"] or 0,
                    }
                    for d in datos
                ],
            }

            # Desglose adicional por día de la semana (si se solicita)
            if por_dia_semana:
                dias = list(
                    qs
                    .values("dia_semana")
                    .annotate(vuelos=Count("id"), pasajeros=Sum("pasajeros"))
                    .order_by("dia_semana")
                )
                respuesta["por_dia_semana"] = [
                    {
                        "dia":       d["dia_semana"],
                        "nombre":    DIAS_SEMANA.get(d["dia_semana"], ""),
                        "vuelos":    d["vuelos"],
                        "pasajeros": d["pasajeros"] or 0,
                    }
                    for d in dias
                ]

            return Response(respuesta)

    # -----------------------------------------------------------------------
    # ENDPOINT 6: Detalle por aeropuerto
    # -----------------------------------------------------------------------

    @action(detail=True, methods=["get"])
    def detalle(self, request, pk=None):
        """
        GET /api/pnr/{iata}/detalle/

        Análisis completo de un aeropuerto específico.
        Ideal para el panel lateral del mapa cuando el usuario hace clic
        en un aeropuerto.

        Devuelve:
          - Totales de salidas y llegadas
          - Desglose por mes
          - Desglose por hora del día
          - Top 10 aerolíneas operando en el aeropuerto
          - Top 10 destinos desde el aeropuerto
          - Top 10 orígenes hacia el aeropuerto
          - Comparativa APIS / PNR / DCS por mes

        Filtros opcionales: ?mes
        """
        iata = pk.strip().upper()
        mes  = request.query_params.get("mes")

        qs_sal = VueloPNR.objects.filter(aeropuerto_salida=iata)
        qs_lle = VueloPNR.objects.filter(aeropuerto_llegada=iata)

        if mes:
            try:
                mes_int = int(mes)
                qs_sal  = qs_sal.filter(mes=mes_int)
                qs_lle  = qs_lle.filter(mes=mes_int)
            except ValueError:
                pass

        # Verificar que el aeropuerto existe en los datos
        if not qs_sal.exists() and not qs_lle.exists():
            raise NotFound(detail=f"Aeropuerto '{iata}' no encontrado en los datos PNR.")

        # --- Totales ---
        # Usamos nombres distintos al campo del modelo para evitar colisión con ORM
        totales_sal = qs_sal.aggregate(
            vuelos    = Count("id"),
            pax_total = Sum("pasajeros"),
        )
        totales_lle = qs_lle.aggregate(
            vuelos    = Count("id"),
            pax_total = Sum("pasajeros"),
        )

        # --- Por mes ---
        por_mes = list(
            qs_sal
            .values("mes")
            .annotate(
                vuelos    = Count("id"),
                pax_total = Sum("pasajeros"),
                apis      = Sum("apis"),
                pnr       = Sum("pnr"),
                dcs       = Sum("dcs"),
            )
            .order_by("mes")
        )
        for d in por_mes:
            d["nombre_mes"] = MESES.get(d["mes"], "")
            d["pasajeros"]  = d.pop("pax_total") or 0

        # --- Por hora del día (franja horaria) ---
        por_hora = list(
            qs_sal
            .extra(select={"hora": "EXTRACT(HOUR FROM hora_salida)"})
            .values("hora")
            .annotate(vuelos=Count("id"), pasajeros=Sum("pasajeros"))
            .order_by("hora")
        )

        # --- Top 10 aerolíneas ---
        top_aerolineas = list(
            qs_sal
            .values("codigo_aerolinea", "nombre_corto_aerolinea")
            .annotate(vuelos=Count("id"), pax_total=Sum("pasajeros"))
            .order_by("-vuelos")[:10]
        )
        for d in top_aerolineas:
            d["pasajeros"] = d.pop("pax_total") or 0

        # --- Top 10 destinos desde este aeropuerto ---
        top_destinos = list(
            qs_sal
            .values("aeropuerto_llegada")
            .annotate(vuelos=Count("id"), pax_total=Sum("pasajeros"))
            .order_by("-vuelos")[:10]
        )
        for d in top_destinos:
            d["pasajeros"] = d.pop("pax_total") or 0

        # --- Top 10 orígenes hacia este aeropuerto ---
        top_origenes = list(
            qs_lle
            .values("aeropuerto_salida")
            .annotate(vuelos=Count("id"), pax_total=Sum("pasajeros"))
            .order_by("-vuelos")[:10]
        )
        for d in top_origenes:
            d["pasajeros"] = d.pop("pax_total") or 0

        return Response({
            "iata": iata,
            "salidas": {
                "vuelos":       totales_sal["vuelos"] or 0,
                "pasajeros":    totales_sal["pax_total"] or 0,
                "pax_promedio": round((totales_sal["pax_total"] or 0) / totales_sal["vuelos"], 1)
                                if (totales_sal["vuelos"] or 0) > 0 else 0,
            },
            "llegadas": {
                "vuelos":    totales_lle["vuelos"] or 0,
                "pasajeros": totales_lle["pax_total"] or 0,
            },
            "por_mes":        por_mes,
            "por_hora":       por_hora,
            "top_aerolineas": top_aerolineas,
            "top_destinos":   top_destinos,
            "top_origenes":   top_origenes,
        })

    # -----------------------------------------------------------------------
    # ENDPOINTS AVANZADOS PARA DASHBOARD Y COROPLETAS
    # -----------------------------------------------------------------------
    
    MAPA_ISO2 = {
        "Mexico": "MX", "Estados Unidos": "US", "Canada": "CA", "Colombia": "CO", 
        "Brasil": "BR", "Argentina": "AR", "Peru": "PE", "Chile": "CL", "Ecuador": "EC",
        "Venezuela": "VE", "Panama": "PA", "Costa Rica": "CR", "El Salvador": "SV",
        "Guatemala": "GT", "Honduras": "HN", "Nicaragua": "NI", "Belice": "BZ",
        "Cuba": "CU", "Republica Dominicana": "DO", "Jamaica": "JM", "Bahamas": "BS",
        "Aruba": "AW", "Antigua y Barbuda": "AG", "Bermuda": "BM", "Sint Maarten": "SX",
        "Reino Unido": "GB", "Francia": "FR", "España": "ES", "Italia": "IT", 
        "Alemania": "DE", "Paises Bajos": "NL", "Belgica": "BE", "Suiza": "CH",
        "Suecia": "SE", "Dinamarca": "DK", "Finlandia": "FI", "Islandia": "IS",
        "Polonia": "PL", "Portugal": "PT", "Turquia": "TR", "Emiratos Árabes Unidos": "AE",
        "China": "CN", "Japon": "JP", "Corea del Sur": "KR", "Islas Virgenes (EE. UU.)": "VI"
    }

    @classmethod
    def get_iso2(cls, pais):
        if not pais: return ""
        p = pais.strip()
        if p == "Espa\u00f1a" or p == "España": return "ES"
        if len(p) == 2: return p.upper()
        return cls.MAPA_ISO2.get(p, p)

    @action(detail=False, methods=["get"], url_path="por-pais")
    def por_pais(self, request):
        """
        Calcula el total de vuelos y pasajeros por país (para mapas de coropletas).
        Agrupa los vuelos según el país del aeropuerto de salida.
        """
        qs = _aplicar_filtros_base(VueloPNR.objects.all(), request)
        
        # Agrupar por aeropuerto primero para eficiencia, luego cruzar en Python
        por_ap = list(
            qs.values("aeropuerto_salida")
            .annotate(vuelos=Count("id"), pasajeros=Sum("pasajeros"))
        )
        
        cat_paises = dict(Aeropuerto.objects.values_list("codigo_iata", "pais"))
        
        # Agregar por país ISO
        paises_data = {}
        for d in por_ap:
            iata = d["aeropuerto_salida"]
            pais = cat_paises.get(iata, "")
            pais_iso = self.get_iso2(pais)
            if not pais_iso:
                continue
            
            if pais_iso not in paises_data:
                paises_data[pais_iso] = {"vuelos": 0, "pasajeros": 0}
            
            paises_data[pais_iso]["vuelos"] += d["vuelos"]
            paises_data[pais_iso]["pasajeros"] += (d["pasajeros"] or 0)
        
        # Formatear como lista
        res = [
            {"pais_iso": k, "vuelos": v["vuelos"], "pasajeros": v["pasajeros"]}
            for k, v in paises_data.items()
        ]
        res.sort(key=lambda x: x["pasajeros"], reverse=True)
        return Response(res)

    @action(detail=False, methods=["get"], url_path="matriz-paises")
    def matriz_paises(self, request):
        """
        Matriz origen-destino a nivel de PAÍS. Ideal para diagrama de Sankey.
        Retorna las top N rutas internacionales.
        """
        qs = _aplicar_filtros_base(VueloPNR.objects.all(), request)
        top = int(request.query_params.get("top", 50))
        
        por_ruta = list(
            qs.values("aeropuerto_salida", "aeropuerto_llegada")
            .annotate(vuelos=Count("id"), pasajeros=Sum("pasajeros"))
        )
        
        cat_paises = dict(Aeropuerto.objects.values_list("codigo_iata", "pais"))
        cat_nombres = dict(Aeropuerto.objects.values_list("codigo_iata", "nombre"))
        
        # Agrupar flujos por pares de países
        flujos = {}
        for d in por_ruta:
            p_origen = cat_paises.get(d["aeropuerto_salida"], "")
            p_destino = cat_paises.get(d["aeropuerto_llegada"], "")
            
            # Solo flujos donde conozcamos ambos países
            if not p_origen or not p_destino:
                continue
                
            par = (p_origen, p_destino)
            if par not in flujos:
                flujos[par] = {"vuelos": 0, "pasajeros": 0}
            
            flujos[par]["vuelos"] += d["vuelos"]
            flujos[par]["pasajeros"] += (d["pasajeros"] or 0)
            
        res = [
            {"origen_iso": k[0], "destino_iso": k[1], "vuelos": v["vuelos"], "pasajeros": v["pasajeros"]}
            for k, v in flujos.items()
        ]
        res.sort(key=lambda x: x["pasajeros"], reverse=True)
        return Response(res[:top])

    @action(detail=False, methods=["get"], url_path="heatmap-tiempo")
    def heatmap_tiempo(self, request):
        """
        Agrupa vuelos por día de la semana y por hora del día.
        Retorna una matriz [dia_semana, hora, vuelos, pasajeros].
        """
        qs = _aplicar_filtros_base(VueloPNR.objects.all(), request)
        
        datos = list(
            qs.extra(select={"hora": "EXTRACT(HOUR FROM hora_salida)"})
            .values("dia_semana", "hora")
            .annotate(vuelos=Count("id"), pasajeros=Sum("pasajeros"))
        )
        
        return Response([{
            "dia": d["dia_semana"],
            "hora": int(d["hora"]) if d["hora"] is not None else 0,
            "vuelos": d["vuelos"],
            "pasajeros": d["pasajeros"] or 0
        } for d in datos])
