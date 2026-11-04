"""Perfilado con las herramientas de la unidad 4 y 7.

=================  ==============================================
Herramienta        Que responde
=================  ==============================================
cProfile           en que FUNCION se va el tiempo
SnakeViz           lo mismo, en un grafico navegable (.prof)
line_profiler      que LINEA de esa funcion tiene la culpa
memory_profiler    cuanta memoria pide cada version
py-spy             flame graph, sin tocar el codigo (muestreo)
Scalene            CPU y memoria por linea, Python vs codigo nativo
=================  ==============================================

Uso::

    python perfilado.py                 cProfile, line_profiler, memoria
    snakeviz resultados/perfil_antes.prof
    py-spy record --subprocesses -o resultados/flamegraph.svg -- (sigue)
        python perfilado.py --carga
    scalene run -o resultados/scalene.json perfilado.py --- --carga
"""

from __future__ import annotations

import cProfile
import io
import pstats
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from planificador import archivos
from planificador.algoritmos import a_estrella, dijkstra_heap, dijkstra_lista
from planificador.concurrencia import secuencial
from planificador.consola import encabezado, separador, titulo
from planificador.consultas import Consulta, generar_consultas
from planificador.formato import formato_tiempo
from planificador.mediciones import con_memoria, mejor_de
from planificador.red import Red, generar_red, red_argentina

LADO = 45  # 2.025 nodos: el baseline tiene que terminar
CONSULTAS = 8
CONSULTAS_ARCHIVO = 100_000
CONSULTAS_CARGA = 300_000  # unos segundos: suficientes muestras
RESULTADOS = Path(__file__).parent / "resultados"


# -------------------------------------------------------------- cProfile


# cProfile -> archivo .prof que se abre con SnakeViz.
def perfilar(
    funcion: Callable[[], object], destino: Path | None = None
) -> tuple[pstats.Stats, float]:
    """Ejecuta ``funcion`` bajo cProfile.

    Args:
        funcion: Funcion sin argumentos a perfilar.
        destino: Si se indica, guarda el perfil en ese archivo ``.prof``
            para abrirlo con SnakeViz.

    Returns:
        Las estadisticas y el tiempo total medido por cProfile.
    """
    perfil = cProfile.Profile()
    perfil.runcall(funcion)
    estadisticas = pstats.Stats(perfil, stream=io.StringIO())
    if destino is not None:
        estadisticas.dump_stats(destino)
    return estadisticas, estadisticas.total_tt


def imprimir_top(estadisticas: pstats.Stats, filas: int = 6) -> None:
    """Imprime las funciones con mas tiempo propio (``tottime``)."""
    flujo = io.StringIO()
    estadisticas.stream = flujo
    estadisticas.sort_stats("tottime").print_stats(filas)
    lineas = flujo.getvalue().splitlines()
    inicio = next(
        (i for i, linea in enumerate(lineas) if "ncalls" in linea), 0
    )
    for linea in lineas[inicio:]:
        if linea.strip():
            # el camino completo del archivo no aporta y rompe el ancho
            print("  " + linea.replace(str(Path(__file__).parent), "."))


def resolver_todas(
    algoritmo: Callable, red: Red, consultas: list[Consulta]
) -> Callable[[], list]:
    """Funcion sin argumentos que resuelve todas las consultas."""
    return lambda: secuencial(red, consultas, algoritmo)


# ------------------------------------------------- herramientas externas


# line_profiler: que linea exacta tiene la culpa.
def por_linea(algoritmo: Callable, red: Red, consultas: list) -> str | None:
    """line_profiler sin decorador ni kernprof.

    Returns:
        El reporte, o ``None`` si line_profiler no esta instalado.
    """
    try:  # dependencia opcional: el script corre aunque no este
        from line_profiler import LineProfiler
    except ImportError:
        return None
    perfil = LineProfiler()
    perfil.add_function(algoritmo)
    perfil.runcall(resolver_todas(algoritmo, red, consultas))
    flujo = io.StringIO()
    perfil.print_stats(stream=flujo, stripzeros=True)
    return flujo.getvalue()


