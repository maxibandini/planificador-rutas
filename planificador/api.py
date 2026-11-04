"""API web del planificador, hecha con Flask.

Flask es un micro-framework: trae ruteo, plantillas y un cliente de
pruebas, y deja elegir el resto. Alcanza para exponer el planificador
como servicio HTTP sin la estructura de un framework completo como Django.

Rutas:
    ``GET  /``                     pagina con formulario y mapa.
    ``GET  /api/ciudades``         ciudades disponibles.
    ``GET  /api/ruta``             ruta entre ``origen`` y ``destino``.
    ``GET  /api/comparar``         la misma consulta con los 4 algoritmos.
    ``POST /api/tramos/cortar``    corta un tramo e invalida la cache.
    ``POST /api/reiniciar``        vuelve al mapa original.
    ``GET  /api/cache``            estadisticas de la cache.
"""

from __future__ import annotations

import copy
import threading
from typing import Any

from flask import Flask, jsonify, render_template, request

from planificador.algoritmos import ALGORITMOS, Resultado, a_estrella
from planificador.cache import CacheDeRutas
from planificador.red import Nodo, Red, red_argentina
from planificador.telemetria import instrumentar_flask, tracer

ALGORITMO_POR_DEFECTO = "A*"
LADO_SVG = (320, 560)
MARGEN_SVG = 20


class ConsultaInvalidaError(ValueError):
    """Error en los datos de una peticion. Se responde con HTTP 400."""


# Span propio para A*: solo aparece en los fallos de cache.
def _a_estrella_trazada(red: Red, origen: Nodo, destino: Nodo) -> Resultado:
    """A* dentro de un span, para ver en el APM cuanto tarda cada calculo.

    Solo se ejecuta en los fallos de cache: en un acierto no aparece.
    """
    with tracer.start_as_current_span("busqueda.a_estrella") as span:
        resultado = a_estrella(red, origen, destino)
        span.set_attribute("busqueda.explorados", resultado.explorados)
        span.set_attribute("busqueda.nodos_en_ruta", len(resultado.ruta or []))
        return resultado


