"""Banco de pruebas del primer parcial: algoritmos, cache y concurrencia.

Uso::

    python banco.py [--rapido]

Las funciones ``medir_*`` devuelven datos y las ``imprimir_*`` los
muestran. En el primer parcial todo estaba en un solo ``main()`` de 95
sentencias: separarlo deja las mediciones faciles de probar y de reusar.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from planificador import concurrencia
from planificador.algoritmos import (
    ALGORITMOS,
    COMPLEJIDADES,
    a_estrella,
    bfs,
    dijkstra_heap,
    dijkstra_lista,
)
from planificador.cache import CacheDeRutas
from planificador.consola import encabezado, separador, titulo
from planificador.consultas import Consulta, generar_consultas
from planificador.formato import formato_memoria, formato_tiempo
from planificador.mediciones import (
    con_memoria,
    cronometrar,
    guardar_json,
    mejor_de,
)
from planificador.red import Red, generar_red

SALIDA = Path(__file__).parent / "resultados" / "mediciones.json"
SALIDA_RAPIDA = SALIDA.with_name("mediciones_rapido.json")

LADOS_ESCALABILIDAD = (30, 40, 50, 60)
LADO_PRINCIPAL = 110  # 12.100 nodos
CONSULTAS_LOTE = 2000
PARES_DISTINTOS = 500  # cada par se repite unas 4 veces
MUESTRA_BASELINE = 3  # el baseline no admite el lote entero
MUESTRA_MEMORIA = 100  # el pico de un bucle secuencial no crece con el
REPETICIONES_TABLA = 2  # minimo de 2 corridas por el ruido de la CPU
CARGAS_CONCURRENCIA = (128, 512, 2048)

Fila = dict[str, Any]


# ------------------------------------------------------------ mediciones


def _explorados_totales(algoritmo, red: Red, consultas: list) -> int:
    """Resuelve todas las consultas y suma los nodos explorados."""
    return sum(algoritmo(red, o, d).explorados for o, d in consultas)


def medir_escalabilidad(
    lados: tuple[int, ...], consultas_por_tamanio: int = 25
) -> list[Fila]:
    """Tiempo y nodos explorados por consulta segun el tamanio del mapa.

    Args:
        lados: Lados de las grillas a probar.
        consultas_por_tamanio: Consultas promediadas en cada tamanio.

    Returns:
        Una fila por tamanio con tiempos y explorados por algoritmo.
    """
    filas = []
    for lado in lados:
        red = generar_red(lado)
        consultas = generar_consultas(
            red, consultas_por_tamanio, consultas_por_tamanio
        )
        fila: Fila = {
            "nodos": red.nodos,
            "aristas": red.aristas,
            "tiempos": {},
            "explorados": {},
        }
        for nombre, algoritmo in ALGORITMOS.items():
            explorados, transcurrido = cronometrar(
                _explorados_totales, algoritmo, red, consultas
            )
            fila["tiempos"][nombre] = transcurrido / len(consultas)
            fila["explorados"][nombre] = explorados / len(consultas)
        filas.append(fila)
        print(f"    V={red.nodos:>6,}  listo")
    return filas


def medir_calidad_bfs(red: Red, consultas: list[Consulta]) -> Fila:
    """Cuanto mas larga es la ruta de BFS que la optima.

    Args:
        red: Mapa.
        consultas: Consultas a comparar.

    Returns:
        Relacion de costo total, peor exceso y coincidencias.
    """
    peor, total_bfs, total_optimo, iguales = 0.0, 0.0, 0.0, 0
    for origen, destino in consultas:
        r_bfs = bfs(red, origen, destino)
        r_optimo = a_estrella(red, origen, destino)
        if not r_bfs.ruta or not r_optimo.ruta or r_optimo.costo == 0:
            continue
        peor = max(peor, r_bfs.costo / r_optimo.costo)
        total_bfs += r_bfs.costo
        total_optimo += r_optimo.costo
        iguales += abs(r_bfs.costo - r_optimo.costo) < 1e-9
    return {
        "relacion_costo_total": total_bfs / total_optimo,
        "exceso_peor": peor,
        "coincidencias": iguales,
        "consultas": len(consultas),
    }


def _correr_final(red: Red, lote: list[Consulta]) -> tuple[list, Fila]:
    """Deduplica, calcula las distintas en paralelo y sirve el resto.

    Returns:
        Costos del lote y estadisticas de la cache.
    """
    distintas = list(dict.fromkeys(lote))
    resultados = concurrencia.rutas_con_procesos(red, distintas)

    cache = CacheDeRutas(red, capacidad=len(distintas) * 2)
    for (origen, destino), resultado in zip(
        distintas, resultados, strict=True
    ):
        cache.precargar(origen, destino, resultado)

    costos = [cache.consultar(o, d).costo for o, d in lote]
    estadisticas = cache.estadisticas()
    estadisticas["distintas"] = len(distintas)
    return costos, estadisticas


class Etapa(NamedTuple):
    """Una fila de la tabla comparativa y como medirla."""

    version: str
    detalle: str
    observacion: str
    funcion: Callable
    args_tiempo: tuple
    args_memoria: tuple


# Refactor: etapas en una lista (antes 5 bloques copiados).
def medir_tabla(red: Red, lote: list[Consulta]) -> list[Fila]:
    """Tabla comparativa obligatoria del primer parcial.

    Cada etapa agrega una tecnica sobre la anterior. El baseline O(V^2) no
    termina en tiempo razonable con el lote entero: se mide sobre una
    muestra y se proyecta el total.

    El tiempo se mide SIN tracemalloc y la memoria en otra pasada. El
    primer parcial media las dos cosas juntas: tracemalloc hacia 3 o 4 veces
    mas lentos a Dijkstra con heap y a A* (crean muchos objetos), no al
    baseline (casi no crea), y no ve a los procesos hijos. Asi subestimaba
    la mejora del heap y de A* y exageraba la de los procesos.

    Args:
        red: Mapa grande.
        lote: Consultas con repeticiones.

    Returns:
        Una fila por version, con aceleracion respecto del baseline.
    """
    muestra = lote[:MUESTRA_BASELINE]
    muestra_memoria = lote[:MUESTRA_MEMORIA]
    secuencial = concurrencia.secuencial
    etapas = [
        Etapa(
            "Implementacion inicial",
            "Dijkstra con lista, O(V^2)",
            "Baseline",
            secuencial,
            (red, muestra, dijkstra_lista),
            (red, muestra, dijkstra_lista),
        ),
        Etapa(
            "Estructura optimizada",
            "Dijkstra con heap, O((V+E) log V)",
            "Mejora de busqueda",
            secuencial,
            (red, lote, dijkstra_heap),
            (red, muestra_memoria, dijkstra_heap),
        ),
        Etapa(
            "Algoritmo optimizado",
            "A* con heuristica admisible",
            "Mejor escalabilidad",
            secuencial,
            (red, lote, a_estrella),
            (red, muestra_memoria, a_estrella),
        ),
        Etapa(
            "Concurrencia/paralelismo",
            f"A* en {concurrencia.NUCLEOS} procesos",
            "Evaluar overhead",
            concurrencia.con_procesos,
            (red, lote),
            (red, lote),
        ),
        Etapa(
            "Version final",
            "A* + deduplicacion + procesos + cache",
            "Resultado final",
            _correr_final,
            (red, lote),
            (red, lote),
        ),
    ]

    filas = []
    for etapa in etapas:
        # Corregimos la tabla del P1: el tiempo se mide SIN
        # tracemalloc y la memoria en otra pasada.
        salida, segundos = mejor_de(
            REPETICIONES_TABLA, etapa.funcion, *etapa.args_tiempo
        )
        _, _, pico = con_memoria(etapa.funcion, *etapa.args_memoria)
        fila: Fila = {
            "version": etapa.version,
            "detalle": etapa.detalle,
            "observacion": etapa.observacion,
            "segundos": segundos,
            "memoria": pico,
            "proyectado": False,
        }
        if etapa.funcion is _correr_final:
            fila["cache"] = salida[1]
        filas.append(fila)

    base = filas[0]
    base["segundos"] *= len(lote) / len(muestra)
    base.update(proyectado=True, muestra=len(muestra))
    for fila in filas:
        fila["por_consulta"] = fila["segundos"] / len(lote)
        fila["aceleracion"] = base["segundos"] / fila["segundos"]
    return filas


# ------------------------------------------------------------- impresion


def imprimir_escalabilidad(filas: list[Fila]) -> None:
    """Tabla de tiempos por tamanio y crecimiento de cada algoritmo."""
    print()
    print(
        f"  {'nodos':>8}{'BFS':>12}{'Dijkstra lista':>17}"
        f"{'Dijkstra heap':>16}{'A*':>12}"
    )
    separador(66)
    for fila in filas:
        tiempos = fila["tiempos"]
        print(
            f"  {fila['nodos']:>8,}"
            f"{formato_tiempo(tiempos['BFS']):>12}"
            f"{formato_tiempo(tiempos['Dijkstra lista']):>17}"
            f"{formato_tiempo(tiempos['Dijkstra heap']):>16}"
            f"{formato_tiempo(tiempos['A*']):>12}"
        )
    separador(66)
    factor_v = filas[-1]["nodos"] / filas[0]["nodos"]
    for nombre in ALGORITMOS:
        crecimiento = (
            filas[-1]["tiempos"][nombre] / filas[0]["tiempos"][nombre]
        )
        print(
            f"  {nombre:<16}{COMPLEJIDADES[nombre]:<18}"
            f"al multiplicar V por {factor_v:.0f}, "
            f"el tiempo x{crecimiento:,.0f}"
        )
    medido = (
        filas[-1]["tiempos"]["Dijkstra lista"]
        / filas[0]["tiempos"]["Dijkstra lista"]
    )
    print()
    print(
        f"  Una O(V^2) ideal daria x{factor_v**2:.0f}; medimos x{medido:.0f}."
    )


def imprimir_explorados(filas: list[Fila]) -> None:
    """Nodos explorados por Dijkstra con heap y por A*."""
    print(f"  {'nodos':>8}{'Dijkstra heap':>16}{'A*':>10}{'reduccion':>12}")
    separador(46)
    for fila in filas:
        dijkstra = fila["explorados"]["Dijkstra heap"]
        estrella = fila["explorados"]["A*"]
        print(
            f"  {fila['nodos']:>8,}{dijkstra:>16,.0f}{estrella:>10,.0f}"
            f"{1 - estrella / dijkstra:>11.0%}"
        )
    separador(46)
    print(
        "  Misma complejidad teorica, pero A* camina hacia el destino en vez"
    )
    print("  de expandirse en circulo: visita una fraccion de los nodos.")


def imprimir_calidad(calidad: Fila, nodos: int) -> None:
    """Resumen de cuanto empeora la ruta de BFS."""
    exceso_total = calidad["relacion_costo_total"] - 1
    print(f"  Sobre {calidad['consultas']} consultas en {nodos:,} nodos:")
    print(f"    El costo total de BFS fue {exceso_total:.1%} mayor.")
    print(f"    En el peor caso, {calidad['exceso_peor'] - 1:.1%} mas larga.")
    print(
        f"    Coincidio con la optima en {calidad['coincidencias']} de "
        f"{calidad['consultas']} consultas."
    )
    print("  Un algoritmo mas rapido que da la respuesta equivocada no es")
    print("  una optimizacion.")


def imprimir_tabla(tabla: list[Fila], consultas: int) -> None:
    """Tabla comparativa con notas sobre el baseline y la memoria."""
    print()
    print(
        f"  {'version':<26}{'tiempo':>12}{'mem. padre':>11}"
        f"{'vs base*':>10}  observacion"
    )
    separador(74)
    for fila in tabla:
        marca = " *" if fila["proyectado"] else ""
        print(
            f"  {fila['version']:<26}"
            f"{formato_tiempo(fila['segundos']) + marca:>12}"
            f"{formato_memoria(fila['memoria']):>11}"
            f"{fila['aceleracion']:>9,.0f}x  {fila['observacion']}"
        )
    separador(74)
    base = tabla[0]
    print(
        f"  * Baseline proyectado: {formato_tiempo(base['por_consulta'])} "
        f"por consulta x {consultas:,} consultas"
    )
    print(f"    (medido sobre {base['muestra']} consultas reales).")
    print(
        "  Tiempo sin tracemalloc, minimo de "
        f"{REPETICIONES_TABLA} corridas. Memoria: pico Python"
    )
    print(
        f"  del proceso padre (secuenciales: sobre {MUESTRA_MEMORIA} "
        "consultas)."
    )
    estadisticas = tabla[-1]["cache"]
    ahorradas = estadisticas["consultas"] - estadisticas["distintas"]
    print(
        f"  La version final calculo {estadisticas['distintas']:,} rutas "
        f"distintas y respondio {ahorradas:,} desde la cache "
        f"({ahorradas / estadisticas['consultas']:.0%} del lote)."
    )


def imprimir_concurrencia(arranque: float, barrido: list[Fila]) -> None:
    """Secuencial contra hilos y procesos con cargas crecientes."""
    print()
    print(
        f"  {'consultas':>10}{'secuencial':>13}{'hilos':>11}{'procesos':>11}"
        f"{'hilos':>9}{'procesos':>10}"
    )
    separador(66)
    for fila in barrido:
        print(
            f"  {fila['consultas']:>10,}"
            f"{formato_tiempo(fila['t_secuencial']):>13}"
            f"{formato_tiempo(fila['t_hilos']):>11}"
            f"{formato_tiempo(fila['t_procesos']):>11}"
            f"{fila['aceleracion_hilos']:>8.2f}x"
            f"{fila['aceleracion_procesos']:>9.2f}x"
        )
    separador(66)
    print("  Los HILOS quedan cerca de 1x: el GIL no deja paralelizar este")
    print("  trabajo de CPU en bytecode Python.")
    print(
        f"  Los PROCESOS pagan {formato_tiempo(arranque)} fijos de arranque:"
    )
    print("  recien convienen cuando el lote es lo bastante grande.")


# ------------------------------------------------------------------ main


# Refactor: main() de 95 sentencias -> medir_* + imprimir_*.
def main() -> None:
    """Corre las cinco secciones y guarda las mediciones en JSON."""
    rapido = "--rapido" in sys.argv
    lado = 60 if rapido else LADO_PRINCIPAL
    consultas = 200 if rapido else CONSULTAS_LOTE
    pares = 50 if rapido else PARES_DISTINTOS
    cargas = (64, 256) if rapido else CARGAS_CONCURRENCIA

    encabezado(
        "PLANIFICADOR INTELIGENTE DE RUTAS - banco de pruebas"
        + ("  (modo rapido)" if rapido else ""),
        f"Python {sys.version.split()[0]}   Nucleos: {concurrencia.NUCLEOS}",
    )
    resultados: Fila = {
        "nucleos": concurrencia.NUCLEOS,
        "python": sys.version.split()[0],
    }

    titulo("1. ESCALABILIDAD: tiempo por consulta segun el tamanio del mapa")
    print("  Midiendo...")
    escalabilidad = medir_escalabilidad(LADOS_ESCALABILIDAD)
    resultados["escalabilidad"] = escalabilidad
    imprimir_escalabilidad(escalabilidad)

    titulo("2. POR QUE A* GANA: nodos explorados por consulta")
    imprimir_explorados(escalabilidad)

    red_media = generar_red(60)
    calidad = medir_calidad_bfs(
        red_media, generar_consultas(red_media, 60, 60)
    )
    resultados["calidad_bfs"] = calidad
    titulo("3. BFS ES EL MAS RAPIDO, PERO NO RESUELVE EL PROBLEMA")
    imprimir_calidad(calidad, red_media.nodos)

    red = generar_red(lado)
    lote = generar_consultas(red, consultas, pares)
    titulo(
        f"4. TABLA COMPARATIVA - {len(lote):,} consultas, {red.nodos:,} nodos"
    )
    print("  Midiendo cada version (el baseline tarda)...", flush=True)
    tabla = medir_tabla(red, lote)
    resultados["tabla"] = tabla
    imprimir_tabla(tabla, len(lote))

    titulo("5. CONCURRENCIA: el overhead tambien se mide")
    arranque = concurrencia.medir_arranque_de_pool(red)
    barrido = concurrencia.barrido(red, cargas)
    resultados["concurrencia"] = {"arranque": arranque, "barrido": barrido}
    imprimir_concurrencia(arranque, barrido)

    # el modo rapido no pisa las mediciones completas del informe
    guardar_json(SALIDA_RAPIDA if rapido else SALIDA, resultados)


if __name__ == "__main__":
    main()
