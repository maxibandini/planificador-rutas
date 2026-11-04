"""Busqueda de rutas. V = nodos, E = tramos.

====================  ================  ===================================
Algoritmo             Complejidad       Comentario
====================  ================  ===================================
``bfs``               O(V + E)          minimiza tramos, no distancia
``dijkstra_lista``    O(V^2)            V vueltas x V para hallar el minimo
``dijkstra_heap``     O((V+E) log V)    el minimo sale del heap en O(log V)
``a_estrella``        O((V+E) log V)    misma cota, explora mucho menos
====================  ================  ===================================

En el primer parcial ``dijkstra_heap`` y ``a_estrella`` eran dos funciones
casi identicas. Ahora comparten :func:`_busqueda_con_heap`: Dijkstra es A*
con una heuristica que siempre vale cero.
"""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Callable
from math import inf
from typing import NamedTuple

from planificador.red import Nodo, Red


class Resultado(NamedTuple):
    """Resultado de una busqueda.

    Attributes:
        ruta: Nodos desde el origen hasta el destino, o ``None`` si no hay
            camino.
        costo: Suma de los pesos de la ruta, o ``inf`` si no hay camino.
        explorados: Nodos que el algoritmo saco de la frontera. Mide cuanto
            trabajo hizo, independientemente del equipo.
    """

    ruta: list[Nodo] | None
    costo: float
    explorados: int


Algoritmo = Callable[[Red, Nodo, Nodo], Resultado]
Heuristica = Callable[[Nodo, Nodo], float]


def _reconstruir(previo: dict[Nodo, Nodo | None], destino: Nodo) -> list:
    """Arma la ruta recorriendo los predecesores desde el destino."""
    ruta = [destino]
    while previo[ruta[-1]] is not None:
        ruta.append(previo[ruta[-1]])
    ruta.reverse()
    return ruta


def bfs(red: Red, origen: Nodo, destino: Nodo) -> Resultado:
    """Ruta con la MENOR CANTIDAD DE TRAMOS. Ignora los pesos.

    Es O(V + E) porque cada nodo entra una sola vez a la cola y cada tramo
    se mira una vez por extremo.

    Args:
        red: Red donde buscar.
        origen: Nodo de partida.
        destino: Nodo de llegada.

    Returns:
        La ruta encontrada, su costo real y los nodos explorados.
    """
    if origen == destino:
        return Resultado([origen], 0.0, 0)

    previo: dict[Nodo, Nodo | None] = {origen: None}
    cola = deque([origen])
    explorados = 0

    while cola:
        actual = cola.popleft()
        explorados += 1
        if actual == destino:
            ruta = _reconstruir(previo, destino)
            return Resultado(ruta, red.costo_de_ruta(ruta), explorados)
        for vecino, _ in red.adyacencia[actual]:
            if vecino not in previo:
                previo[vecino] = actual
                cola.append(vecino)

    return Resultado(None, inf, explorados)


# Baseline O(V^2): el min() de abajo es el cuello de botella.
def dijkstra_lista(red: Red, origen: Nodo, destino: Nodo) -> Resultado:
    """Dijkstra que busca el pendiente mas cercano recorriendo todos.

    Es la implementacion inicial (baseline) del primer parcial. El
    cuello de botella es ``min()``: O(V) por vuelta y V vueltas, O(V^2).

    Args:
        red: Red donde buscar.
        origen: Nodo de partida.
        destino: Nodo de llegada.

    Returns:
        La ruta optima, su costo y los nodos explorados.
    """
    distancia = dict.fromkeys(red.adyacencia, inf)
    distancia[origen] = 0.0
    previo: dict[Nodo, Nodo | None] = {origen: None}
    pendientes = set(red.adyacencia)
    explorados = 0

    while pendientes:
        # cuello de botella: recorre todos los pendientes en cada vuelta
        actual = min(pendientes, key=lambda nodo: distancia[nodo])
        if distancia[actual] == inf:
            break
        pendientes.discard(actual)
        explorados += 1

        if actual == destino:
            ruta = _reconstruir(previo, destino)
            return Resultado(ruta, distancia[destino], explorados)

        for vecino, peso in red.adyacencia[actual]:
            if vecino in pendientes:
                candidata = distancia[actual] + peso
                if candidata < distancia[vecino]:
                    distancia[vecino] = candidata
                    previo[vecino] = actual

    return Resultado(None, inf, explorados)


