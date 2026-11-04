"""Contratos de complejidad: lo medido tiene que coincidir con la teoria.

Tiempo: se mide cada algoritmo en grillas de tamanio creciente y se ajusta
una recta en escala log-log. Si el tiempo crece como c * V**k, la pendiente
de esa recta es k. La velocidad de la maquina solo cambia c, no k: por eso
este control da lo mismo en la notebook, en la PC y en el runner del CI.

Espacio: la lectura por streaming tiene que usar la misma memoria con un
archivo 10 veces mas grande (O(1)); la lectura con readlines, no (O(n)).
"""

import json
import math
import statistics
import timeit
import tracemalloc
from pathlib import Path

import pytest

from planificador import archivos
from planificador.algoritmos import dijkstra_heap, dijkstra_lista
from planificador.consultas import generar_consultas
from planificador.red import generar_red

LADOS = (20, 28, 40, 56)  # de 400 a 3.136 nodos
REPORTE = Path("reportes/complejidad.json")
medidos: dict[str, float] = {}


@pytest.fixture(scope="module", autouse=True)
def guardar_reporte():
    yield
    REPORTE.parent.mkdir(exist_ok=True)
    REPORTE.write_text(json.dumps(medidos, indent=2), encoding="utf-8")


def exponente(algoritmo):
    """Pendiente log-log del tiempo de ``algoritmo`` contra los nodos."""
    nodos, tiempos = [], []
    for lado in LADOS:
        red = generar_red(lado)
        cronometro = timeit.Timer(
            lambda red=red: algoritmo(red, 0, red.nodos - 1)
        )
        # autorange elige cuantas veces repetir para que cada medicion dure
        # al menos 0,2 s: los tamanios chicos no quedan a merced del ruido
        # de un runner compartido. Despues, el minimo de 3 mediciones.
        veces, _ = cronometro.autorange()
        tiempo = min(cronometro.repeat(number=veces, repeat=3)) / veces
        nodos.append(math.log(red.nodos))
        tiempos.append(math.log(tiempo))
    return statistics.linear_regression(nodos, tiempos).slope


def test_dijkstra_con_lista_es_cuadratico():
    k = medidos["dijkstra_lista"] = round(exponente(dijkstra_lista), 2)
    assert 1.7 <= k <= 2.3, f"se esperaba O(V^2) (k ~ 2) y se midio k = {k}"


def test_dijkstra_con_heap_es_casi_lineal():
    k = medidos["dijkstra_heap"] = round(exponente(dijkstra_heap), 2)
    assert k <= 1.4, f"se esperaba O(V log V) (k ~ 1,1) y se midio k = {k}"


def _pico(funcion):
    tracemalloc.start()
    try:
        funcion()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_streaming_usa_memoria_constante(tmp_path):
    red = generar_red(20)
    picos = {}
    for lineas in (5_000, 50_000):
        ruta = tmp_path / f"consultas_{lineas}.txt"
        archivos.escribir_consultas(ruta, generar_consultas(red, lineas))
        picos[lineas] = (
            _pico(lambda r=ruta: sum(1 for _ in archivos.leer_consultas(r))),
            _pico(lambda r=ruta: len(archivos.leer_todo(r))),
        )
    streaming = picos[50_000][0] / picos[5_000][0]
    readlines = picos[50_000][1] / picos[5_000][1]
    medidos["memoria_streaming_x10"] = round(streaming, 2)
    medidos["memoria_readlines_x10"] = round(readlines, 2)
    assert streaming < 1.5, f"streaming crecio {streaming:.1f}x con 10x datos"
    assert readlines > 5, "el control no distingue O(1) de O(n)"
