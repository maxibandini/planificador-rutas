"""Entrada y salida de archivos grandes de consultas.

Una empresa de logistica recibe cada dia un archivo con millones de
pedidos de ruta y tiene que devolver otro archivo con los resultados.
Este modulo resuelve ese flujo como una tuberia de generadores::

    leer  ->  resolver  ->  escribir

Cada etapa se puede cambiar por separado, y asi se mide el efecto de
cada tecnica de E/S de la unidad 5:

* **Streaming**: leer linea a linea con un generador en lugar de
  ``readlines()``. La memoria queda acotada, no crece con el archivo.
* **Buffer**: abrir el archivo una vez y dejar que el buffer agrupe las
  escrituras, en lugar de abrir y cerrar por cada linea.
* **Batching**: procesar y escribir de a lotes (``writelines``), y en la
  base de datos insertar con ``executemany`` y un commit por lote.
* **Paralelismo**: repartir los lotes entre procesos, con una ventana
  acotada de lotes en vuelo para no cargar todo el archivo en memoria.

Formato de entrada: una consulta por linea, ``origen;destino``.
Formato de salida: ``origen;destino;costo;nodos_en_ruta``.
"""

from __future__ import annotations

import sqlite3
from collections import deque
from collections.abc import Iterable, Iterator
from contextlib import closing
from itertools import islice
from pathlib import Path
from typing import IO

from planificador.algoritmos import Resultado, a_estrella
from planificador.cache import CacheDeRutas
from planificador.concurrencia import NUCLEOS, crear_pool
from planificador.red import Nodo, Red

Ruta = str | Path
ConsultaTexto = tuple[str, str]
FilaResultado = tuple[str, str, float, int]

SEPARADOR = ";"
CODIFICACION_ENTRADA = "utf-8-sig"
"""UTF-8 que ignora el BOM que agregan el Bloc de notas y Excel."""

TAMANIO_LOTE = 10_000
BUFFER_GRANDE = 1024 * 1024
"""Buffer de escritura de 1 MiB. El de Python por defecto es de 8 KiB."""

VENTANA_POR_TRABAJADOR = 2
"""Lotes en vuelo por proceso en el modo paralelo (memoria acotada)."""

CAPACIDAD_CACHE = 100_000


def _controlar_lote(tamanio: int) -> None:
    """Lanza ``ValueError`` si el tamanio de lote no es positivo."""
    if tamanio <= 0:
        raise ValueError("El tamanio de lote tiene que ser positivo")


# [EXPO 4] BATCHING: agrupa cualquier iterable en lotes, sin cargar todo.
def en_lotes[T](elementos: Iterable[T], tamanio: int) -> Iterator[list[T]]:
    """Agrupa cualquier iterable en listas de ``tamanio`` elementos.

    Es perezoso: solo tiene en memoria el lote actual, asi que sirve para
    archivos que no entran en memoria.

    Args:
        elementos: Iterable de origen, por ejemplo las lineas de un archivo.
        tamanio: Elementos por lote. El ultimo lote puede ser mas chico.

    Yields:
        Listas de hasta ``tamanio`` elementos.

    Raises:
        ValueError: Si ``tamanio`` no es positivo.

    Example:
        >>> mensajes = [f"msg_{i}" for i in range(1, 28)]
        >>> lotes = list(en_lotes(mensajes, 5))
        >>> len(lotes), lotes[-1]
        (6, ['msg_26', 'msg_27'])
    """
    _controlar_lote(tamanio)
    iterador = iter(elementos)
    while lote := list(islice(iterador, tamanio)):
        yield lote


def formatear_consulta(origen: Nodo, destino: Nodo) -> str:
    r"""Linea de texto de una consulta.

    Example:
        >>> formatear_consulta("Ushuaia", "Salta")
        'Ushuaia;Salta\n'
    """
    return f"{origen}{SEPARADOR}{destino}\n"


def parsear_consulta(linea: str) -> ConsultaTexto:
    r"""Separa una linea ``origen;destino`` en sus dos partes.

    Args:
        linea: Linea leida del archivo, con o sin salto de linea.

    Returns:
        Tupla ``(origen, destino)`` como texto, sin espacios alrededor.

    Raises:
        ValueError: Si la linea no tiene exactamente dos campos.

    Example:
        >>> parsear_consulta("Ushuaia;Salta\n")
        ('Ushuaia', 'Salta')
        >>> parsear_consulta(" Ushuaia ; Salta \r\n")
        ('Ushuaia', 'Salta')
    """
    campos = [campo.strip() for campo in linea.split(SEPARADOR)]
    if len(campos) != 2:
        raise ValueError(f"Linea mal formada: {linea!r}")
    return campos[0], campos[1]


