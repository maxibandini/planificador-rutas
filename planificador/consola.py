"""Impresion por consola compartida por los scripts.

En el primer parcial ``titulo`` estaba copiada en ``main.py``, ``banco.py``
y ``perfilado.py``. Separar la presentacion de los calculos tambien deja
las funciones de medicion faciles de probar.
"""

from __future__ import annotations

from collections.abc import Sequence

ANCHO = 76


# [EXPO 1] Antes estaba copiada en main.py, banco.py y perfilado.py.
def titulo(texto: str) -> None:
    """Imprime un titulo de seccion entre dos lineas.

    Args:
        texto: Texto del titulo.

    Example:
        >>> titulo("PRUEBA")  # doctest: +ELLIPSIS
        <BLANKLINE>
        ======...======
          PRUEBA
        ======...======
    """
    print()
    encabezado(texto)


def encabezado(*lineas: str) -> None:
    """Imprime el encabezado de un script, sin linea en blanco previa.

    Args:
        *lineas: Lineas de texto del encabezado.
    """
    print("=" * ANCHO)
    for linea in lineas:
        print(" ", linea)
    print("=" * ANCHO)


def separador(ancho: int = ANCHO - 6) -> None:
    """Imprime una linea de guiones con la sangria de las tablas.

    Args:
        ancho: Cantidad de guiones.
    """
    print("  " + "-" * ancho)


def mostrar_ruta(ruta: Sequence[object], ancho: int = 68) -> None:
    """Imprime una ruta, partida en varias lineas si no entra en una.

    Args:
        ruta: Nodos de la ruta, en orden.
        ancho: Largo maximo de cada linea.

    Example:
        >>> mostrar_ruta(["Ushuaia", "Trelew", "Salta"])
            Ushuaia -> Trelew -> Salta
    """
    linea = "    "
    for posicion, nodo in enumerate(ruta):
        pieza = str(nodo) if posicion == 0 else f" -> {nodo}"
        if len(linea) + len(pieza) > ancho:
            print(linea)
            linea = "      " + pieza.lstrip(" ->")
        else:
            linea += pieza
    print(linea)
