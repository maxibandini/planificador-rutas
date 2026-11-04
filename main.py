"""Demostracion sobre el mapa de ciudades argentinas.

Uso::

    python main.py [origen] [destino]
"""

from __future__ import annotations

import sys

from planificador.algoritmos import ALGORITMOS, COMPLEJIDADES, Resultado
from planificador.cache import CacheDeRutas, crear_memoizado
from planificador.consola import encabezado, mostrar_ruta, separador, titulo
from planificador.formato import formato_tiempo
from planificador.mediciones import cronometrar
from planificador.red import Red, red_argentina

ORIGEN_POR_DEFECTO = "Ushuaia"
DESTINO_POR_DEFECTO = "Salta"


def leer_argumentos(red: Red, argumentos: list[str]) -> tuple[str, str]:
    """Obtiene origen y destino de la linea de comandos.

    Args:
        red: Mapa donde tienen que existir las ciudades.
        argumentos: Argumentos sin el nombre del script.

    Returns:
        Tupla ``(origen, destino)``.

    Raises:
        SystemExit: Si alguna ciudad no existe, despues de listarlas.
    """
    origen = argumentos[0] if argumentos else ORIGEN_POR_DEFECTO
    destino = argumentos[1] if len(argumentos) > 1 else DESTINO_POR_DEFECTO
    for ciudad in (origen, destino):
        if ciudad not in red:
            print(f"No conozco la ciudad '{ciudad}'. Ciudades disponibles:")
            for nombre in sorted(red.adyacencia):
                print("   ", nombre)
            raise SystemExit(1)
    return origen, destino


# Devuelve los resultados para no volver a calcular A*.
def comparar_algoritmos(
    red: Red, origen: str, destino: str
) -> dict[str, Resultado]:
    """Resuelve la consulta con los cuatro algoritmos e imprime la tabla.

    Args:
        red: Mapa.
        origen: Ciudad de partida.
        destino: Ciudad de llegada.

    Returns:
        Resultado de cada algoritmo, por nombre. Se reutiliza despues para
        no volver a calcular A*.
    """
    titulo("1. LA MISMA CONSULTA CON LOS CUATRO ALGORITMOS")
    print(
        f"  {'algoritmo':<18}{'complejidad':<18}{'distancia':>12}"
        f"{'ciudades':>9}{'explorados':>12}"
    )
    separador()
    resultados = {}
    for nombre, algoritmo in ALGORITMOS.items():
        resultado = algoritmo(red, origen, destino)
        resultados[nombre] = resultado
        print(
            f"  {nombre:<18}{COMPLEJIDADES[nombre]:<18}"
            f"{resultado.costo:>10,.0f} u.{len(resultado.ruta):>10}"
            f"{resultado.explorados:>12}"
        )
    separador()
    print("  BFS minimiza TRAMOS, no distancia: llega en menos escalas y")
    print("  recorre mas. Los otros tres son optimos: misma distancia.")
    print("  Lista y heap son EL MISMO algoritmo con distinta estructura")
    print("  para pedir el minimo. A* explora menos: se saltea las ciudades")
    print("  que estan lejos pero hacia el otro lado.")

    optima = resultados["A*"]
    print()
    print(f"  Ruta optima ({optima.costo:,.0f} unidades simuladas):")
    mostrar_ruta(optima.ruta)
    return resultados


def demostrar_cache(cache: CacheDeRutas, origen: str, destino: str) -> None:
    """Mide la misma consulta dos veces: calculada y desde la cache.

    Args:
        cache: Cache vacia.
        origen: Ciudad de partida.
        destino: Ciudad de llegada.
    """
    titulo("2. EL CACHE DE RUTAS")
    _, t_primera = cronometrar(cache.consultar, origen, destino)
    _, t_segunda = cronometrar(cache.consultar, origen, destino)
    print(f"  Primera consulta (se calcula): {formato_tiempo(t_primera):>12}")
    print(f"  Segunda consulta (del cache):  {formato_tiempo(t_segunda):>12}")
    print(f"  {t_primera / t_segunda:,.0f} veces mas rapida.")


def demostrar_invalidacion(
    red: Red,
    cache: CacheDeRutas,
    optima: Resultado,
    origen: str,
    destino: str,
) -> None:
    """Corta un tramo de la ruta optima y compara memoizacion con cache.

    Args:
        red: Mapa (se modifica).
        cache: Cache que ya tiene guardada la ruta.
        optima: Ruta optima antes del corte.
        origen: Ciudad de partida.
        destino: Ciudad de llegada.
    """
    titulo("3. SE CORTA UNA RUTA: memoizacion vs caching inteligente")
    if len(optima.ruta) < 2:
        print("  Origen y destino coinciden: no hay tramo para cortar.")
        return
    memoizado = crear_memoizado(red)
    memoizado(origen, destino)  # queda guardada en lru_cache

    # Bug del P1 que encontraron los tests: usaba siempre
    # ruta[2] y ruta[3] y fallaba con rutas de menos de 4 ciudades.
    indice = min(2, len(optima.ruta) - 2)
    a, b = optima.ruta[indice], optima.ruta[indice + 1]
    print(f"  Se corta el tramo {a} - {b}, que la ruta optima usaba.")
    invalidadas = cache.cortar_tramo(a, b)
    print(f"  El cache inteligente invalido {invalidadas} ruta(s).")
    print()

    vieja = memoizado(origen, destino)
    print(f"  MEMOIZACION (lru_cache) devuelve {vieja.costo:,.0f} unidades")
    try:
        red.costo_de_ruta(vieja.ruta)
        print("    y la ruta sigue siendo valida")
    except ValueError as error:
        print(f"    RUTA OBSOLETA -> {error}")
        print(
            "    lru_cache no sabe que el mapa cambio: guarda por argumentos."
        )

    nueva = cache.consultar(origen, destino)
    red.costo_de_ruta(nueva.ruta)  # lanza ValueError si fuera invalida
    print()
    print(f"  CACHE INTELIGENTE devuelve {nueva.costo:,.0f} unidades")
    print("    ruta recalculada y valida:")
    mostrar_ruta(nueva.ruta)
    print()
    print(
        f"  El desvio cuesta {nueva.costo - optima.costo:,.0f} unidades mas."
    )
    print("  Distancias de un modelo didactico, no kilometros viales.")


def mostrar_siguientes_pasos() -> None:
    """Lista los demas scripts del proyecto."""
    titulo("4. PARA VER LAS MEDICIONES COMPLETAS")
    print("  python banco.py        algoritmos, cache y concurrencia")
    print("  python banco_es.py     archivos grandes: buffer, lotes, paralelo")
    print("  python perfilado.py    cProfile, SnakeViz, line/memory_profiler")
    print("  python servidor.py     API web con Flask")
    print()


# Refactor: el main() de 76 sentencias quedo en 4 funciones.
def main() -> None:
    """Punto de entrada."""
    red = red_argentina()
    origen, destino = leer_argumentos(red, sys.argv[1:])

    encabezado("PLANIFICADOR INTELIGENTE DE RUTAS")
    print(f"  Mapa: {red}")
    print(f"  Consulta: {origen}  ->  {destino}")

    resultados = comparar_algoritmos(red, origen, destino)
    cache = CacheDeRutas(red)
    demostrar_cache(cache, origen, destino)
    demostrar_invalidacion(red, cache, resultados["A*"], origen, destino)
    mostrar_siguientes_pasos()


if __name__ == "__main__":
    main()
