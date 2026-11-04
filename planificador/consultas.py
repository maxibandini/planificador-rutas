"""Generacion reproducible de lotes de consultas ``(origen, destino)``.

En el primer parcial habia dos funciones casi iguales: ``generar_lote`` en
``banco.py`` y ``generar_consultas`` en ``concurrencia.py``. Ahora hay una.
"""

from __future__ import annotations

import random

from planificador.red import Nodo, Red

Consulta = tuple[Nodo, Nodo]


# [EXPO 1] Reemplaza a generar_lote() y generar_consultas() del P1.
def generar_consultas(
    red: Red,
    cantidad: int,
    pares_distintos: int | None = None,
    semilla: int = 5,
) -> list[Consulta]:
    """Genera consultas al azar, opcionalmente con repeticiones.

    Un servicio real recibe muchas veces las mismas consultas. Con
    ``pares_distintos`` se sortean primero esos pares y despues cada
    consulta elige uno de ellos, de modo que la cache tenga que hacer.

    Args:
        red: Red de donde salen los nodos.
        cantidad: Cantidad de consultas a generar.
        pares_distintos: Cantidad de pares diferentes. Si es ``None`` cada
            consulta es un par independiente.
        semilla: Semilla del generador, para repetir el mismo lote.

    Returns:
        Lista de consultas ``(origen, destino)``.

    Example:
        >>> from planificador.red import red_argentina
        >>> lote = generar_consultas(red_argentina(), 100, pares_distintos=5)
        >>> len(lote), len(set(lote)) <= 5
        (100, True)
    """
    # random alcanza: es una simulacion, no un uso criptografico.
    rng = random.Random(semilla)  # nosec B311
    nodos = list(red.adyacencia)
    if pares_distintos is None:
        return [
            (rng.choice(nodos), rng.choice(nodos)) for _ in range(cantidad)
        ]
    pares = [
        (rng.choice(nodos), rng.choice(nodos)) for _ in range(pares_distintos)
    ]
    return [pares[rng.randrange(pares_distintos)] for _ in range(cantidad)]
