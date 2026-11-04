"""CPython contra PyPy (compilador JIT) con el mismo codigo.

PyPy es otra implementacion de Python que compila a codigo maquina en
tiempo de ejecucion las partes que mas se repiten (JIT). No hay que cambiar
el programa: las cargas que se miden usan solo la biblioteca estandar.

Uso::

    python compiladores.py --comparar C:/ruta/a/pypy.exe
    python compiladores.py            (solo mide con el interprete actual)

Cada interprete corre en un proceso nuevo y mide cada carga tres veces:
la primera incluye el "calentamiento" del JIT; la mejor muestra el regimen
estable. La diferencia entre las dos es lo que dicen las diapositivas:
PyPy rinde en programas largos con muchos bucles, no en los cortos.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from planificador import archivos
from planificador.algoritmos import a_estrella, dijkstra_lista
from planificador.consultas import generar_consultas
from planificador.mediciones import cronometrar, mejor_de
from planificador.red import generar_red, red_argentina

SALIDA = Path(__file__).parent / "resultados" / "compiladores.json"
REPETICIONES = 3


def _a_estrella_en_grilla() -> None:
    """A* sobre la grilla grande: dicts, heap y muchas llamadas."""
    red = generar_red(110)
    for origen, destino in generar_consultas(red, 300, semilla=3):
        a_estrella(red, origen, destino)


def _baseline_en_grilla() -> None:
    """Baseline O(V^2): un bucle que PyPy puede compilar."""
    red = generar_red(50)
    for origen, destino in generar_consultas(red, 3, semilla=3):
        dijkstra_lista(red, origen, destino)


def _tuberia_de_archivos() -> None:
    """Tuberia V1: E/S, parseo de texto y A* sobre el mapa chico."""
    red = red_argentina()
    with tempfile.TemporaryDirectory(prefix="pef_jit_") as carpeta:
        entrada = Path(carpeta) / "consultas.txt"
        archivos.escribir_consultas(
            entrada, generar_consultas(red, 100_000, 500, semilla=21)
        )
        archivos.procesar_streaming(red, entrada, Path(carpeta) / "r.txt")


CARGAS_DE_TRABAJO = {
    "A*, 300 consultas, 12.100 nodos": _a_estrella_en_grilla,
    "Dijkstra lista, 3 consultas, 2.500 nodos": _baseline_en_grilla,
    "Tuberia de archivos, 100.000 consultas": _tuberia_de_archivos,
}


# [EXPO 2] Compilador JIT: PyPy contra CPython con el mismo codigo.
def medir_interprete_actual() -> dict:
    """Mide cada carga con el interprete que esta corriendo este script.

    Returns:
        Interprete, version y, por carga, la primera y la mejor corrida.
    """
    resultados = {}
    for nombre, carga in CARGAS_DE_TRABAJO.items():
        # la primera corrida incluye el calentamiento del JIT
        tiempos = [cronometrar(carga)[1] for _ in range(REPETICIONES)]
        resultados[nombre] = {"primera": tiempos[0], "mejor": min(tiempos)}
    return {
        "interprete": platform.python_implementation(),
        "version": platform.python_version(),
        "cargas": resultados,
    }


def medir_en(ejecutable: str) -> dict:
    """Corre este script con otro interprete y lee su resultado.

    Args:
        ejecutable: Ruta al interprete (``python.exe``, ``pypy.exe``).

    Returns:
        El diccionario que devuelve :func:`medir_interprete_actual`.
    """
    # Bandit B603: el interprete lo indica quien corre el script.
    salida = subprocess.run(  # nosec B603
        [ejecutable, str(Path(__file__).resolve()), "--json"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parent,
    ).stdout
    return json.loads(salida)


def arranque(ejecutable: str) -> float:
    """Segundos que tarda el interprete en arrancar y salir sin hacer nada."""

    def correr_vacio() -> None:
        subprocess.run([ejecutable, "-c", "pass"], check=True)  # nosec B603

    return mejor_de(REPETICIONES, correr_vacio)[1]


def imprimir(cpython: dict, pypy: dict) -> None:
    """Tabla comparativa."""
    print(
        f"  {'carga':<42}{'CPython':>9}{'PyPy 1ra':>10}"
        f"{'PyPy mejor':>11}{'mejora':>8}"
    )
    print("  " + "-" * 80)
    for nombre in CARGAS_DE_TRABAJO:
        base = cpython["cargas"][nombre]["mejor"]
        primera = pypy["cargas"][nombre]["primera"]
        mejor = pypy["cargas"][nombre]["mejor"]
        print(
            f"  {nombre:<42}{base:>8.2f}s{primera:>9.2f}s"
            f"{mejor:>10.2f}s{base / mejor:>7.1f}x"
        )
    print("  " + "-" * 80)
    print(
        f"  Arranque del interprete: CPython {cpython['arranque'] * 1e3:.0f}"
        f" ms, PyPy {pypy['arranque'] * 1e3:.0f} ms."
    )


def main() -> None:
    """Punto de entrada."""
    parser = argparse.ArgumentParser(description="CPython contra PyPy")
    parser.add_argument(
        "--comparar", metavar="RUTA_PYPY", help="interprete a comparar"
    )
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    argumentos = parser.parse_args()
    if argumentos.json or not argumentos.comparar:
        print(json.dumps(medir_interprete_actual(), indent=2))
        return

    ruta_pypy = argumentos.comparar
    if not Path(ruta_pypy).is_file():
        print(f"No encuentro el interprete {ruta_pypy}")
        sys.exit(1)
    print("Midiendo con CPython...", flush=True)
    cpython = medir_en(sys.executable)
    cpython["arranque"] = arranque(sys.executable)
    print("Midiendo con PyPy...", flush=True)
    pypy = medir_en(ruta_pypy)
    pypy["arranque"] = arranque(ruta_pypy)
    print(
        f"\n  CPython {cpython['version']}  contra  "
        f"PyPy (Python {pypy['version']})\n"
    )
    imprimir(cpython, pypy)
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(
        json.dumps({"cpython": cpython, "pypy": pypy}, indent=2),
        encoding="utf-8",
    )
    print(f"\n  Guardado en resultados/{SALIDA.name}")


if __name__ == "__main__":
    main()
