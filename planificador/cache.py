"""Reutilizacion de rutas ya calculadas.

Memoizacion: guarda por argumentos y no se entera si cambia el mapa.
Caching: guarda y ademas invalida las rutas que usaban el tramo cortado.
La cache descarta por LRU. No tiene TTL: un corte de ruta es un evento,
no algo que vence con el tiempo.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import pairwise

from planificador.algoritmos import Algoritmo, Resultado, a_estrella
from planificador.red import Nodo, Red

Clave = tuple[Nodo, Nodo]
Tramo = tuple[Nodo, Nodo]


def clave_de_tramo(a: Nodo, b: Nodo) -> Tramo:
    """Clave de un tramo, sin importar el sentido en que se recorra.

    Args:
        a: Un extremo.
        b: El otro extremo.

    Returns:
        La tupla ordenada de los dos extremos.

    Example:
        >>> clave_de_tramo("Salta", "Cordoba")
        ('Cordoba', 'Salta')
        >>> clave_de_tramo("Cordoba", "Salta")
        ('Cordoba', 'Salta')
    """
    return (a, b) if str(a) <= str(b) else (b, a)


# [EXPO 8] Refactor "Large Class": los contadores pasan a un dataclass.
@dataclass
class Contadores:
    """Contadores de actividad de la cache.

    Attributes:
        aciertos: Consultas respondidas desde la cache.
        fallos: Consultas que hubo que calcular.
        invalidadas: Rutas borradas porque usaban un tramo cortado.
        descartadas: Rutas borradas por falta de lugar (LRU).
    """

    aciertos: int = 0
    fallos: int = 0
    invalidadas: int = 0
    descartadas: int = 0

    @property
    def consultas(self) -> int:
        """Total de consultas: aciertos mas fallos."""
        return self.aciertos + self.fallos

    @property
    def tasa_aciertos(self) -> float:
        """Proporcion de consultas respondidas desde la cache."""
        return self.aciertos / self.consultas if self.consultas else 0.0


class CacheDeRutas:
    """Cache de rutas con invalidacion selectiva por tramo y politica LRU.

    Ademas de las rutas guarda un indice invertido ``tramo -> rutas que lo
    usan``. Cuando se corta un tramo, el indice dice exactamente que rutas
    borrar, sin recorrer toda la cache.

    No es segura para varios hilos: quien la comparta debe protegerla con
    un lock (ver :mod:`planificador.api`).

    Example:
        >>> from planificador.red import red_argentina
        >>> cache = CacheDeRutas(red_argentina())
        >>> _ = cache.consultar("Ushuaia", "Salta")
        >>> _ = cache.consultar("Ushuaia", "Salta")
        >>> cache
        <CacheDeRutas 1/1000 rutas, 50% de aciertos>
    """

    def __init__(
        self,
        red: Red,
        capacidad: int = 1000,
        algoritmo: Algoritmo = a_estrella,
    ) -> None:
        """Crea una cache vacia.

        Args:
            red: Red sobre la que se calculan las rutas.
            capacidad: Cantidad maxima de rutas guardadas.
            algoritmo: Funcion de busqueda que se usa en los fallos.
        """
        self.red = red
        self.capacidad = capacidad
        self.algoritmo = algoritmo
        self.contadores = Contadores()
        self._rutas: OrderedDict[Clave, Resultado] = OrderedDict()
        self._por_tramo: dict[Tramo, set[Clave]] = {}

    def __contains__(self, clave: Clave) -> bool:
        """Indica si la ruta ``(origen, destino)`` esta guardada."""
        return clave in self._rutas

    def __len__(self) -> int:
        """Cantidad de rutas guardadas."""
        return len(self._rutas)

    def consultar(self, origen: Nodo, destino: Nodo) -> Resultado:
        """Devuelve la ruta, desde la cache si esta o calculandola si no.

        Args:
            origen: Nodo de partida.
            destino: Nodo de llegada.

        Returns:
            El resultado de la busqueda.
        """
        clave = (origen, destino)
        resultado = self._rutas.get(clave)  # una sola busqueda en el dict
        if resultado is not None:
            self.contadores.aciertos += 1
            self._rutas.move_to_end(clave)  # LRU: pasa a ser la mas nueva
            return resultado

        self.contadores.fallos += 1
        resultado = self.algoritmo(self.red, origen, destino)
        self._guardar(clave, resultado)
        return resultado

    def precargar(
        self, origen: Nodo, destino: Nodo, resultado: Resultado
    ) -> None:
        """Guarda una ruta calculada afuera. No cuenta como acierto ni fallo.

        Args:
            origen: Nodo de partida.
            destino: Nodo de llegada.
            resultado: Ruta ya calculada, por ejemplo en otro proceso.
        """
        self._guardar((origen, destino), resultado)

    def _guardar(self, clave: Clave, resultado: Resultado) -> None:
        """Guarda la ruta, la indexa por tramo y aplica LRU si sobra."""
        self._rutas[clave] = resultado
        self._rutas.move_to_end(clave)
        for tramo in _tramos(resultado):
            self._por_tramo.setdefault(tramo, set()).add(clave)

        while len(self._rutas) > self.capacidad:
            clave_vieja, resultado_viejo = self._rutas.popitem(last=False)
            self._quitar_del_indice(clave_vieja, resultado_viejo)
            self.contadores.descartadas += 1

    def _quitar_del_indice(
        self, clave: Clave, resultado: Resultado, excepto: Tramo | None = None
    ) -> None:
        """Saca la ruta del indice de tramos, salvo del tramo ``excepto``."""
        for tramo in _tramos(resultado):
            if tramo == excepto:
                continue
            usuarias = self._por_tramo.get(tramo)
            if usuarias:
                usuarias.discard(clave)
                if not usuarias:
                    del self._por_tramo[tramo]

    # [EXPO P1] Cache inteligente: invalida solo las rutas de ese tramo.
    def cortar_tramo(self, a: Nodo, b: Nodo) -> int:
        """Corta un tramo de la red e invalida solo las rutas que lo usaban.

        Args:
            a: Un extremo del tramo.
            b: El otro extremo.

        Returns:
            Cantidad de rutas invalidadas.
        """
        self.red.cortar_arista(a, b)
        tramo = clave_de_tramo(a, b)
        afectadas = self._por_tramo.pop(tramo, set())

        for clave in afectadas:
            resultado = self._rutas.pop(clave, None)
            if resultado is not None:
                self._quitar_del_indice(clave, resultado, excepto=tramo)

        self.contadores.invalidadas += len(afectadas)
        return len(afectadas)

    def estadisticas(self) -> dict[str, float]:
        """Resumen de la actividad, listo para imprimir o serializar.

        Returns:
            Diccionario con consultas, aciertos, fallos, tasa de aciertos,
            rutas guardadas, invalidadas y descartadas.
        """
        datos: dict[str, float] = asdict(self.contadores)
        datos["consultas"] = self.contadores.consultas
        datos["tasa_aciertos"] = self.contadores.tasa_aciertos
        datos["guardadas"] = len(self._rutas)
        return datos

    def __repr__(self) -> str:
        """Ocupacion y tasa de aciertos."""
        return (
            f"<CacheDeRutas {len(self._rutas)}/{self.capacidad} rutas, "
            f"{self.contadores.tasa_aciertos:.0%} de aciertos>"
        )


def _tramos(resultado: Resultado) -> list[Tramo]:
    """Tramos que usa una ruta, como claves sin sentido."""
    if not resultado.ruta:
        return []
    return [clave_de_tramo(a, b) for a, b in pairwise(resultado.ruta)]


def crear_memoizado(red: Red) -> Callable[[Nodo, Nodo], Resultado]:
    """Memoizacion con ``lru_cache``: rapida pero ciega a los cambios.

    Guarda por argumentos ``(origen, destino)``. Si despues se corta un
    tramo, sigue devolviendo la ruta vieja: no sabe que el mapa cambio.

    Args:
        red: Red sobre la que se calculan las rutas.

    Returns:
        Funcion ``calcular(origen, destino)`` memoizada.
    """

    @lru_cache(maxsize=1000)
    def calcular(origen: Nodo, destino: Nodo) -> Resultado:
        return a_estrella(red, origen, destino)

    return calcular
