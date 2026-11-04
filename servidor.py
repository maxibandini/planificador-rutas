"""Levanta la API web del planificador.

Uso::

    python servidor.py                      waitress en http://127.0.0.1:8000
    python servidor.py --telemetria         ademas exporta trazas a Jaeger
    python servidor.py --desarrollo         servidor de Flask con recarga

Waitress es un servidor WSGI de produccion escrito en Python puro: funciona
igual en Windows y en Linux. El servidor que trae Flask es solo para
desarrollo.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys

from planificador.api import crear_app
from planificador.telemetria import ENDPOINT_OTLP, configurar_trazas

HOST = "127.0.0.1"
HILOS = 8


def puerto_valido(texto: str) -> int:
    """Convierte el argumento ``--puerto`` y controla el rango."""
    puerto = int(texto)
    if not 1 <= puerto <= 65535:
        raise argparse.ArgumentTypeError("el puerto va de 1 a 65535")
    return puerto


def leer_argumentos() -> argparse.Namespace:
    """Opciones de la linea de comandos."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--puerto", type=puerto_valido, default=8000)
    parser.add_argument(
        "--telemetria",
        action="store_true",
        help="exportar trazas OpenTelemetry (Jaeger u otro APM OTLP)",
    )
    parser.add_argument(
        "--endpoint", default=ENDPOINT_OTLP, help="URL OTLP/HTTP del APM"
    )
    parser.add_argument(
        "--desarrollo",
        action="store_true",
        help="usar el servidor de desarrollo de Flask",
    )
    return parser.parse_args()


def puerto_ocupado(puerto: int) -> bool:
    """Indica si ya hay un servidor atendiendo en ese puerto.

    En Windows waitress y Flask pueden abrir un puerto que ya usa otro
    proceso, y las peticiones las sigue atendiendo el viejo. Mejor avisar.
    """
    try:
        with socket.create_connection((HOST, puerto), timeout=0.5):
            return True
    except OSError:
        return False


# waitress sirve la app Flask; --telemetria activa OpenTelemetry.
def main() -> None:
    """Punto de entrada."""
    argumentos = leer_argumentos()
    # El recargador de Flask abre el puerto en un proceso padre y vuelve a
    # correr este script en un hijo: en el hijo el puerto ya es suyo.
    es_hijo_del_recargador = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not es_hijo_del_recargador and puerto_ocupado(argumentos.puerto):
        print(
            f"Ya hay un servidor en el puerto {argumentos.puerto}. Cerralo "
            "(Ctrl+C en su terminal) o usa --puerto con otro numero."
        )
        sys.exit(1)

    proveedor = None
    if argumentos.telemetria:
        # el proveedor de trazas se configura antes de crear la app
        proveedor = configurar_trazas(endpoint=argumentos.endpoint)
    app = crear_app(telemetria=argumentos.telemetria)

    print(f"Planificador en http://{HOST}:{argumentos.puerto}  (Ctrl+C sale)")
    if argumentos.telemetria:
        print(f"Trazas -> {argumentos.endpoint}  (Jaeger: localhost:16686)")
    try:
        if argumentos.desarrollo:
            app.run(host=HOST, port=argumentos.puerto, debug=True)
        else:
            # import perezoso: el modo desarrollo no necesita waitress
            from waitress import serve

            serve(app, host=HOST, port=argumentos.puerto, threads=HILOS)
    finally:
        if proveedor is not None:
            proveedor.shutdown()  # envia los spans que quedaban en el lote


if __name__ == "__main__":
    main()