def memoria_mib(funcion: Callable, *argumentos) -> float | None:
    """Memoria adicional (MiB) que pide ``funcion``, con memory_profiler.

    Returns:
        Pico menos memoria inicial, o ``None`` si no esta instalado.
    """
    try:  # dependencia opcional
        from memory_profiler import memory_usage
    except ImportError:
        return None
    muestras = memory_usage((funcion, argumentos), interval=0.01)
    return max(muestras) - muestras[0]


# ------------------------------------------------------ carga de trabajo


# Carga para py-spy (flame graph) y Scalene (memoria).
def carga_de_trabajo() -> None:
    """Carga representativa para perfilar con py-spy o Scalene.

    Mezcla las tres situaciones del proyecto: lectura de un archivo
    grande, la tuberia con y sin cache, y el baseline contra A*.
    """
    with tempfile.TemporaryDirectory(prefix="pef_perfil_") as carpeta:
        red = red_argentina()
        entrada = Path(carpeta) / "consultas.txt"
        archivos.escribir_consultas(
            entrada,
            generar_consultas(red, CONSULTAS_CARGA, 500, semilla=21),
        )
        archivos.leer_todo(entrada)
        archivos.procesar_streaming(red, entrada, Path(carpeta) / "v1.txt")
        archivos.procesar_por_lotes(red, entrada, Path(carpeta) / "v2.txt")

    grilla = generar_red(LADO)
    consultas = generar_consultas(grilla, 3, 3)
    resolver_todas(dijkstra_lista, grilla, consultas)()
    resolver_todas(a_estrella, grilla, consultas)()


# ------------------------------------------------------------------ main


def seccion_algoritmos(red: Red, consultas: list[Consulta]) -> dict:
    """Perfila con cProfile antes y despues, y con line_profiler."""
    titulo("1. cProfile - ANTES: Dijkstra con lista")
    antes, total_antes = perfilar(
        resolver_todas(dijkstra_lista, red, consultas),
        RESULTADOS / "perfil_antes.prof",
    )
    imprimir_top(antes)
    print()
    print("  min() y el lambda de su clave se llevan casi todo el tiempo:")
    print(
        "  en cada una de las V vueltas recorre los V pendientes. Es O(V^2)."
    )
    print("  Grafico: snakeviz resultados/perfil_antes.prof")

    titulo("2. line_profiler - QUE LINEA EXACTAMENTE")
    reporte = por_linea(dijkstra_lista, red, consultas[:3])
    if reporte is None:
        print("  no instalado:  pip install line-profiler")
    else:
        for linea in reporte.splitlines():
            campos = linea.split()
            # encabezados y lineas ejecutadas (las que tienen Hits)
            ejecutada = (
                len(campos) > 1
                and campos[0].isdigit()
                and (campos[1].isdigit())
            )
            if ejecutada or linea.startswith(("Total", "Line #", "===")):
                print("  " + linea[:74])
        print()
        print("  cProfile dice QUE funcion; line_profiler dice QUE LINEA.")

    titulo("3. cProfile - DESPUES: A* con cola de prioridad")
    despues, total_despues = perfilar(
        resolver_todas(a_estrella, red, consultas),
        RESULTADOS / "perfil_despues.prof",
    )
    imprimir_top(despues)
    print()
    print("  El min() lineal desaparecio: el tiempo se reparte entre el heap")
    print("  y la heuristica. Ya no hay un unico cuello de botella.")

    _, total_heap = perfilar(resolver_todas(dijkstra_heap, red, consultas))
    return {
        "Dijkstra con lista (baseline)": total_antes,
        "Dijkstra con heap": total_heap,
        "A* con heuristica": total_despues,
    }


