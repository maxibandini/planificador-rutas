"""Banco de E/S: archivos grandes con buffer, lotes y procesamiento paralelo.

Uso::

    python banco_es.py [--rapido] [--conservar]

Los archivos se generan en una carpeta temporal del sistema y no dentro
del proyecto: escribir cientos de MB en una carpeta sincronizada (OneDrive,
Dropbox) mediria la sincronizacion y no el programa.

Cuando una variante ingenua tardaria demasiado con el volumen completo se
mide sobre una muestra y se proyecta, igual que el baseline del primer
parcial. Esas filas se marcan con ``*``.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

from planificador import archivos
from planificador.algoritmos import Resultado
from planificador.concurrencia import NUCLEOS
from planificador.consola import encabezado, separador, titulo
from planificador.consultas import generar_consultas
from planificador.formato import formato_memoria, formato_tiempo
from planificador.mediciones import con_memoria, guardar_json, mejor_de
from planificador.red import Red, generar_red, red_argentina

SALIDA = Path(__file__).parent / "resultados" / "mediciones_es.json"
SALIDA_RAPIDA = SALIDA.with_name("mediciones_es_rapido.json")

Fila = dict[str, Any]


class Escala(NamedTuple):
    """Volumenes de cada seccion. Es inmutable: solo agrupa datos."""

    lineas_lectura: int
    lineas_escritura: int
    muestra_ingenua: int
    consultas_tuberia: int
    pares_tuberia: int
    lado_paralelo: int
    consultas_paralelo: int
    lote_paralelo: int
    trabajadores: tuple[int, ...]
    filas_sqlite: int
    muestra_sqlite: int
    repeticiones: int


ESCALA_COMPLETA = Escala(
    lineas_lectura=1_000_000,
    lineas_escritura=1_000_000,
    muestra_ingenua=10_000,
    consultas_tuberia=200_000,
    pares_tuberia=500,
    lado_paralelo=110,
    consultas_paralelo=4_000,
    lote_paralelo=100,
    trabajadores=(1, 2, 4, NUCLEOS),
    filas_sqlite=200_000,
    muestra_sqlite=500,
    repeticiones=3,
)
ESCALA_RAPIDA = ESCALA_COMPLETA._replace(
    lineas_lectura=200_000,
    lineas_escritura=200_000,
    muestra_ingenua=2_000,
    consultas_tuberia=20_000,
    pares_tuberia=200,
    lado_paralelo=60,
    consultas_paralelo=600,
    lote_paralelo=50,
    trabajadores=(1, NUCLEOS),
    filas_sqlite=20_000,
    muestra_sqlite=100,
    repeticiones=2,
)


def _fila(nombre: str, segundos: float, memoria: int | None = None) -> Fila:
    """Fila medida sobre el volumen completo."""
    return {
        "variante": nombre,
        "segundos": segundos,
        "memoria": memoria,
        "proyectado": False,
    }


def _fila_proyectada(
    nombre: str, segundos_muestra: float, muestra: int, total: int
) -> Fila:
    """Fila de una variante medida sobre una muestra y proyectada al total.

    Se usa con las versiones ingenuas, que con el volumen completo tardarian
    minutos u horas (igual que el baseline del primer parcial).
    """
    fila = _fila(nombre, segundos_muestra / muestra * total)
    fila.update(proyectado=True, muestra=muestra)
    return fila


# ------------------------------------------------------------ mediciones


def medir_lectura(carpeta: Path, escala: Escala, red: Red) -> list[Fila]:
    """readlines() contra streaming contra lotes: tiempo y memoria.

    Args:
        carpeta: Carpeta temporal de trabajo.
        escala: Volumenes a usar.
        red: Mapa del que salen las consultas.

    Returns:
        Una fila por estrategia de lectura.
    """
    entrada = carpeta / "consultas_lectura.txt"
    archivos.escribir_consultas(
        entrada, generar_consultas(red, escala.lineas_lectura, semilla=11)
    )

    def contar_streaming(ruta: Path) -> int:
        return sum(1 for _ in archivos.leer_consultas(ruta))

    def contar_por_lotes(ruta: Path) -> int:
        return sum(
            len(lote) for lote in archivos.leer_consultas_por_lotes(ruta)
        )

    filas = []
    for nombre, funcion in (
        ("readlines(): todo en memoria", archivos.leer_todo),
        ("Streaming linea a linea", contar_streaming),
        ("Lotes de 10.000 lineas", contar_por_lotes),
    ):
        # Dos pasadas: tracemalloc encarece cada asignacion y falsearia el
        # tiempo, asi que el tiempo se mide sin el y la memoria con el.
        _, segundos = mejor_de(escala.repeticiones, funcion, entrada)
        _, _, pico = con_memoria(funcion, entrada)
        filas.append(_fila(nombre, segundos, pico))
    return filas


def medir_escritura(carpeta: Path, escala: Escala) -> list[Fila]:
    """Abrir por linea contra buffer chico, buffer grande y lotes.

    Args:
        carpeta: Carpeta temporal de trabajo.
        escala: Volumenes a usar.

    Returns:
        Una fila por estrategia de escritura.
    """
    linea = archivos.formatear_resultado(
        "Ushuaia", "Salta", Resultado(["Ushuaia", "Salta"], 4818.8, 9)
    )
    total = escala.lineas_escritura
    destino = carpeta / "escritura.txt"
    _, segundos = mejor_de(
        escala.repeticiones,
        archivos.escribir_abriendo_por_linea,
        destino,
        [linea] * escala.muestra_ingenua,
    )
    filas = [
        _fila_proyectada(
            "Abrir y cerrar por linea",
            segundos,
            escala.muestra_ingenua,
            total,
        )
    ]
    # Una lista y no un generador: un generador se agota en la primera
    # repeticion y las siguientes escribirian un archivo vacio.
    lineas = [linea] * total
    for nombre, funcion, argumentos in (
        ("Una apertura, buffer 8 KiB", archivos.escribir_con_buffer, (8192,)),
        ("Una apertura, buffer 1 MiB", archivos.escribir_con_buffer, ()),
        ("Lotes con writelines", archivos.escribir_por_lotes, ()),
    ):
        escritas, segundos = mejor_de(
            escala.repeticiones, funcion, destino, lineas, *argumentos
        )
        if escritas != total:
            raise RuntimeError(f"{nombre}: se escribieron {escritas} lineas")
        filas.append(_fila(nombre, segundos))
    return filas


def medir_tuberias(carpeta: Path, escala: Escala) -> tuple[list[Fila], bool]:
    """Archivo de consultas -> rutas -> archivo de resultados, 4 versiones.

    Usa el mapa argentino con muchas consultas repetidas: el calculo es
    barato y la E/S pesa.

    Args:
        carpeta: Carpeta temporal de trabajo.
        escala: Volumenes a usar.

    Returns:
        Las filas y si las cuatro salidas son identicas byte a byte.
    """
    red = red_argentina()
    entrada = carpeta / "consultas_argentina.txt"
    archivos.escribir_consultas(
        entrada,
        generar_consultas(
            red, escala.consultas_tuberia, escala.pares_tuberia, semilla=21
        ),
    )
    versiones = (
        ("V0 Ingenua", archivos.procesar_ingenuo, ()),
        ("V1 Streaming + buffer", archivos.procesar_streaming, ()),
        ("V2 Lotes + cache", archivos.procesar_por_lotes, ()),
        ("V3 Lotes en paralelo", archivos.procesar_en_paralelo, ()),
    )
    filas, salidas = [], []
    for indice, (nombre, funcion, extra) in enumerate(versiones):
        salida = carpeta / f"resultados_v{indice}.txt"
        _, segundos = mejor_de(
            escala.repeticiones, funcion, red, entrada, salida, *extra
        )
        filas.append(_fila(nombre, segundos))
        salidas.append(salida.read_bytes())
    return filas, all(salida == salidas[0] for salida in salidas)


def medir_paralelo(carpeta: Path, escala: Escala) -> tuple[list[Fila], bool]:
    """Lotes en el proceso principal contra lotes en 1, 2, 4 y 8 procesos.

    Usa una grilla grande con consultas distintas: el calculo domina.

    Args:
        carpeta: Carpeta temporal de trabajo.
        escala: Volumenes a usar.

    Returns:
        Las filas y si todas las salidas son identicas.
    """
    red = generar_red(escala.lado_paralelo)
    entrada = carpeta / "consultas_grilla.txt"
    archivos.escribir_consultas(
        entrada, generar_consultas(red, escala.consultas_paralelo, semilla=31)
    )
    referencia = carpeta / "grilla_secuencial.txt"
    _, segundos = mejor_de(
        escala.repeticiones,
        archivos.procesar_por_lotes,
        red,
        entrada,
        referencia,
    )
    filas = [_fila("Lotes secuencial, este proceso", segundos)]
    iguales = True
    for trabajadores in escala.trabajadores:
        salida = carpeta / f"grilla_{trabajadores}.txt"
        _, segundos = mejor_de(
            escala.repeticiones,
            archivos.procesar_en_paralelo,
            red,
            entrada,
            salida,
            escala.lote_paralelo,
            trabajadores,
        )
        plural = "s" if trabajadores > 1 else ""
        filas.append(
            _fila(f"Lotes en {trabajadores} proceso{plural}", segundos)
        )
        iguales &= salida.read_bytes() == referencia.read_bytes()
    return filas, iguales


def medir_sqlite(
    carpeta: Path, escala: Escala, resultados: Path
) -> tuple[list[Fila], bool]:
    """Insertar fila por fila con commit contra executemany por lotes.

    Args:
        carpeta: Carpeta temporal de trabajo.
        escala: Volumenes a usar.
        resultados: Archivo de resultados del que salen las filas.

    Returns:
        Las filas y si las bases quedaron con la cantidad esperada.
    """
    filas_db = list(archivos.leer_resultados(resultados))[
        : escala.filas_sqlite
    ]
    muestra = filas_db[: escala.muestra_sqlite]
    base_uno = carpeta / "uno_a_uno.db"
    base_lotes = carpeta / "por_lotes.db"
    # una sola corrida: cada commit escribe a disco y tarda milisegundos
    _, segundos = mejor_de(
        1, archivos.guardar_en_sqlite_uno_a_uno, base_uno, muestra
    )
    filas = [
        _fila_proyectada(
            "Un INSERT y un commit por fila",
            segundos,
            len(muestra),
            len(filas_db),
        )
    ]

    def insertar_en_base_nueva() -> int:
        # cada repeticion arranca de una base vacia, si no se acumulan filas
        base_lotes.unlink(missing_ok=True)
        return archivos.guardar_en_sqlite_por_lotes(base_lotes, filas_db)

    _, segundos = mejor_de(escala.repeticiones, insertar_en_base_nueva)
    filas.append(_fila("executemany, commit por lote de 1.000", segundos))
    correctas = archivos.contar_filas(base_uno) == len(muestra) and (
        archivos.contar_filas(base_lotes) == len(filas_db)
    )
    return filas, correctas


# ------------------------------------------------------------- impresion


def imprimir_tabla(filas: list[Fila], con_memoria_pico: bool = False) -> None:
    """Tabla de variantes con aceleracion respecto de la primera fila."""
    base = filas[0]["segundos"]
    columna = f"{'mem. pico':>11}" if con_memoria_pico else ""
    print(f"  {'variante':<38}{'tiempo':>12}{columna}{'vs primera':>12}")
    separador(74)
    for fila in filas:
        marca = " *" if fila["proyectado"] else ""
        memoria = (
            f"{formato_memoria(fila['memoria']):>11}"
            if con_memoria_pico
            else ""
        )
        print(
            f"  {fila['variante']:<38}"
            f"{formato_tiempo(fila['segundos']) + marca:>12}{memoria}"
            f"{base / fila['segundos']:>11,.1f}x"
        )
    separador(74)
    proyectadas = [fila for fila in filas if fila["proyectado"]]
    for fila in proyectadas:
        print(
            f"  * Medido sobre {fila['muestra']:,} elementos y proyectado "
            "al volumen completo."
        )


def concluir_lectura(filas: list[Fila]) -> None:
    """Conclusion de la lectura segun lo que se midio."""
    todo, streaming = filas[0], filas[1]
    print(
        f"  readlines() pidio {formato_memoria(todo['memoria'])}: crece con "
        "el archivo. El generador no."
    )
    if streaming["segundos"] > todo["segundos"]:
        relacion = streaming["segundos"] / todo["segundos"]
        print(
            f"  El streaming tardo {relacion:.1f}x mas: readlines() lee en "
            "bloque en C. Se paga"
        )
        print(
            "  un poco de tiempo para que la memoria no dependa del archivo."
        )
    print("  Los lotes no aceleran la lectura: agrupan el trabajo que sigue.")


def concluir_tuberias(filas: list[Fila]) -> None:
    """Conclusion de la tuberia segun lo que se midio, no fija."""
    secuencial, paralelo = filas[2]["segundos"], filas[3]["segundos"]
    print("  La mayor parte de la mejora viene del buffer y de la cache.")
    if paralelo < secuencial:
        print(f"  Los procesos sumaron {secuencial / paralelo:.1f}x sobre V2.")
    else:
        print(
            f"  Los procesos fueron {paralelo / secuencial:.1f}x mas lentos "
            "que V2: el calculo"
        )
        print("  es barato y pesan el arranque y el envio de los lotes.")


def concluir_paralelo(filas: list[Fila]) -> None:
    """Escalado contra 1 proceso, que es la referencia justa.

    "Lotes en 1 proceso" paga lo mismo que los demas (arranque del pool,
    envio del mapa y de los lotes) y corre en un proceso nuevo. Comparar
    contra el secuencial del proceso principal mezcla el paralelismo con
    otros efectos: en la CPU hibrida del grupo el proceso principal, que ya
    hizo mucha E/S, corria mas lento que un proceso recien creado.
    """
    secuencial, un_proceso = filas[0]["segundos"], filas[1]["segundos"]
    mejor = min(filas[2:], key=lambda fila: fila["segundos"])
    escalado = un_proceso / mejor["segundos"]
    if un_proceso < secuencial:
        relacion = secuencial / un_proceso
        print(
            f"  Mismo trabajo en 1 proceso nuevo: {relacion:.1f}x mas rapido "
            "que en este"
        )
        print("  proceso (efecto de la CPU hibrida, no del paralelismo).")
    print(
        f"  Paralelismo real: {mejor['variante']} rinde {escalado:.1f}x "
        "contra 1 proceso."
    )
    if escalado <= 1:
        print("  El lote es chico: el arranque del pool se come la ganancia.")


# ------------------------------------------------------------------ main


# Banco de E/S: lectura, escritura, tuberia, paralelo, SQLite.
def main() -> None:
    """Corre las cinco secciones y guarda las mediciones en JSON."""
    rapido = "--rapido" in sys.argv
    escala = ESCALA_RAPIDA if rapido else ESCALA_COMPLETA
    carpeta = Path(tempfile.mkdtemp(prefix="pef_es_"))
    resultados: Fila = {"nucleos": NUCLEOS, "python": sys.version.split()[0]}

    encabezado(
        "ENTRADA/SALIDA DE ARCHIVOS GRANDES" + (" (rapido)" if rapido else ""),
        f"Carpeta temporal: {carpeta}",
    )
    try:
        titulo(f"1. LECTURA de {escala.lineas_lectura:,} lineas")
        lectura = medir_lectura(carpeta, escala, red_argentina())
        imprimir_tabla(lectura, con_memoria_pico=True)
        concluir_lectura(lectura)
        resultados["lectura"] = lectura

        titulo(f"2. ESCRITURA de {escala.lineas_escritura:,} lineas")
        escritura = medir_escritura(carpeta, escala)
        imprimir_tabla(escritura)
        print("  Cada apertura es una llamada al sistema operativo; el buffer")
        print("  junta miles de lineas en una sola escritura a disco.")
        resultados["escritura"] = escritura

        titulo(
            f"3. TUBERIA COMPLETA: {escala.consultas_tuberia:,} consultas, "
            "mapa argentino"
        )
        tuberias, iguales = medir_tuberias(carpeta, escala)
        imprimir_tabla(tuberias)
        print(f"  Las cuatro salidas son identicas byte a byte: {iguales}")
        concluir_tuberias(tuberias)
        resultados["tuberias"] = {"filas": tuberias, "iguales": iguales}

        titulo(
            f"4. PARALELO: {escala.consultas_paralelo:,} consultas distintas, "
            f"grilla de {escala.lado_paralelo**2:,} nodos"
        )
        paralelo, iguales = medir_paralelo(carpeta, escala)
        imprimir_tabla(paralelo)
        print(f"  Todas las salidas son identicas: {iguales}")
        concluir_paralelo(paralelo)
        resultados["paralelo"] = {"filas": paralelo, "iguales": iguales}

        titulo(f"5. BASE DE DATOS: {escala.filas_sqlite:,} filas en SQLite")
        sqlite, correctas = medir_sqlite(
            carpeta, escala, carpeta / "resultados_v2.txt"
        )
        imprimir_tabla(sqlite)
        print(f"  Cantidad de filas verificada: {correctas}")
        print("  Cada commit fuerza a SQLite a asegurar los datos en disco.")
        resultados["sqlite"] = {"filas": sqlite, "correctas": correctas}
    finally:
        if "--conservar" not in sys.argv:
            shutil.rmtree(carpeta, ignore_errors=True)

    # el modo rapido no pisa las mediciones completas del informe
    guardar_json(SALIDA_RAPIDA if rapido else SALIDA, resultados)


if __name__ == "__main__":
    main()