# Mapa y cache compartidos por los hilos: protegidos con lock.
class ServicioDeRutas:
    """Capa de servicio: mapa y cache compartidos por todas las peticiones.

    El servidor atiende cada peticion en un hilo distinto, y la cache
    modifica un ``OrderedDict`` en cada consulta. Sin el lock dos hilos
    podrian corromperla. El lock serializa los calculos, pero con el GIL
    el trabajo de CPU en hilos tampoco correria en paralelo.

    Args:
        red: Mapa de ciudades (nodos con nombre). Por defecto, las
            ciudades argentinas.
    """

    def __init__(self, red: Red | None = None) -> None:
        """Crea el servicio con su mapa y su cache."""
        self._lock = threading.Lock()
        self._red_original = red or red_argentina()
        self.red, self.cache = self._estado_inicial()

    def _estado_inicial(self) -> tuple[Red, CacheDeRutas]:
        """Copia del mapa original y una cache vacia sobre esa copia."""
        red = copy.deepcopy(self._red_original)
        return red, CacheDeRutas(red, algoritmo=_a_estrella_trazada)

    def reiniciar(self) -> None:
        """Vuelve al mapa original y vacia la cache."""
        with self._lock:
            self.red, self.cache = self._estado_inicial()

    def ciudades(self) -> list[str]:
        """Nombres de las ciudades, ordenados alfabeticamente."""
        return sorted(str(nodo) for nodo in self.red.adyacencia)

    def _validar(self, *nodos: str) -> None:
        """Lanza :class:`ConsultaInvalidaError` si alguna ciudad no existe."""
        for nodo in nodos:
            if nodo not in self.red:
                raise ConsultaInvalidaError(f"Ciudad desconocida: {nodo!r}")

    def ruta(
        self, origen: str, destino: str, algoritmo: str = ALGORITMO_POR_DEFECTO
    ) -> tuple[Resultado, bool]:
        """Calcula una ruta. Con A* usa la cache.

        Args:
            origen: Ciudad de partida.
            destino: Ciudad de llegada.
            algoritmo: Nombre de un algoritmo de :data:`ALGORITMOS`.

        Returns:
            Tupla ``(resultado, desde_cache)``.

        Raises:
            ConsultaInvalidaError: Si una ciudad o el algoritmo no existen.
        """
        self._validar(origen, destino)
        if algoritmo not in ALGORITMOS:
            raise ConsultaInvalidaError(
                f"Algoritmo desconocido: {algoritmo!r}"
            )

        with tracer.start_as_current_span("servicio.ruta") as span:
            span.set_attribute("ruta.origen", origen)
            span.set_attribute("ruta.destino", destino)
            span.set_attribute("ruta.algoritmo", algoritmo)
            with self._lock:
                if algoritmo == ALGORITMO_POR_DEFECTO:
                    desde_cache = (origen, destino) in self.cache
                    resultado = self.cache.consultar(origen, destino)
                else:
                    desde_cache = False
                    resultado = ALGORITMOS[algoritmo](
                        self.red, origen, destino
                    )
            span.set_attribute("cache.acierto", desde_cache)
            return resultado, desde_cache

    def cortar_tramo(self, a: str, b: str) -> int:
        """Corta un tramo existente e invalida las rutas que lo usaban.

        Args:
            a: Un extremo.
            b: El otro extremo.

        Returns:
            Cantidad de rutas invalidadas.

        Raises:
            ConsultaInvalidaError: Si alguna ciudad o el tramo no existen.
        """
        self._validar(a, b)
        with tracer.start_as_current_span("servicio.cortar_tramo") as span:
            with self._lock:
                try:
                    self.red.peso(a, b)
                except ValueError as error:
                    raise ConsultaInvalidaError(str(error)) from error
                invalidadas = self.cache.cortar_tramo(a, b)
            span.set_attribute("cache.invalidadas", invalidadas)
            return invalidadas

    def estadisticas(self) -> dict[str, float]:
        """Estadisticas de la cache."""
        with self._lock:
            return self.cache.estadisticas()

    def mapa_svg(self) -> dict[str, Any]:
        """Coordenadas escaladas al SVG de la pagina y lista de tramos."""
        xs = [x for x, _ in self.red.coordenadas.values()]
        ys = [y for _, y in self.red.coordenadas.values()]
        ancho, alto = LADO_SVG
        # max(..., 1e-9): un mapa con todos los nodos alineados no divide por 0
        escala = min(
            (ancho - 2 * MARGEN_SVG) / max(max(xs) - min(xs), 1e-9),
            (alto - 2 * MARGEN_SVG) / max(max(ys) - min(ys), 1e-9),
        )
        puntos = {
            str(nodo): (
                round(MARGEN_SVG + (x - min(xs)) * escala, 1),
                round(MARGEN_SVG + (max(ys) - y) * escala, 1),
            )
            for nodo, (x, y) in self.red.coordenadas.items()
        }
        tramos = sorted(
            {
                tuple(sorted((str(a), str(b))))
                for a, vecinos in self.red.adyacencia.items()
                for b, _ in vecinos
            }
        )
        return {
            "puntos": puntos,
            "tramos": tramos,
            "ancho": ancho,
            "alto": alto,
        }


def _resultado_a_json(resultado: Resultado) -> dict[str, Any]:
    """Convierte un resultado en un diccionario serializable."""
    return {
        "ruta": resultado.ruta,
        "costo": round(resultado.costo, 3) if resultado.ruta else None,
        "explorados": resultado.explorados,
        "nodos_en_ruta": len(resultado.ruta or []),
    }


