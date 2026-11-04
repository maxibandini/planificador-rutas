"""Fixtures compartidas por los tests (pytest las inyecta por nombre)."""

from __future__ import annotations

import pytest

from planificador.api import crear_app
from planificador.red import Red, generar_red, red_argentina


@pytest.fixture
def red_ar() -> Red:
    """Mapa argentino nuevo para cada test (los cortes no se filtran)."""
    return red_argentina()


@pytest.fixture
def grilla() -> Red:
    """Grilla chica: 225 nodos, rapida pero con caminos alternativos."""
    return generar_red(15, semilla=11)


@pytest.fixture
def red_desconectada() -> Red:
    """Dos islas sin tramo entre ellas."""
    red = Red("islas")
    for nodo, x in (("A", 0), ("B", 1), ("C", 10), ("D", 11)):
        red.agregar_nodo(nodo, x, 0)
    red.agregar_arista("A", "B", 1.0)
    red.agregar_arista("C", "D", 1.0)
    return red


@pytest.fixture
def cliente():
    """Cliente de pruebas de Flask sobre una aplicacion limpia."""
    app = crear_app()
    app.config["TESTING"] = True
    return app.test_client()