def seccion_archivos(carpeta: Path) -> None:
    """Perfila la tuberia de archivos y la memoria de la lectura."""
    red = red_argentina()
    entrada = carpeta / "consultas.txt"
    archivos.escribir_consultas(
        entrada, generar_consultas(red, CONSULTAS_ARCHIVO, 500, semilla=21)
    )

    titulo("4. cProfile - TUBERIA DE ARCHIVOS SIN CACHE (V1)")
    estadisticas, total_v1 = perfilar(
        lambda: archivos.procesar_streaming(red, entrada, carpeta / "v1.txt"),
        RESULTADOS / "perfil_archivos.prof",
    )
    imprimir_top(estadisticas, filas=5)
    _, total_v2 = perfilar(
        lambda: archivos.procesar_por_lotes(red, entrada, carpeta / "v2.txt")
    )
    print()
    print("  Con el buffer, escribir dejo de ser el problema: el tiempo esta")
    print(
        "  en A*, recalculando consultas repetidas. Por eso V2 agrega cache:"
    )
    print(
        f"  V1 {formato_tiempo(total_v1)} -> V2 {formato_tiempo(total_v2)} "
        "(tiempos inflados por cProfile)."
    )

    titulo("5. memory_profiler - LECTURA DEL ARCHIVO")
    todo = memoria_mib(archivos.leer_todo, entrada)
    if todo is None:
        print("  no instalado:  pip install memory-profiler")
        return
    streaming = memoria_mib(
        lambda ruta: sum(1 for _ in archivos.leer_consultas(ruta)), entrada
    )
    print(
        f"  readlines(), {CONSULTAS_ARCHIVO:,} lineas: {todo:7.1f} MiB extra"
    )
    print(f"  streaming con generador:       {streaming:7.1f} MiB extra")
    print("  memory_profiler mide la memoria del proceso entero (RSS), por")
    print("  eso difiere de tracemalloc, que cuenta solo objetos Python.")


def seccion_tracemalloc(red: Red, consultas: list[Consulta]) -> None:
    """Cuanto infla tracemalloc el tiempo de cada algoritmo.

    Es la medicion que respalda la correccion de la tabla del primer
    parcial: alli el tiempo se tomaba con tracemalloc activo.
    """
    titulo("6. EL COSTO DE MEDIR: tracemalloc")
    print(f"  {'por consulta':<22}{'sin':>12}{'con':>12}{'efecto':>10}")
    separador(56)
    for nombre, algoritmo, muestra in (
        ("Dijkstra con lista", dijkstra_lista, consultas[:3]),
        ("Dijkstra con heap", dijkstra_heap, consultas),
        ("A*", a_estrella, consultas),
    ):
        funcion = resolver_todas(algoritmo, red, muestra)
        _, sin = mejor_de(3, funcion)
        _, con, _ = con_memoria(funcion)
        print(
            f"  {nombre:<22}{formato_tiempo(sin / len(muestra)):>12}"
            f"{formato_tiempo(con / len(muestra)):>12}{con / sin:>9.1f}x"
        )
    separador(56)
    print("  tracemalloc registra cada objeto que se crea: castiga al heap y")
    print("  a A* (crean muchos) y casi no al baseline. Por eso el tiempo se")
    print("  mide sin tracemalloc y la memoria en otra pasada.")


def imprimir_resumen(totales: dict[str, float]) -> None:
    """Tiempos de cProfile por version y como seguir con otras herramientas."""
    titulo("7. RESUMEN")
    base = next(iter(totales.values()))
    print(f"  {'version':<34}{'tiempo':>12}{'mejora':>12}")
    separador(60)
    for nombre, total in totales.items():
        print(
            f"  {nombre:<34}{formato_tiempo(total):>12}{base / total:>11.1f}x"
        )
    separador(60)
    print("  cProfile cobra en cada llamada: sirve para saber DONDE se va el")
    print(
        "  tiempo, no CUANTO. Los tiempos del informe se miden sin perfilar."
    )
    print()
    print("  Siguientes pasos (ver README):")
    print("    snakeviz resultados/perfil_antes.prof")
    print(
        "    py-spy record --subprocesses -o resultados/flamegraph.svg "
        "-- python perfilado.py --carga"
    )
    print(
        "    scalene run -o resultados/scalene.json perfilado.py --- --carga"
    )


def main() -> None:
    """Punto de entrada."""
    if "--carga" in sys.argv:
        carga_de_trabajo()
        return

    RESULTADOS.mkdir(exist_ok=True)
    red = generar_red(LADO)
    consultas = generar_consultas(red, CONSULTAS, CONSULTAS)
    encabezado("PERFILADO", f"Mapa: {red}    Consultas: {CONSULTAS}")

    totales = seccion_algoritmos(red, consultas)
    with tempfile.TemporaryDirectory(prefix="pef_perfil_") as carpeta:
        seccion_archivos(Path(carpeta))
    seccion_tracemalloc(red, consultas)
    imprimir_resumen(totales)


if __name__ == "__main__":
    main()