def formatear_resultado(
    origen: str, destino: str, resultado: Resultado | None
) -> str:
    r"""Linea de texto con el resultado de una consulta.

    Args:
        origen: Origen tal como vino en el archivo.
        destino: Destino tal como vino en el archivo.
        resultado: Resultado de la busqueda, o ``None`` si alguna ciudad
            no existe en el mapa.

    Returns:
        Linea ``origen;destino;costo;nodos_en_ruta``. Si no hay ruta, el
        costo es ``inf`` y la cantidad de nodos es 0.

    Example:
        >>> formatear_resultado("A", "B", Resultado(["A", "B"], 12.3456, 2))
        'A;B;12.346;2\n'
        >>> formatear_resultado("A", "Atlantida", None)
        'A;Atlantida;inf;0\n'
    """
    if resultado is None or resultado.ruta is None:
        return f"{origen}{SEPARADOR}{destino}{SEPARADOR}inf{SEPARADOR}0\n"
    return (
        f"{origen}{SEPARADOR}{destino}{SEPARADOR}"
        f"{resultado.costo:.3f}{SEPARADOR}{len(resultado.ruta)}\n"
    )


def parsear_resultado(linea: str) -> FilaResultado:
    r"""Convierte una linea de resultado en una fila para la base de datos.

    Example:
        >>> parsear_resultado("A;B;12.346;2\n")
        ('A', 'B', 12.346, 2)
    """
    origen, destino, costo, nodos = linea.rstrip("\r\n").split(SEPARADOR)
    return origen, destino, float(costo), int(nodos)


# --------------------------------------------------------------- lectura


def _parsear_lineas(
    lineas: Iterable[str], ruta: Ruta
) -> Iterator[ConsultaTexto]:
    """Parsea lineas de consultas, salteando las vacias.

    Raises:
        ValueError: Si una linea esta mal formada o el archivo no esta en
            UTF-8. El mensaje dice el archivo y el numero de linea, para
            encontrarla aunque haya millones.
    """
    numero = 0
    try:
        for numero, linea in enumerate(lineas, start=1):
            if not linea.strip():
                continue
            try:
                consulta = parsear_consulta(linea)
            except ValueError as error:
                raise ValueError(f"{ruta}, linea {numero}: {error}") from error
            yield consulta
    except UnicodeDecodeError as error:
        raise ValueError(
            f"{ruta}, linea {numero + 1}: el archivo no esta en UTF-8"
        ) from error


# [EXPO 4] Ingenua: readlines() carga el archivo entero en memoria.
def leer_todo(ruta: Ruta) -> list[ConsultaTexto]:
    """Lee el archivo entero con ``readlines()``. Version ingenua.

    Tiene en memoria todas las lineas a la vez: el consumo crece con el
    tamanio del archivo. Se conserva para compararla.

    Args:
        ruta: Archivo de consultas.

    Returns:
        Lista con todas las consultas.
    """
    try:
        with open(ruta, encoding=CODIFICACION_ENTRADA) as archivo:
            lineas = archivo.readlines()
    except UnicodeDecodeError as error:
        raise ValueError(f"{ruta}: el archivo no esta en UTF-8") from error
    return list(_parsear_lineas(lineas, ruta))


# [EXPO 4] STREAMING: generador, la memoria no crece con el archivo.
def leer_consultas(ruta: Ruta) -> Iterator[ConsultaTexto]:
    """Lee el archivo linea a linea (streaming).

    Iterar sobre el objeto archivo ya usa el buffer de lectura de Python:
    lee bloques del disco y entrega una linea por vez.

    Args:
        ruta: Archivo de consultas.

    Yields:
        Una consulta ``(origen, destino)`` por linea no vacia.
    """
    with open(ruta, encoding=CODIFICACION_ENTRADA) as archivo:
        yield from _parsear_lineas(archivo, ruta)


