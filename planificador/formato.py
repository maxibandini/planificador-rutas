"""Formato de las mediciones del informe.

El MILISEGUNDO es la unidad base: nada se muestra en microsegundos, para
que todas las tablas se lean en la misma escala. Los tiempos grandes se
muestran en segundos, minutos u horas.

Los decimales se ajustan a la magnitud: un acierto de cache ronda los
0,0015 ms y con dos decimales quedaria en 0,00.
"""

from __future__ import annotations

SEGUNDOS_POR_HORA = 3600
SEGUNDOS_POR_MINUTO = 60
BYTES_POR_MB = 1024 * 1024


def formato_tiempo(segundos: float) -> str:
    """Duracion legible, con el milisegundo como unidad minima.

    Args:
        segundos: Duracion en segundos.

    Returns:
        Texto con la unidad mas adecuada.

    Example:
        >>> formato_tiempo(7200)
        '2.0 h'
        >>> formato_tiempo(90)
        '1.5 min'
        >>> formato_tiempo(1.5)
        '1.50 s'
        >>> formato_tiempo(0.0123)
        '12.30 ms'
        >>> formato_tiempo(0.00005)
        '0.050 ms'
        >>> formato_tiempo(0.0000015)
        '0.0015 ms'
    """
    if segundos >= SEGUNDOS_POR_HORA:
        return f"{segundos / SEGUNDOS_POR_HORA:,.1f} h"
    if segundos >= SEGUNDOS_POR_MINUTO:
        return f"{segundos / SEGUNDOS_POR_MINUTO:,.1f} min"
    if segundos >= 1:
        return f"{segundos:,.2f} s"

    milisegundos = segundos * 1e3
    if milisegundos >= 1:
        return f"{milisegundos:,.2f} ms"
    if milisegundos >= 0.01:
        return f"{milisegundos:,.3f} ms"
    return f"{milisegundos:,.4f} ms"


def formato_memoria(cantidad_bytes: float) -> str:
    """Cantidad de bytes expresada en megabytes.

    Args:
        cantidad_bytes: Tamanio en bytes.

    Returns:
        Texto en MB con un decimal.

    Example:
        >>> formato_memoria(3 * 1024 * 1024)
        '3.0 MB'
    """
    return f"{cantidad_bytes / BYTES_POR_MB:,.1f} MB"


if __name__ == "__main__":
    # Ejecutar "python -m planificador.formato" corre los ejemplos de
    # arriba como pruebas (doctest). Si no imprime nada, pasaron todas.
    import doctest

    doctest.testmod()
