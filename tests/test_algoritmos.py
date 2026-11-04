"""Pruebas de los algoritmos de busqueda."""

import random
from math import inf

import pytest

from planificador.algoritmos import (
    ALGORITMOS,
    a_estrella,
    bfs,
    dijkstra_heap,
    dijkstra_lista,
)

OPTIMOS = [dijkstra_lista, dijkstra_heap, a_estrella]


@pytest.mark.parametrize("semilla", range(5))
def test_los_tres_optimos_dan_el_mismo_costo(grilla, semilla):
    rng = random.Random(semilla)
    nodos = list(grilla.adyacencia)
    for _ in range(15):
        origen, destino = rng.sample(nodos, 2)
        costos = [alg(grilla, origen, destino).costo for alg in OPTIMOS]
        assert costos == pytest.approx([costos[0]] * 3)


@pytest.mark.parametrize("algoritmo", list(ALGORITMOS.values()))
def test_el_costo_informado_coincide_con_la_ruta(red_ar, algoritmo):
    resultado = algoritmo(red_ar, "Ushuaia", "Salta")
    assert resultado.ruta[0] == "Ushuaia"
    assert resultado.ruta[-1] == "Salta"
    assert red_ar.costo_de_ruta(resultado.ruta) == pytest.approx(
        resultado.costo
    )


def test_bfs_minimiza_tramos_y_no_distancia(red_ar):
    rapido = bfs(red_ar, "Ushuaia", "Salta")
    optimo = a_estrella(red_ar, "Ushuaia", "Salta")
    assert len(rapido.ruta) < len(optimo.ruta)
    assert rapido.costo > optimo.costo


def test_a_estrella_explora_menos_que_dijkstra(grilla):
    nodos = list(grilla.adyacencia)
    estrella = sum(a_estrella(grilla, nodos[0], d).explorados for d in nodos)
    dijkstra = sum(
        dijkstra_heap(grilla, nodos[0], d).explorados for d in nodos
    )
    assert estrella < dijkstra


@pytest.mark.parametrize("algoritmo", list(ALGORITMOS.values()))
def test_origen_igual_destino(red_ar, algoritmo):
    resultado = algoritmo(red_ar, "Salta", "Salta")
    assert resultado.ruta == ["Salta"]
    assert resultado.costo == 0.0


@pytest.mark.parametrize("algoritmo", list(ALGORITMOS.values()))
def test_sin_camino_devuelve_none_e_infinito(red_desconectada, algoritmo):
    resultado = algoritmo(red_desconectada, "A", "D")
    assert resultado.ruta is None
    assert resultado.costo == inf


# [EXPO 9] Regresion: el refactor no cambio la ruta del P1.
def test_regresion_ruta_conocida(red_ar):
    # Prueba de regresion: la refactorizacion no cambio el resultado del
    # primer parcial (misma ruta, mismo costo, mismos nodos explorados).
    resultado = a_estrella(red_ar, "Ushuaia", "Salta")
    assert resultado.ruta == [
        "Ushuaia", "Trelew", "Bahia Blanca", "Buenos Aires", "Parana",
        "Santa Fe", "Cordoba", "Tucuman", "Salta",
    ]  # fmt: skip
    assert round(resultado.costo) == 4819
    assert resultado.explorados == 17