def _sin_heuristica(_nodo: Nodo, _destino: Nodo) -> float:
    """Heuristica nula: convierte A* en Dijkstra."""
    return 0.0


# Codigo redundante: Dijkstra y A* ahora comparten esta funcion.
def _busqueda_con_heap(
    red: Red, origen: Nodo, destino: Nodo, heuristica: Heuristica
) -> Resultado:
    """Busqueda de costo minimo con cola de prioridad.

    Prioriza por ``f(n) = g(n) + h(n)``: lo recorrido mas una estimacion
    de lo que falta. Con ``h = 0`` es Dijkstra. Con una ``h`` admisible
    sigue siendo optima y explora menos nodos.

    Las entradas viejas del heap no se borran (no hay ``decrease-key`` en
    ``heapq``): se descartan al salir si el nodo ya fue visitado.

    Args:
        red: Red donde buscar.
        origen: Nodo de partida.
        destino: Nodo de llegada.
        heuristica: Funcion ``h(nodo, destino)`` que nunca sobreestima.

    Returns:
        La ruta optima, su costo y los nodos explorados.
    """
    costo_hasta: dict[Nodo, float] = {origen: 0.0}
    previo: dict[Nodo, Nodo | None] = {origen: None}
    frontera = [(heuristica(origen, destino), 0.0, origen)]
    visitados: set[Nodo] = set()
    explorados = 0

    while frontera:
        _, costo_actual, actual = heapq.heappop(frontera)
        if actual in visitados:
            continue
        visitados.add(actual)
        explorados += 1

        if actual == destino:
            ruta = _reconstruir(previo, destino)
            return Resultado(ruta, costo_actual, explorados)

        for vecino, peso in red.adyacencia[actual]:
            if vecino in visitados:
                continue
            candidata = costo_actual + peso
            if candidata < costo_hasta.get(vecino, inf):
                costo_hasta[vecino] = candidata
                previo[vecino] = actual
                # Calculo repetido que NO eliminamos: memoizar h
                # fue 0-10 % mas lento (el dict cuesta lo mismo que hypot).
                prioridad = candidata + heuristica(vecino, destino)
                heapq.heappush(frontera, (prioridad, candidata, vecino))

    return Resultado(None, inf, explorados)


# Dijkstra = A* con heuristica cero: una linea cada uno.
def dijkstra_heap(red: Red, origen: Nodo, destino: Nodo) -> Resultado:
    """Dijkstra con heap: el minimo sale en O(log V) en vez de O(V).

    Args:
        red: Red donde buscar.
        origen: Nodo de partida.
        destino: Nodo de llegada.

    Returns:
        La ruta optima, su costo y los nodos explorados.
    """
    return _busqueda_con_heap(red, origen, destino, _sin_heuristica)


def a_estrella(red: Red, origen: Nodo, destino: Nodo) -> Resultado:
    """A*: Dijkstra guiado por la distancia en linea recta al destino.

    Args:
        red: Red donde buscar.
        origen: Nodo de partida.
        destino: Nodo de llegada.

    Returns:
        La ruta optima, su costo y los nodos explorados.

    Example:
        >>> from planificador.red import red_argentina
        >>> resultado = a_estrella(red_argentina(), "Ushuaia", "Salta")
        >>> resultado.ruta[0], resultado.ruta[-1], round(resultado.costo)
        ('Ushuaia', 'Salta', 4819)
    """
    return _busqueda_con_heap(red, origen, destino, red.distancia_recta)


ALGORITMOS: dict[str, Algoritmo] = {
    "BFS": bfs,
    "Dijkstra lista": dijkstra_lista,
    "Dijkstra heap": dijkstra_heap,
    "A*": a_estrella,
}
"""Algoritmos disponibles, por nombre para mostrar."""

COMPLEJIDADES = {
    "BFS": "O(V + E)",
    "Dijkstra lista": "O(V^2)",
    "Dijkstra heap": "O((V+E) log V)",
    "A*": "O((V+E) log V)",
}
"""Complejidad temporal de cada algoritmo, en el peor caso."""
