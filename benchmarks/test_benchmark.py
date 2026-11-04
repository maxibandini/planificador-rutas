"""Benchmarks de operaciones representativas (pytest-benchmark).

Los tiempos absolutos cambian de una maquina a otra (la notebook, la PC de
escritorio y el runner de GitHub no se parecen). Por eso, ademas de las
operaciones del proyecto, se mide ``test_referencia``: un trabajo fijo en
Python puro. ``controles.py`` divide cada tiempo por el de la referencia y
compara ese cociente con la linea base (``linea_base.json``).

    pytest benchmarks/test_benchmark.py --benchmark-only
"""

from planificador import archivos
from planificador.algoritmos import a_estrella, dijkstra_heap
from planificador.cache import CacheDeRutas
from planificador.consultas import generar_consultas
from planificador.red import generar_red

RED = generar_red(60)  # 3.600 nodos
CONSULTAS = generar_consultas(RED, 20, semilla=3)


def _referencia():
    return sum(i * i for i in range(200_000))


def test_referencia(benchmark):
    benchmark(_referencia)


def test_a_estrella(benchmark):
    benchmark(lambda: [a_estrella(RED, o, d) for o, d in CONSULTAS])


def test_dijkstra_heap(benchmark):
    benchmark(lambda: [dijkstra_heap(RED, o, d) for o, d in CONSULTAS])


def test_cache_acierto(benchmark):
    cache = CacheDeRutas(RED)
    cache.consultar(0, RED.nodos - 1)
    benchmark(cache.consultar, 0, RED.nodos - 1)


def test_procesar_archivo_por_lotes(benchmark, tmp_path):
    entrada = tmp_path / "consultas.txt"
    archivos.escribir_consultas(
        entrada, generar_consultas(RED, 2_000, semilla=4)
    )
    benchmark(archivos.procesar_por_lotes, RED, entrada, tmp_path / "out.txt")
