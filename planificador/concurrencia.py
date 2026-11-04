"""Resolver muchas consultas a la vez: secuencial, hilos y procesos.

Las consultas son independientes y solo leen el mapa, asi que no hace
falta lock. Es trabajo de CPU: por el GIL los hilos quedan cerca del
tiempo secuencial, y los procesos aprovechan varios nucleos cuando el lote
amortiza su costo fijo de arranque.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

from planificador.algoritmos import Algoritmo, Resultado, a_estrella
from planificador.consultas import Consulta, generar_consultas
from planificador.mediciones import cronometrar
from planificador.red import Red

NUCLEOS = min(8, os.cpu_count() or 4)
"""Trabajadores por defecto.

Ocho alcanzan para mostrar el paralelismo sin crear decenas de procesos en
equipos grandes, y coinciden con la corrida del primer parcial.
"""

ENVIOS_POR_TRABAJADOR = 4  # chunksize: unos 4 envios por proceso
CARGAS = (32, 128, 512, 2048)

# Cada proceso hijo guarda aca su copia del mapa, enviada una sola vez por
# el initializer en lugar de serializarla con cada consulta.
# Sin valor inicial: lo asigna _iniciar_trabajador al arrancar cada proceso.
_red_del_trabajador: Red  # pylint: disable=invalid-name


def _iniciar_trabajador(red: Red) -> None:
    """Initializer del pool: guarda el mapa en la memoria del proceso."""
    # pylint: disable-next=global-statement
    global _red_del_trabajador
    _red_del_trabajador = red


def _ruta_en_proceso(consulta: Consulta) -> Resultado:
    """Resuelve una consulta en un proceso hijo y devuelve la ruta."""
    origen, destino = consulta
    return a_estrella(_red_del_trabajador, origen, destino)


def _costo_en_proceso(consulta: Consulta) -> float:
    """Resuelve una consulta en un proceso hijo y devuelve solo el costo.

    Devolver un float en vez de la ruta reduce lo que se serializa de
    vuelta al proceso padre.
    """
    return _ruta_en_proceso(consulta).costo


# [EXPO 1] Un solo lugar para crear el pool (antes estaba repetido).
def crear_pool(
    red: Red,
    trabajadores: int = NUCLEOS,
    inicializador: Callable[[Red], None] = _iniciar_trabajador,
) -> ProcessPoolExecutor:
    """Pool de procesos que ya tienen el mapa cargado.

    Args:
        red: Mapa que recibe cada proceso al arrancar.
        trabajadores: Cantidad de procesos.
        inicializador: Funcion que corre una vez en cada proceso con el
            mapa. Por defecto lo guarda para las busquedas de este modulo.

    Returns:
        El pool, listo para usar con ``with``.
    """
    return ProcessPoolExecutor(
        max_workers=trabajadores,
        initializer=inicializador,
        initargs=(red,),
    )


def tamanio_de_lote(cantidad: int, trabajadores: int = NUCLEOS) -> int:
    """Consultas por envio: unos cuatro lotes por trabajador.

    Agrupar consultas (``chunksize``) reduce los viajes entre procesos.
    Con lotes demasiado grandes un trabajador lento retrasa a todos.

    Args:
        cantidad: Total de consultas.
        trabajadores: Cantidad de procesos.

    Returns:
        Tamanio de lote, al menos 1.

    Example:
        >>> tamanio_de_lote(2000, 8)
        62
        >>> tamanio_de_lote(3, 8)
        1
    """
    return max(1, cantidad // (trabajadores * ENVIOS_POR_TRABAJADOR))


def _mapear_en_procesos(
    red: Red,
    tarea: Callable[[Consulta], Any],
    consultas: Sequence[Consulta],
    trabajadores: int,
) -> list[Any]:
    """Aplica ``tarea`` a cada consulta en un pool de procesos."""
    with crear_pool(red, trabajadores) as ejecutor:
        return list(
            ejecutor.map(
                tarea,
                consultas,
                chunksize=tamanio_de_lote(len(consultas), trabajadores),
            )
        )


def secuencial(
    red: Red, consultas: Sequence[Consulta], algoritmo: Algoritmo = a_estrella
) -> list[float]:
    """Resuelve las consultas una detras de otra.

    Args:
        red: Mapa.
        consultas: Pares ``(origen, destino)``.
        algoritmo: Algoritmo de busqueda. Por defecto, A*.

    Returns:
        Costo de cada ruta, en el mismo orden.
    """
    return [
        algoritmo(red, origen, destino).costo for origen, destino in consultas
    ]


def con_hilos(
    red: Red, consultas: Sequence[Consulta], trabajadores: int = NUCLEOS
) -> list[float]:
    """Resuelve las consultas con un pool de hilos.

    Args:
        red: Mapa compartido por todos los hilos.
        consultas: Pares ``(origen, destino)``.
        trabajadores: Cantidad de hilos.

    Returns:
        Costo de cada ruta, en el mismo orden.
    """
    with ThreadPoolExecutor(max_workers=trabajadores) as ejecutor:
        return list(
            ejecutor.map(
                lambda c: a_estrella(red, c[0], c[1]).costo, consultas
            )
        )


def con_procesos(
    red: Red, consultas: Sequence[Consulta], trabajadores: int = NUCLEOS
) -> list[float]:
    """Resuelve las consultas con un pool de procesos.

    Args:
        red: Mapa que recibe cada proceso.
        consultas: Pares ``(origen, destino)``.
        trabajadores: Cantidad de procesos.

    Returns:
        Costo de cada ruta, en el mismo orden.
    """
    return _mapear_en_procesos(red, _costo_en_proceso, consultas, trabajadores)


def rutas_con_procesos(
    red: Red, consultas: Sequence[Consulta], trabajadores: int = NUCLEOS
) -> list[Resultado]:
    """Como :func:`con_procesos` pero devuelve la ruta completa.

    Args:
        red: Mapa que recibe cada proceso.
        consultas: Pares ``(origen, destino)``.
        trabajadores: Cantidad de procesos.

    Returns:
        Resultado de cada consulta, en el mismo orden.
    """
    return _mapear_en_procesos(red, _ruta_en_proceso, consultas, trabajadores)


def comparar(
    red: Red, consultas: Sequence[Consulta], trabajadores: int = NUCLEOS
) -> dict[str, Any]:
    """Corre las tres variantes y verifica que den lo mismo.

    Args:
        red: Mapa.
        consultas: Pares ``(origen, destino)``.
        trabajadores: Hilos o procesos a usar.

    Returns:
        Tiempos, aceleraciones y si los tres resultados coinciden.
    """
    costos_sec, t_sec = cronometrar(secuencial, red, consultas)
    costos_hilos, t_hilos = cronometrar(
        con_hilos, red, consultas, trabajadores
    )
    costos_proc, t_proc = cronometrar(
        con_procesos, red, consultas, trabajadores
    )
    return {
        "consultas": len(consultas),
        "trabajadores": trabajadores,
        "nodos": red.nodos,
        "t_secuencial": t_sec,
        "t_hilos": t_hilos,
        "t_procesos": t_proc,
        "aceleracion_hilos": t_sec / t_hilos,
        "aceleracion_procesos": t_sec / t_proc,
        "iguales": costos_sec == costos_hilos == costos_proc,
    }


def _tarea_trivial(_: object) -> int:
    """Tarea vacia, para medir solo el costo fijo del pool."""
    return 0


def medir_arranque_de_pool(red: Red, trabajadores: int = NUCLEOS) -> float:
    """Costo fijo del pool: levantar interpretes, enviar el mapa y cerrar.

    Se mapea una tarea trivial sobre varios elementos porque con una lista
    vacia el pool es perezoso y no llega a crear los procesos.

    Args:
        red: Mapa que recibe cada proceso.
        trabajadores: Cantidad de procesos.

    Returns:
        Segundos que tarda el ciclo completo del pool.
    """

    def ciclo_completo() -> None:
        with crear_pool(red, trabajadores) as ejecutor:
            tareas = range(trabajadores * 4)
            list(ejecutor.map(_tarea_trivial, tareas, chunksize=1))

    return cronometrar(ciclo_completo)[1]


def barrido(
    red: Red, cargas: Sequence[int] = CARGAS, trabajadores: int = NUCLEOS
) -> list[dict[str, Any]]:
    """Mide las tres variantes con cargas crecientes.

    Sirve para encontrar a partir de cuantas consultas conviene pagar el
    costo de arrancar procesos.

    Args:
        red: Mapa.
        cargas: Cantidades de consultas a probar.
        trabajadores: Hilos o procesos a usar.

    Returns:
        Una fila de :func:`comparar` por cada carga.
    """
    return [
        comparar(
            red, generar_consultas(red, cantidad, semilla=1), trabajadores
        )
        for cantidad in cargas
    ]
