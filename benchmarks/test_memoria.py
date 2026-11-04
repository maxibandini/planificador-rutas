"""Control de consumo de memoria con tracemalloc.

Cada prueba mide el pico de memoria Python de una operacion y falla si
supera en mas de un 20 % el valor de la linea base. tracemalloc cuenta
objetos Python, no la memoria total del proceso: por eso da casi el mismo
numero en Windows y en Linux con la misma version de Python, y sirve como
control reproducible.
"""

import json
from pathlib import Path

import pytest

from planificador import archivos
from planificador.algoritmos import a_estrella
from planificador.consultas import generar_consultas
from planificador.mediciones import con_memoria
from planificador.red import generar_red

LINEA_BASE = Path(__file__).with_name("linea_base.json")
REPORTE = Path("reportes/memoria.json")
TOLERANCIA = 0.20
medidos: dict[str, float] = {}


@pytest.fixture(scope="module", autouse=True)
def guardar_reporte():
    yield
    REPORTE.parent.mkdir(exist_ok=True)
    REPORTE.write_text(json.dumps(medidos, indent=2), encoding="utf-8")


def _controlar(nombre, funcion, *argumentos):
    _, _, pico = con_memoria(funcion, *argumentos)
    medidos[nombre] = round(pico / 1024, 1)
    base = json.loads(LINEA_BASE.read_text(encoding="utf-8"))["memoria_kib"]
    limite = base[nombre] * (1 + TOLERANCIA)
    assert medidos[nombre] <= limite, (
        f"{nombre}: {medidos[nombre]} KiB supera el limite de {limite:.0f} KiB"
    )


def test_memoria_a_estrella():
    red = generar_red(100)  # 10.000 nodos
    _controlar("a_estrella_10k_nodos", a_estrella, red, 0, red.nodos - 1)


def test_memoria_archivo_por_lotes(tmp_path):
    red = generar_red(40)
    entrada = tmp_path / "consultas.txt"
    archivos.escribir_consultas(entrada, generar_consultas(red, 5_000))
    _controlar(
        "archivo_5k_consultas",
        archivos.procesar_por_lotes,
        red,
        entrada,
        tmp_path / "out.txt",
    )
