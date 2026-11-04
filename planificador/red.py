"""Red de rutas: grafo no dirigido con pesos, en lista de adyacencia.

Se usa lista y no matriz porque la red es dispersa: ocupa O(V + E) de
memoria contra O(V^2), y recorrer los vecinos de un nodo, que es lo unico
que piden Dijkstra y A*, es la operacion barata.
"""

from __future__ import annotations

import math
import random
from collections.abc import Hashable, Sequence
from functools import partial
from itertools import pairwise

Nodo = Hashable
"""Identificador de un nodo: nombre de ciudad (str) o numero (int)."""


# [EXPO 5] Docstring estilo Google, con ejemplo ejecutable y tipos.
class Red:
    """Grafo no dirigido con pesos.

    Attributes:
        nombre: Descripcion corta que aparece en ``repr``.
        adyacencia: Diccionario ``nodo -> [(vecino, peso), ...]``.
        coordenadas: Diccionario ``nodo -> (x, y)`` en unidades del modelo.

    Example:
        >>> red = Red("ejemplo")
        >>> red.agregar_nodo("A", 0, 0)
        >>> red.agregar_nodo("B", 3, 4)
        >>> red.agregar_arista("A", "B", 5.0)
        >>> red.distancia_recta("A", "B")
        5.0
        >>> red
        <Red ejemplo: 2 nodos, 1 tramos>
    """

    def __init__(self, nombre: str = "red") -> None:
        """Crea una red vacia.

        Args:
            nombre: Descripcion corta de la red.
        """
        self.nombre = nombre
        self.adyacencia: dict[Nodo, list[tuple[Nodo, float]]] = {}
        self.coordenadas: dict[Nodo, tuple[float, float]] = {}

    def __contains__(self, nodo: Nodo) -> bool:
        """Indica si el nodo pertenece a la red (``nodo in red``)."""
        return nodo in self.adyacencia

    def agregar_nodo(self, nodo: Nodo, x: float, y: float) -> None:
        """Agrega un nodo con sus coordenadas.

        Args:
            nodo: Identificador del nodo.
            x: Coordenada horizontal.
            y: Coordenada vertical.
        """
        self.adyacencia.setdefault(nodo, [])
        self.coordenadas[nodo] = (x, y)

    def agregar_arista(self, a: Nodo, b: Nodo, peso: float) -> None:
        """Une dos nodos existentes con un tramo en ambos sentidos.

        Args:
            a: Primer extremo.
            b: Segundo extremo.
            peso: Costo de recorrer el tramo.
        """
        self.adyacencia[a].append((b, peso))
        self.adyacencia[b].append((a, peso))

    def cortar_arista(self, a: Nodo, b: Nodo) -> None:
        """Elimina el tramo entre ``a`` y ``b`` y marca el mapa como cambiado.

        Args:
            a: Primer extremo.
            b: Segundo extremo.
        """
        self.adyacencia[a] = [(v, p) for v, p in self.adyacencia[a] if v != b]
        self.adyacencia[b] = [(v, p) for v, p in self.adyacencia[b] if v != a]

    @property
    def nodos(self) -> int:
        """Cantidad de nodos (V)."""
        return len(self.adyacencia)

    @property
    def aristas(self) -> int:
        """Cantidad de tramos (E). Cada tramo aparece dos veces en la lista."""
        return sum(len(v) for v in self.adyacencia.values()) // 2

    def distancia_recta(self, a: Nodo, b: Nodo) -> float:
        """Distancia en linea recta entre dos nodos: la heuristica de A*.

        Es admisible porque todo tramo pesa al menos su linea recta, asi que
        nunca supera el costo real del camino.

        Args:
            a: Nodo de partida.
            b: Nodo de llegada.

        Returns:
            Distancia euclidea entre las coordenadas de ``a`` y ``b``.
        """
        x1, y1 = self.coordenadas[a]
        x2, y2 = self.coordenadas[b]
        return math.hypot(x2 - x1, y2 - y1)

    def peso(self, a: Nodo, b: Nodo) -> float:
        """Peso del tramo directo entre ``a`` y ``b``.

        Args:
            a: Primer extremo.
            b: Segundo extremo.

        Returns:
            El peso del tramo.

        Raises:
            ValueError: Si no existe un tramo directo entre ambos nodos.
        """
        for vecino, peso in self.adyacencia[a]:
            if vecino == b:
                return peso
        raise ValueError(f"La ruta usa un tramo inexistente: {a}-{b}")

    def costo_de_ruta(self, ruta: Sequence[Nodo] | None) -> float:
        """Suma los pesos de una ruta. Sirve para verificar resultados.

        Args:
            ruta: Secuencia de nodos consecutivos.

        Returns:
            El costo total, o 0.0 si la ruta tiene menos de dos nodos.

        Raises:
            ValueError: Si la ruta usa un tramo que no existe, por ejemplo
                porque fue cortado despues de calcularla.
        """
        if not ruta or len(ruta) < 2:
            return 0.0
        return sum(self.peso(a, b) for a, b in pairwise(ruta))

    def __repr__(self) -> str:
        """Resumen de la red con cantidad de nodos y tramos."""
        return (
            f"<Red {self.nombre}: {self.nodos:,} nodos, "
            f"{self.aristas:,} tramos>"
        )


SEPARACION_GRILLA = 10.0
FACTOR_TRAMO = (1.05, 1.35)
FACTOR_AUTOPISTA = (1.05, 1.05)