def _parametro(nombre: str) -> str:
    """Lee un parametro obligatorio de la URL."""
    valor = request.args.get(nombre, "").strip()
    if not valor:
        raise ConsultaInvalidaError(f"Falta el parametro {nombre!r}")
    return valor


# FLASK: application factory con todas las rutas de la API.
def crear_app(red: Red | None = None, telemetria: bool = False) -> Flask:
    """Crea la aplicacion Flask (patron *application factory*).

    Crear la app en una funcion permite tener varias instancias
    independientes, por ejemplo una limpia para cada test.

    Args:
        red: Mapa a usar. Por defecto, las ciudades argentinas.
        telemetria: Si es ``True`` se instrumenta con OpenTelemetry. Antes
            hay que llamar a :func:`planificador.telemetria.configurar_trazas`.

    Returns:
        La aplicacion lista para servir.
    """
    app = Flask(__name__)
    servicio = ServicioDeRutas(red)
    app.extensions["servicio"] = servicio
    if telemetria:
        instrumentar_flask(app)

    @app.errorhandler(ConsultaInvalidaError)
    def error_de_consulta(error: ConsultaInvalidaError):
        return jsonify(error=str(error)), 400

    @app.get("/")
    def inicio():
        origen = request.args.get("origen", "Ushuaia")
        destino = request.args.get("destino", "Salta")
        algoritmo = request.args.get("algoritmo", ALGORITMO_POR_DEFECTO)
        contexto: dict[str, Any] = {
            "ciudades": servicio.ciudades(),
            "algoritmos": list(ALGORITMOS),
            "origen": origen,
            "destino": destino,
            "algoritmo": algoritmo,
            "mapa": servicio.mapa_svg(),
            "resultado": None,
            "error": None,
        }
        try:
            resultado, desde_cache = servicio.ruta(origen, destino, algoritmo)
            contexto["resultado"] = _resultado_a_json(resultado)
            contexto["desde_cache"] = desde_cache
        except ConsultaInvalidaError as error:
            contexto["error"] = str(error)
        return render_template("index.html", **contexto)

    @app.get("/api/ciudades")
    def ciudades():
        return jsonify(ciudades=servicio.ciudades())

    # Endpoint principal: GET /api/ruta?origen=...&destino=...
    @app.get("/api/ruta")
    def ruta():
        origen, destino = _parametro("origen"), _parametro("destino")
        algoritmo = request.args.get("algoritmo", ALGORITMO_POR_DEFECTO)
        resultado, desde_cache = servicio.ruta(origen, destino, algoritmo)
        if resultado.ruta is None:
            return jsonify(error="No hay ruta entre esas ciudades"), 404
        return jsonify(
            origen=origen,
            destino=destino,
            algoritmo=algoritmo,
            desde_cache=desde_cache,
            **_resultado_a_json(resultado),
        )

    @app.get("/api/comparar")
    def comparar():
        origen, destino = _parametro("origen"), _parametro("destino")
        filas = {}
        for nombre in ALGORITMOS:
            resultado, _ = servicio.ruta(origen, destino, nombre)
            filas[nombre] = _resultado_a_json(resultado)
        return jsonify(origen=origen, destino=destino, algoritmos=filas)

    @app.post("/api/tramos/cortar")
    def cortar_tramo():
        datos = request.get_json(silent=True)
        if (
            not isinstance(datos, dict)
            or not datos.get("a")
            or not datos.get("b")
        ):
            raise ConsultaInvalidaError(
                'Se espera un JSON {"a": ciudad, "b": ciudad}'
            )
        a, b = str(datos["a"]).strip(), str(datos["b"]).strip()
        invalidadas = servicio.cortar_tramo(a, b)
        return jsonify(tramo=[a, b], invalidadas=invalidadas)

    @app.post("/api/reiniciar")
    def reiniciar():
        servicio.reiniciar()
        return jsonify(ok=True)

    @app.get("/api/cache")
    def estadisticas():
        return jsonify(servicio.estadisticas())

    return app
