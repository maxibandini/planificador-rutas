"""Pruebas de formato y de los scripts de punta a punta."""

import subprocess
import sys
from pathlib import Path

import pytest

from planificador import consola, mediciones
from planificador.formato import formato_memoria, formato_tiempo

RAIZ = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("segundos", "esperado"),
    [
        (3600, "1.0 h"),
        (59.99, "59.99 s"),
        (60, "1.0 min"),
        (1, "1.00 s"),
        (0.001, "1.00 ms"),
        (0.00001, "0.010 ms"),
        (0.000009, "0.0090 ms"),
    ],
)
def test_limites_de_formato_tiempo(segundos, esperado):
    assert formato_tiempo(segundos) == esperado


def test_formato_memoria():
    assert formato_memoria(0) == "0.0 MB"


# Funcional: corre main.py como lo haria un usuario.
def test_main_de_punta_a_punta():
    # Prueba funcional: corre el script como lo haria un usuario.
    salida = subprocess.run(
        [sys.executable, "main.py", "Rosario", "Santa Fe"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    assert "RUTA OBSOLETA" in salida
    assert "ruta recalculada y valida" in salida


def test_main_ciudad_desconocida_sale_con_error():
    proceso = subprocess.run(
        [sys.executable, "main.py", "Atlantida"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proceso.returncode == 1
    assert "No conozco la ciudad" in proceso.stdout


def test_mejor_de_devuelve_el_minimo(monkeypatch):
    # perf_counter falso: corridas de 3, 1 y 2 segundos
    tiempos = iter([0, 3, 10, 11, 20, 22])
    monkeypatch.setattr(mediciones.time, "perf_counter", lambda: next(tiempos))
    resultado, segundos = mediciones.mejor_de(3, lambda: "ok")
    assert (resultado, segundos) == ("ok", 1)


def test_con_memoria_mide_un_pico_positivo():
    _, segundos, pico = mediciones.con_memoria(lambda: [0] * 100_000)
    assert segundos >= 0
    assert pico > 100_000


def test_mostrar_ruta_parte_las_lineas_largas(capsys):
    consola.mostrar_ruta([f"Ciudad numero {numero}" for numero in range(8)])
    lineas = capsys.readouterr().out.splitlines()
    assert len(lineas) > 1
    assert all(len(linea) <= 68 for linea in lineas)


def test_encabezado_y_separador(capsys):
    consola.encabezado("UNO", "DOS")
    consola.separador(10)
    salida = capsys.readouterr().out.splitlines()
    assert salida == ["=" * 76, "  UNO", "  DOS", "=" * 76, "  " + "-" * 10]
