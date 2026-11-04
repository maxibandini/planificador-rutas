"""Pruebas de rendimiento con timeit.

Una prueba unitaria verifica que el resultado sea correcto; estas
verifican que una optimizacion siga siendo una optimizacion. Comparan
relaciones (A mas rapido que B) y no tiempos absolutos, para no depender
del equipo. Se pueden saltear con ``pytest -m "not rendimiento"``.
"""

import timeit

import pytest

from planificador import archivos
from planificador.algoritmos import a_estrella, dijkstra_heap, dijkstra_lista
from planificador.cache import CacheDeRutas
from planificador.consultas import generar_consultas
from planificador.mediciones import con_memoria
from planificador.red import generar_red

pytestmark = pytest.mark.rendimiento


@pytest.fixture(scope="module")
def red_mediana():
    return generar_red(40)


def _mejor_tiempo(funcion, repeticiones=3):
    return min(timeit.repeat(funcion, number=1, repeat=repeticiones))


# [EXPO 9] Pruebas de rendimiento con timeit.
def test_heap_mas_rapido_que_lista(red_mediana):
    consultas = generar_consultas(red_mediana, 5, semilla=8)

    def correr(algoritmo):
        return lambda: [algoritmo(red_mediana, o, d) for o, d in consultas]

    assert _mejor_tiempo(correr(dijkstra_heap)) * 5 < _mejor_tiempo(
        correr(dijkstra_lista)
    )


def test_a_estrella_no_mas_lento_que_dijkstra_heap(red_mediana):
    consultas = generar_consultas(red_mediana, 30, semilla=9)

    def correr(algoritmo):
        return lambda: [algoritmo(red_mediana, o, d) for o, d in consultas]

    assert _mejor_tiempo(correr(a_estrella)) < _mejor_tiempo(
        correr(dijkstra_heap)
    )


def test_acierto_de_cache_mucho_mas_rapido(red_mediana):
    cache = CacheDeRutas(red_mediana)
    cache.consultar(0, red_mediana.nodos - 1)
    acierto = _mejor_tiempo(lambda: cache.consultar(0, red_mediana.nodos - 1))
    calculo = _mejor_tiempo(
        lambda: a_estrella(red_mediana, 0, red_mediana.nodos - 1)
    )
    assert acierto * 50 < calculo


def test_streaming_usa_menos_memoria_que_readlines(tmp_path, red_mediana):
    ruta = tmp_path / "consultas.txt"
    archivos.escribir_consultas(
        ruta, generar_consultas(red_mediana, 50_000, semilla=1)
    )
    _, _, pico_todo = con_memoria(archivos.leer_todo, ruta)
    _, _, pico_streaming = con_memoria(
        lambda r: sum(1 for _ in archivos.leer_consultas(r)), ruta
    )
    assert pico_streaming * 20 < pico_todo


def test_buffer_mas_rapido_que_abrir_por_linea(tmp_path):
    lineas = ["Ushuaia;Salta;4818.788;9\n"] * 2000
    abrir = _mejor_tiempo(
        lambda: archivos.escribir_abriendo_por_linea(tmp_path / "a", lineas),
        repeticiones=1,
    )
    buffer = _mejor_tiempo(
        lambda: archivos.escribir_por_lotes(tmp_path / "b", lineas)
    )
    assert buffer * 20 < abrir
