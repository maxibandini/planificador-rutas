"""Trazas distribuidas con OpenTelemetry (monitoreo tipo APM).

OpenTelemetry es el estandar abierto de instrumentacion. El codigo genera
*spans* (tramos de una traza: cuanto tardo cada parte de una peticion) y
un exportador los envia por OTLP a un servidor de APM. Aca se usa Jaeger
porque corre local y gratis, pero Elastic APM, New Relic y Dynatrace
aceptan el mismo protocolo OTLP: cambiar de herramienta es cambiar el
``endpoint``, no el codigo.

Mientras no se llame a :func:`configurar_trazas`, ``tracer`` no hace nada
y su costo es despreciable: la instrumentacion puede quedar siempre.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)

from planificador import __version__

if TYPE_CHECKING:
    from flask import Flask

NOMBRE_SERVICIO = "planificador-rutas"
ENDPOINT_OTLP = "http://localhost:4318/v1/traces"
"""Puerto OTLP/HTTP por defecto de Jaeger, Elastic APM y el Collector."""

tracer = trace.get_tracer("planificador", __version__)
"""Tracer del paquete. Es un proxy: empieza a exportar al configurarlo."""


def reloj_de_alta_resolucion() -> Callable[[], int]:
    """Reloj en nanosegundos desde 1970 con resolucion de microsegundos.

    Ancla ``perf_counter_ns`` (alta resolucion, sin fecha) a ``time_ns``
    (con fecha, baja resolucion) una sola vez, al crearlo.

    Returns:
        Funcion sin argumentos que devuelve la hora actual en ns.

    Example:
        >>> reloj = reloj_de_alta_resolucion()
        >>> abs(reloj() - time.time_ns()) < 1_000_000_000
        True
    """
    base = time.time_ns() - time.perf_counter_ns()
    return lambda: base + time.perf_counter_ns()


# Problema real: el reloj de Windows dejaba los spans en 0 ms.
def _corregir_reloj_en_windows() -> None:
    """Da a OpenTelemetry un reloj preciso en Windows con Python < 3.13.

    Ahi ``time.time_ns()`` usa ``GetSystemTimeAsFileTime`` y avanza de a
    0,5-15,6 ms: un A* de 0,02 ms aparecia en Jaeger con duracion 0.
    Python 3.13 ya usa el reloj preciso y no necesita la correccion.
    """
    if sys.platform != "win32" or sys.version_info >= (3, 13):
        return
    import opentelemetry.instrumentation.flask as instrumentacion_flask
    import opentelemetry.sdk.trace as sdk_trace

    # sdk_trace: inicio y fin de los spans; flask: inicio de cada peticion.
    # Si una version futura cambia estos nombres internos, no se toca nada.
    reloj = reloj_de_alta_resolucion()
    for modulo in (sdk_trace, instrumentacion_flask):
        if hasattr(modulo, "time_ns"):
            # Solo corre en Windows: en Linux mypy ve la linea inalcanzable.
            modulo.time_ns = reloj  # type: ignore[attr-defined,unused-ignore]


# APM: OpenTelemetry exporta las trazas a Jaeger por OTLP.
def configurar_trazas(
    nombre_servicio: str = NOMBRE_SERVICIO,
    endpoint: str = ENDPOINT_OTLP,
    exportador: SpanExporter | None = None,
    por_lotes: bool = True,
) -> TracerProvider:
    """Activa la exportacion de trazas para todo el proceso.

    Args:
        nombre_servicio: Nombre con el que aparece el servicio en el APM.
        endpoint: URL OTLP/HTTP del colector de trazas.
        exportador: Exportador a usar. Por defecto OTLP hacia
            ``endpoint``; los tests pasan uno en memoria.
        por_lotes: Si es ``True`` los spans se envian de a lotes en un
            hilo aparte (``BatchSpanProcessor``), asi la peticion no espera
            a la red. Es la misma idea de batching de la unidad 5.

    Returns:
        El proveedor configurado, por si hay que cerrarlo con
        ``shutdown()`` para vaciar los lotes pendientes.
    """
    if exportador is None:
        # Import perezoso: el exportador OTLP solo se carga si se usa.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        exportador = OTLPSpanExporter(endpoint=endpoint)

    _corregir_reloj_en_windows()
    proveedor = TracerProvider(
        resource=Resource.create(
            {
                "service.name": nombre_servicio,
                "service.version": __version__,
            }
        )
    )
    procesador = (
        BatchSpanProcessor(exportador)
        if por_lotes
        else SimpleSpanProcessor(exportador)
    )
    proveedor.add_span_processor(procesador)
    trace.set_tracer_provider(proveedor)
    return proveedor


def instrumentar_flask(app: Flask) -> None:
    """Crea un span por cada peticion HTTP que atiende la aplicacion.

    Args:
        app: Aplicacion Flask a instrumentar.
    """
    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    FlaskInstrumentor().instrument_app(app)