def leer_consultas_por_lotes(
    ruta: Ruta, tamanio_lote: int = TAMANIO_LOTE
) -> Iterator[list[ConsultaTexto]]:
    """Lee el archivo en lotes de ``tamanio_lote`` consultas.

    Args:
        ruta: Archivo de consultas.
        tamanio_lote: Consultas por lote.

    Yields:
        Listas de consultas.
    """
    return en_lotes(leer_consultas(ruta), tamanio_lote)


def leer_resultados(ruta: Ruta) -> Iterator[FilaResultado]:
    """Lee un archivo de resultados linea a linea.

    Args:
        ruta: Archivo generado por alguna de las escrituras.

    Yields:
        Filas ``(origen, destino, costo, nodos_en_ruta)``.
    """
    with open(ruta, encoding=CODIFICACION_ENTRADA) as archivo:
        for linea in archivo:
            if linea.strip():
                yield parsear_resultado(linea)


# --------------------------------------------------------------- calculo


def resolver_consultas(
    red: Red,
    consultas: Iterable[ConsultaTexto],
    cache: CacheDeRutas | None = None,
) -> Iterator[str]:
    """Resuelve cada consulta y entrega la linea de resultado.

    Es un generador: calcula una consulta recien cuando quien escribe pide
    la siguiente linea.

    Args:
        red: Mapa.
        consultas: Pares ``(origen, destino)`` como texto.
        cache: Cache de rutas opcional. Sin cache, las consultas repetidas
            se vuelven a calcular.

    Yields:
        Una linea de resultado por consulta, en el mismo orden.
    """
    nodos = {str(nodo): nodo for nodo in red.adyacencia}
    for origen, destino in consultas:
        nodo_origen = nodos.get(origen)
        nodo_destino = nodos.get(destino)
        if nodo_origen is None or nodo_destino is None:
            yield formatear_resultado(origen, destino, None)
            continue
        if cache is None:
            resultado = a_estrella(red, nodo_origen, nodo_destino)
        else:
            resultado = cache.consultar(nodo_origen, nodo_destino)
        yield formatear_resultado(origen, destino, resultado)


# ------------------------------------------------------------- escritura


def _abrir_salida(ruta: Ruta, modo: str = "w", buffer: int = -1) -> IO[str]:
    r"""Abre un archivo de salida siempre con el mismo formato.

    ``newline="\n"`` evita que Windows escriba ``\r\n``: asi todas las
    estrategias generan archivos identicos byte a byte.
    """
    return open(ruta, modo, encoding="utf-8", newline="\n", buffering=buffer)


# [EXPO 4] Ingenua: abre y cierra el archivo por cada linea.
def escribir_abriendo_por_linea(ruta: Ruta, lineas: Iterable[str]) -> int:
    """Abre, escribe y cierra el archivo por cada linea. Version ingenua.

    Cada apertura y cierre es una llamada al sistema operativo, y cerrar
    obliga a vaciar el buffer: no hay ningun agrupamiento.

    Args:
        ruta: Archivo de salida. Se vacia antes de empezar.
        lineas: Lineas a escribir.

    Returns:
        Cantidad de lineas escritas.
    """
    _abrir_salida(ruta).close()
    escritas = 0
    for linea in lineas:
        with _abrir_salida(ruta, "a") as archivo:
            archivo.write(linea)
        escritas += 1
    return escritas


# [EXPO 4] BUFFER: una sola apertura; el buffer junta las escrituras.
def escribir_con_buffer(
    ruta: Ruta, lineas: Iterable[str], buffer: int = BUFFER_GRANDE
) -> int:
    """Abre el archivo una vez y escribe linea a linea sobre el buffer.

    Args:
        ruta: Archivo de salida.
        lineas: Lineas a escribir.
        buffer: Tamanio del buffer en bytes.

    Returns:
        Cantidad de lineas escritas.
    """
    escritas = 0
    with _abrir_salida(ruta, buffer=buffer) as archivo:
        for linea in lineas:
            archivo.write(linea)
            escritas += 1
    return escritas


# [EXPO 4] BATCHING: un solo writelines por lote.
def escribir_por_lotes(
    ruta: Ruta,
    lineas: Iterable[str],
    tamanio_lote: int = TAMANIO_LOTE,
    buffer: int = BUFFER_GRANDE,
) -> int:
    """Escribe de a lotes: una sola llamada ``writelines`` por lote.

    Args:
        ruta: Archivo de salida.
        lineas: Lineas a escribir.
        tamanio_lote: Lineas por lote.
        buffer: Tamanio del buffer en bytes.

    Returns:
        Cantidad de lineas escritas.
    """
    _controlar_lote(tamanio_lote)
    escritas = 0
    with _abrir_salida(ruta, buffer=buffer) as archivo:
        for lote in en_lotes(lineas, tamanio_lote):
            archivo.writelines(lote)
            escritas += len(lote)
    return escritas


