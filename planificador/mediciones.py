"""Cronometro y medicion de memoria compartidos por todos los bancos.

En el primer parcial ``cronometrar`` estaba copiada en ``banco.py`` y en
``concurrencia.py``. Ahora vive en un solo lugar.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


# [EXPO 1] Antes estaba copiada en banco.py y concurrencia.py.
def cronometrar(
    funcion: Callable[..., Any], *argumentos: Any
) -> tuple[Any, float]:
    """Ejecuta una funcion y mide cuanto tarda.

    Usa ``time.perf_counter``, el reloj de mayor resolucion disponible.

    Args:
        funcion: Funcion a ejecutar.
        *argumentos: Argumentos posicionales para la funcion.

    Returns:
        Tupla ``(resultado, segundos)``.

    Example:
        >>> resultado, segundos = cronometrar(sum, range(10))
        >>> resultado, segundos >= 0
        (45, True)
    """
    inicio = time.perf_counter()
    resultado = funcion(*argumentos)
    return resultado, time.perf_counter() - inicio


def mejor_de(
    repeticiones: int, funcion: Callable[..., Any], *argumentos: Any
) -> tuple[Any, float]:
    """Ejecuta varias veces y se queda con el menor tiempo, como ``timeit``.

    El ruido (otros procesos, el sistema operativo moviendo el hilo a un
    nucleo mas lento, frecuencia variable) solo puede sumar tiempo, nunca
    restarlo: el minimo es la mejor estimacion del costo real. En el
    i7-14700K del grupo, con nucleos P y E, la misma corrida variaba
    hasta 1,9x segun el nucleo que eligiera Windows.

    Args:
        repeticiones: Cantidad de ejecuciones, al menos 1.
        funcion: Funcion a ejecutar.
        *argumentos: Argumentos posicionales para la funcion.

    Returns:
        Tupla ``(resultado_de_la_ultima, menor_tiempo_en_segundos)``.
    """
    mejor = float("inf")
    resultado = None
    for _ in range(max(1, repeticiones)):
        resultado, segundos = cronometrar(funcion, *argumentos)
        mejor = min(mejor, segundos)
    return resultado, mejor


def con_memoria(
    funcion: Callable[..., Any], *argumentos: Any
) -> tuple[Any, float, int]:
    """Ejecuta una funcion y mide tiempo y pico de memoria Python.

    ``tracemalloc`` registra las asignaciones de objetos Python del proceso
    actual. No incluye la memoria total del interprete ni la de procesos
    hijos: sirve para comparar versiones, no para medir el consumo total.

    Args:
        funcion: Funcion a ejecutar.
        *argumentos: Argumentos posicionales para la funcion.

    Returns:
        Tupla ``(resultado, segundos, pico_en_bytes)``.
    """
    # Import perezoso: PyPy no implementa tracemalloc, y asi el resto del
    # paquete se puede importar y medir tambien con PyPy.
    import tracemalloc  # pylint: disable=import-outside-toplevel

    tracemalloc.start()
    try:
        resultado, segundos = cronometrar(funcion, *argumentos)
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return resultado, segundos, pico


def guardar_json(ruta: Path, datos: dict[str, Any]) -> None:
    """Guarda mediciones en JSON y avisa en que archivo quedaron.

    Args:
        ruta: Archivo de destino. La carpeta se crea si hace falta.
        datos: Mediciones serializables.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    print()
    print(f"  Mediciones guardadas en {ruta.parent.name}/{ruta.name}")
    print()