# [EXPO 8] Refactor "Long Parameter List": el rango va en una tupla.
def _conectar(
    red: Red,
    a: Nodo,
    b: Nodo,
    rng: random.Random,
    factores: tuple[float, float] = FACTOR_TRAMO,
) -> None:
    """Une dos nodos con un peso mayor o igual a su distancia en linea recta.

    Multiplicar la linea recta por un factor >= 1 es lo que mantiene
    admisible la heuristica de A*.

    Args:
        red: Red a modificar.
        a: Primer extremo.
        b: Segundo extremo.
        rng: Generador aleatorio con semilla, para que sea reproducible.
        factores: Rango ``(minimo, maximo)`` del factor que se sortea.
    """
    peso = red.distancia_recta(a, b) * rng.uniform(*factores)
    red.agregar_arista(a, b, peso)


def generar_red(lado: int, semilla: int = 42, autopistas: float = 0.02) -> Red:
    """Grilla de ``lado x lado`` con coordenadas movidas al azar.

    Ademas de los tramos de la grilla agrega algunas autopistas: tramos
    largos entre nodos al azar.

    Args:
        lado: Cantidad de nodos por lado. La red tiene ``lado**2`` nodos.
        semilla: Semilla del generador aleatorio.
        autopistas: Proporcion de autopistas respecto de la cantidad de
            nodos.

    Returns:
        La red generada.

    Example:
        >>> generar_red(10)
        <Red grilla 10x10: 100 nodos, 182 tramos>
    """
    # random alcanza: es una simulacion, no un uso criptografico.
    rng = random.Random(semilla)  # nosec B311
    red = Red(f"grilla {lado}x{lado}")

    for fila in range(lado):
        for columna in range(lado):
            x = columna * SEPARACION_GRILLA + rng.uniform(-3, 3)
            y = fila * SEPARACION_GRILLA + rng.uniform(-3, 3)
            red.agregar_nodo(fila * lado + columna, x, y)

    for fila in range(lado):
        for columna in range(lado):
            actual = fila * lado + columna
            if columna + 1 < lado:
                _conectar(red, actual, actual + 1, rng)
            if fila + 1 < lado:
                _conectar(red, actual, actual + lado, rng)

    total_nodos = lado * lado
    for _ in range(int(total_nodos * autopistas)):
        a = rng.randrange(total_nodos)
        b = rng.randrange(total_nodos)
        if a != b:
            _conectar(red, a, b, rng, FACTOR_AUTOPISTA)

    return red


CIUDADES = {
    "Buenos Aires": (-34.61, -58.38),
    "La Plata": (-34.92, -57.95),
    "Mar del Plata": (-38.00, -57.56),
    "Bahia Blanca": (-38.72, -62.27),
    "Rosario": (-32.95, -60.66),
    "Santa Fe": (-31.63, -60.70),
    "Cordoba": (-31.42, -64.18),
    "Rio Cuarto": (-33.12, -64.35),
    "Mendoza": (-32.89, -68.84),
    "San Juan": (-31.54, -68.53),
    "San Luis": (-33.30, -66.34),
    "Santiago del Estero": (-27.78, -64.26),
    "Tucuman": (-26.82, -65.22),
    "Salta": (-24.79, -65.41),
    "Resistencia": (-27.45, -58.99),
    "Corrientes": (-27.47, -58.83),
    "Posadas": (-27.36, -55.90),
    "Parana": (-31.73, -60.53),
    "Neuquen": (-38.95, -68.06),
    "Bariloche": (-41.13, -71.31),
    "Comodoro Rivadavia": (-45.86, -67.50),
    "Trelew": (-43.25, -65.31),
    "Rio Gallegos": (-51.62, -69.22),
    "Ushuaia": (-54.80, -68.30),
}
"""Ciudades del mapa didactico: nombre -> (latitud, longitud)."""

KM_POR_GRADO = 111.0
FACTOR_RUTA_ARGENTINA = (1.10, 1.45)


def red_argentina(vecinos: int = 3, semilla: int = 7) -> Red:
    """Modelo didactico de ciudades argentinas y conexiones simuladas.

    Cada ciudad se une con sus ``vecinos`` mas cercanas. Las coordenadas
    parten de latitud y longitud, pero no reemplazan una red vial ni
    producen distancias oficiales por carretera.

    Args:
        vecinos: Cantidad de ciudades cercanas con las que se une cada una.
        semilla: Semilla del generador aleatorio.

    Returns:
        La red de 24 ciudades.

    Example:
        >>> red_argentina()
        <Red ciudades argentinas: 24 nodos, 45 tramos>
    """
    rng = random.Random(semilla)  # nosec B311
    red = Red("ciudades argentinas")

    for nombre, (latitud, longitud) in CIUDADES.items():
        red.agregar_nodo(
            nombre, longitud * KM_POR_GRADO, latitud * KM_POR_GRADO
        )

    conectadas: set[tuple[str, str]] = set()
    for ciudad in CIUDADES:
        cercanas = sorted(
            (otra for otra in CIUDADES if otra != ciudad),
            key=partial(red.distancia_recta, ciudad),
        )
        for vecina in cercanas[:vecinos]:
            a, b = sorted((ciudad, vecina))
            par = (a, b)
            if par not in conectadas:
                conectadas.add(par)
                _conectar(red, ciudad, vecina, rng, FACTOR_RUTA_ARGENTINA)

    return red