def escribir_consultas(
    ruta: Ruta,
    consultas: Iterable[tuple[Nodo, Nodo]],
    tamanio_lote: int = TAMANIO_LOTE,
) -> int:
    """Genera un archivo de consultas, por lotes y con buffer grande.

    Args:
        ruta: Archivo a crear.
        consultas: Pares ``(origen, destino)``.
        tamanio_lote: Lineas por lote.

    Returns:
        Cantidad de consultas escritas.
    """
    lineas = (
        formatear_consulta(origen, destino) for origen, destino in consultas
    )
    return escribir_por_lotes(ruta, lineas, tamanio_lote)


# --------------------------------------------------- tuberias completas


def _validar_rutas(entrada: Ruta, salida: Ruta) -> None:
    """Controla las rutas antes de abrir la salida, que se sobrescribe.

    Raises:
        FileNotFoundError: Si la entrada no existe.
        ValueError: Si entrada y salida son el mismo archivo: al abrir la
            salida se borraria la entrada antes de leerla.
    """
    entrada, salida = Path(entrada), Path(salida)
    if not entrada.is_file():
        raise FileNotFoundError(f"No existe el archivo de entrada: {entrada}")
    if salida.exists() and entrada.resolve() == salida.resolve():
        raise ValueError(
            "La entrada y la salida no pueden ser el mismo archivo"
        )


# [EXPO 4] Tuberia completa en 4 versiones, de V0 (peor) a V3 (mejor).
def procesar_ingenuo(red: Red, entrada: Ruta, salida: Ruta) -> int:
    """Todo en memoria, sin cache y abriendo la salida por cada linea.

    Args:
        red: Mapa.
        entrada: Archivo de consultas.
        salida: Archivo de resultados.

    Returns:
        Cantidad de consultas procesadas.
    """
    _validar_rutas(entrada, salida)
    consultas = leer_todo(entrada)
    return escribir_abriendo_por_linea(
        salida, resolver_consultas(red, consultas)
    )


def procesar_streaming(red: Red, entrada: Ruta, salida: Ruta) -> int:
    """Lectura linea a linea y escritura con buffer. Todavia sin cache.

    Args:
        red: Mapa.
        entrada: Archivo de consultas.
        salida: Archivo de resultados.

    Returns:
        Cantidad de consultas procesadas.
    """
    _validar_rutas(entrada, salida)
    return escribir_con_buffer(
        salida, resolver_consultas(red, leer_consultas(entrada))
    )


def procesar_por_lotes(
    red: Red,
    entrada: Ruta,
    salida: Ruta,
    tamanio_lote: int = TAMANIO_LOTE,
) -> int:
    """Streaming, cache de rutas y escritura de a lotes.

    Args:
        red: Mapa.
        entrada: Archivo de consultas.
        salida: Archivo de resultados.
        tamanio_lote: Lineas por lote de escritura.

    Returns:
        Cantidad de consultas procesadas.
    """
    _validar_rutas(entrada, salida)
    cache = CacheDeRutas(red, capacidad=CAPACIDAD_CACHE)
    lineas = resolver_consultas(red, leer_consultas(entrada), cache)
    return escribir_por_lotes(salida, lineas, tamanio_lote)


# Cada proceso hijo tiene su propia cache (con su copia del mapa): no se
# comparten entre procesos, asi que no hacen falta locks.
# Sin valor inicial: lo asigna el initializer al arrancar cada proceso.
_cache_del_trabajador: CacheDeRutas  # pylint: disable=C0103


def _iniciar_trabajador_de_archivos(red: Red) -> None:
    """Initializer del pool: crea la cache propia de cada proceso."""
    # Un global por proceso hijo es el patron del initializer del pool.
    # pylint: disable-next=global-statement
    global _cache_del_trabajador
    _cache_del_trabajador = CacheDeRutas(red, capacidad=CAPACIDAD_CACHE)


