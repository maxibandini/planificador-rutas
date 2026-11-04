"""Pruebas unitarias del grafo."""

import unittest

import pytest

from planificador.red import Red, generar_red, red_argentina


def test_grilla_tiene_lado_al_cuadrado_nodos():
    red = generar_red(10)
    assert red.nodos == 100
    # 2 * lado * (lado - 1) tramos de grilla, mas las autopistas
    assert red.aristas >= 2 * 10 * 9


def test_mismo_mapa_con_la_misma_semilla():
    a, b = generar_red(12, semilla=3), generar_red(12, semilla=3)
    assert a.adyacencia == b.adyacencia


def test_heuristica_admisible_en_todos_los_tramos(grilla):
    # A* solo es optimo si h nunca sobreestima: peso >= linea recta
    for nodo, vecinos in grilla.adyacencia.items():
        for vecino, peso in vecinos:
            assert peso >= grilla.distancia_recta(nodo, vecino)


def test_cortar_arista_la_saca_en_ambos_sentidos(red_ar):
    red_ar.cortar_arista("Bahia Blanca", "Buenos Aires")
    with pytest.raises(ValueError):
        red_ar.peso("Bahia Blanca", "Buenos Aires")
    with pytest.raises(ValueError):
        red_ar.peso("Buenos Aires", "Bahia Blanca")


@pytest.mark.parametrize("ruta", [None, [], ["Salta"]])
def test_costo_de_rutas_triviales_es_cero(red_ar, ruta):
    assert red_ar.costo_de_ruta(ruta) == 0.0


def test_costo_de_ruta_con_tramo_inexistente(red_ar):
    with pytest.raises(ValueError, match="tramo inexistente"):
        red_ar.costo_de_ruta(["Ushuaia", "Salta"])


def test_contains(red_ar):
    assert "Cordoba" in red_ar
    assert "Atlantida" not in red_ar


# pytest tambien corre tests escritos con unittest.
class TestRedConUnittest(unittest.TestCase):
    """pytest tambien corre tests escritos con unittest (compatibilidad)."""

    def setUp(self):
        self.red = Red("triangulo")
        for nodo, (x, y) in {"A": (0, 0), "B": (3, 0), "C": (3, 4)}.items():
            self.red.agregar_nodo(nodo, x, y)
        self.red.agregar_arista("A", "B", 3.0)
        self.red.agregar_arista("B", "C", 4.0)

    def test_distancia_recta(self):
        self.assertAlmostEqual(self.red.distancia_recta("A", "C"), 5.0)

    def test_costo_de_ruta(self):
        self.assertEqual(self.red.costo_de_ruta(["A", "B", "C"]), 7.0)

    def test_argentina_tiene_24_ciudades(self):
        self.assertEqual(red_argentina().nodos, 24)
