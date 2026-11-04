"""Genera trafico contra la API para observarla con el APM.

Uso (con ``python servidor.py --telemetria`` corriendo en otra terminal)::

    python carga_api.py [--peticiones 400] [--hilos 8] [--url URL]

Hace consultas al azar entre las 24 ciudades (muchas se repiten, asi que la
cache trabaja), corta un tramo a mitad de camino y al final resume las
latencias por percentil, como lo haria un panel de APM.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from planificador.consultas import generar_consultas
from planificador.red import red_argentina

URL_POR_DEFECTO = "http://127.0.0.1:8000"
TIEMPO_MAXIMO = 10
PARES_DISTINTOS = 60


def pedir(url: str, datos: dict | None = None) -> tuple[dict, float]:
    """Hace una peticion HTTP y mide cuanto tarda.

    Args:
        url: URL completa.
        datos: Si se indica, se envia como JSON con POST.

    Returns:
        Tupla ``(respuesta_json, segundos)``.
    """
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    peticion = urllib.request.Request(
        url, data=cuerpo, headers={"Content-Type": "application/json"}
    )
    inicio = time.perf_counter()
    # Bandit B310: la URL es la de la API local, la elige quien corre esto.
    abierta = urllib.request.urlopen(  # nosec B310
        peticion, timeout=TIEMPO_MAXIMO
    )
    with abierta as respuesta:
        contenido = json.loads(respuesta.read())
    return contenido, time.perf_counter() - inicio


def consultar_ruta(url_base: str, par: tuple[str, str]) -> tuple[bool, float]:
    """Pide una ruta y devuelve si vino de la cache y la latencia."""
    parametros = urllib.parse.urlencode({"origen": par[0], "destino": par[1]})
    datos, segundos = pedir(f"{url_base}/api/ruta?{parametros}")
    return datos["desde_cache"], segundos


def percentil(valores: list[float], porcentaje: float) -> float:
    """Percentil por el metodo del rango mas cercano.

    Example:
        >>> percentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95)
        10
    """
    ordenados = sorted(valores)
    indice = max(0, math.ceil(porcentaje / 100 * len(ordenados)) - 1)
    return ordenados[indice]


def imprimir_latencias(resultados: list[tuple[bool, float]]) -> None:
    """Percentiles de latencia, separando aciertos de cache y calculos."""
    aciertos = [s * 1e3 for desde_cache, s in resultados if desde_cache]
    calculos = [s * 1e3 for desde_cache, s in resultados if not desde_cache]
    print(f"  {'latencia (ms)':<22}{'p50':>8}{'p95':>8}{'p99':>8}")
    for nombre, valores in (
        ("todas", aciertos + calculos),
        ("desde la cache", aciertos),
        ("calculadas (A*)", calculos),
    ):
        if valores:
            print(
                f"  {nombre:<22}{statistics.median(valores):>8.2f}"
                f"{percentil(valores, 95):>8.2f}{percentil(valores, 99):>8.2f}"
            )


# Genera trafico para ver las trazas en Jaeger.
def main() -> None:
    """Punto de entrada."""
    parser = argparse.ArgumentParser(description="Carga para la API")
    parser.add_argument("--peticiones", type=int, default=400)
    parser.add_argument("--hilos", type=int, default=8)
    parser.add_argument("--url", default=URL_POR_DEFECTO)
    argumentos = parser.parse_args()
    url = argumentos.url.rstrip("/")

    try:
        pedir(f"{url}/api/reiniciar", {})
    except urllib.error.URLError:
        print(f"No hay servidor en {url}. Primero: python servidor.py")
        sys.exit(1)

    lote = generar_consultas(
        red_argentina(), argumentos.peticiones, PARES_DISTINTOS, semilla=7
    )
    mitad = len(lote) // 2
    consultar = partial(consultar_ruta, url)
    with ThreadPoolExecutor(max_workers=argumentos.hilos) as ejecutor:
        resultados = list(ejecutor.map(consultar, lote[:mitad]))
        corte, _ = pedir(
            f"{url}/api/tramos/cortar",
            {"a": "Bahia Blanca", "b": "Buenos Aires"},
        )
        resultados += ejecutor.map(consultar, lote[mitad:])

    aciertos = sum(1 for desde_cache, _ in resultados if desde_cache)
    print(f"Peticiones: {len(resultados)}  ({argumentos.hilos} hilos)")
    print(f"Corte de tramo a mitad de camino: {corte['invalidadas']} rutas")
    print(f"  invalidadas. Aciertos de cache: {aciertos}")
    print()
    imprimir_latencias(resultados)
    print()
    print("Trazas en Jaeger: http://localhost:16686 (servicio")
    print("planificador-rutas). La latencia incluye HTTP y el lock.")


if __name__ == "__main__":
    main()