def _resolver_lote_en_proceso(lote: list[ConsultaTexto]) -> str:
    """Resuelve un lote en un proceso hijo.

    Devuelve todo el lote ya formateado como un unico ``str``: es mucho
    mas barato de serializar entre procesos que miles de tuplas.
    """
    cache = _cache_del_trabajador
    return "".join(resolver_consultas(cache.red, lote, cache))


# [EXPO 4] PARALELO: lotes repartidos en procesos, ventana acotada.
def procesar_en_paralelo(
    red: Red,
    entrada: Ruta,
    salida: Ruta,
    tamanio_lote: int = TAMANIO_LOTE,
    trabajadores: int = NUCLEOS,
) -> int:
    """Reparte los lotes entre procesos y escribe en el orden original.

    ``Executor.map`` consume todo el iterable de entrada antes de empezar,
    lo que cargaria el archivo entero en memoria. Por eso los lotes se
    envian con ``submit`` y se mantiene una ventana acotada de lotes en
    vuelo: se lee el siguiente recien cuando se escribio uno.

    Args:
        red: Mapa que recibe cada proceso.
        entrada: Archivo de consultas.
        salida: Archivo de resultados.
        tamanio_lote: Consultas por lote enviado a un proceso.
        trabajadores: Cantidad de procesos.

    Returns:
        Cantidad de consultas procesadas.
    """
    _validar_rutas(entrada, salida)
    _controlar_lote(tamanio_lote)
    limite_en_vuelo = trabajadores * VENTANA_POR_TRABAJADOR
    procesadas = 0
    en_vuelo: deque = deque()
    pool = crear_pool(red, trabajadores, _iniciar_trabajador_de_archivos)
    with pool, _abrir_salida(salida, buffer=BUFFER_GRANDE) as archivo:
        for lote in leer_consultas_por_lotes(entrada, tamanio_lote):
            en_vuelo.append(pool.submit(_resolver_lote_en_proceso, lote))
            procesadas += len(lote)
            if len(en_vuelo) >= limite_en_vuelo:
                archivo.write(en_vuelo.popleft().result())
        while en_vuelo:
            archivo.write(en_vuelo.popleft().result())
    return procesadas


# --------------------------------------------------------- base de datos

_CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS resultados (
    origen TEXT NOT NULL,
    destino TEXT NOT NULL,
    costo REAL NOT NULL,
    nodos_en_ruta INTEGER NOT NULL
)
"""
_INSERTAR = "INSERT INTO resultados VALUES (?, ?, ?, ?)"


# [EXPO 4] BATCHING en base de datos: commit por fila vs por lote.
def guardar_en_sqlite_uno_a_uno(
    ruta_base: Ruta, filas: Iterable[FilaResultado]
) -> int:
    """Inserta fila por fila con un commit por cada una. Version ingenua.

    Cada commit obliga a SQLite a asegurar los datos en disco.

    Args:
        ruta_base: Archivo de la base SQLite.
        filas: Filas a insertar.

    Returns:
        Cantidad de filas insertadas.
    """
    insertadas = 0
    with closing(sqlite3.connect(ruta_base)) as conexion:
        conexion.execute(_CREAR_TABLA)
        for fila in filas:
            conexion.execute(_INSERTAR, fila)
            conexion.commit()
            insertadas += 1
    return insertadas


def guardar_en_sqlite_por_lotes(
    ruta_base: Ruta,
    filas: Iterable[FilaResultado],
    tamanio_lote: int = 1000,
) -> int:
    """Inserta de a lotes con ``executemany`` y un commit por lote.

    Args:
        ruta_base: Archivo de la base SQLite.
        filas: Filas a insertar.
        tamanio_lote: Filas por lote.

    Returns:
        Cantidad de filas insertadas.
    """
    insertadas = 0
    with closing(sqlite3.connect(ruta_base)) as conexion:
        conexion.execute(_CREAR_TABLA)
        for lote in en_lotes(filas, tamanio_lote):
            conexion.executemany(_INSERTAR, lote)
            conexion.commit()
            insertadas += len(lote)
    return insertadas


def contar_filas(ruta_base: Ruta) -> int:
    """Cantidad de filas guardadas en la tabla de resultados."""
    with closing(sqlite3.connect(ruta_base)) as conexion:
        (cantidad,) = conexion.execute(
            "SELECT COUNT(*) FROM resultados"
        ).fetchone()
    return cantidad
