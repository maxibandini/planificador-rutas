"""Pruebas de integracion de la API Flask con su cliente de pruebas."""

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from planificador import telemetria
from planificador.api import crear_app


def test_ciudades(cliente):
    respuesta = cliente.get("/api/ciudades")
    assert respuesta.status_code == 200
    assert len(respuesta.get_json()["ciudades"]) == 24


# Integracion: la API completa con el cliente de Flask.
def test_ruta_y_segunda_consulta_desde_cache(cliente):
    url = "/api/ruta?origen=Ushuaia&destino=Salta"
    primera = cliente.get(url).get_json()
    segunda = cliente.get(url).get_json()
    assert primera["costo"] == segunda["costo"]
    assert primera["desde_cache"] is False
    assert segunda["desde_cache"] is True
    assert primera["ruta"][0] == "Ushuaia"


def test_ciudad_desconocida_responde_400(cliente):
    respuesta = cliente.get("/api/ruta?origen=Atlantida&destino=Salta")
    assert respuesta.status_code == 400
    assert "Atlantida" in respuesta.get_json()["error"]


def test_falta_parametro_responde_400(cliente):
    assert cliente.get("/api/ruta?origen=Salta").status_code == 400


def test_algoritmo_desconocido_responde_400(cliente):
    url = "/api/ruta?origen=Ushuaia&destino=Salta&algoritmo=magia"
    assert cliente.get(url).status_code == 400


def test_cortar_tramo_invalida_y_recalcula(cliente):
    url = "/api/ruta?origen=Ushuaia&destino=Salta"
    antes = cliente.get(url).get_json()
    corte = cliente.post(
        "/api/tramos/cortar", json={"a": "Bahia Blanca", "b": "Buenos Aires"}
    )
    assert corte.get_json()["invalidadas"] == 1
    despues = cliente.get(url).get_json()
    assert despues["desde_cache"] is False
    assert despues["costo"] > antes["costo"]


def test_cortar_tramo_inexistente_responde_400(cliente):
    corte = cliente.post(
        "/api/tramos/cortar", json={"a": "Ushuaia", "b": "Salta"}
    )
    assert corte.status_code == 400


def test_reiniciar_restaura_el_mapa(cliente):
    cliente.post(
        "/api/tramos/cortar", json={"a": "Bahia Blanca", "b": "Buenos Aires"}
    )
    cliente.post("/api/reiniciar")
    datos = cliente.get("/api/ruta?origen=Ushuaia&destino=Salta").get_json()
    assert round(datos["costo"]) == 4819


def test_comparar_devuelve_los_cuatro_algoritmos(cliente):
    datos = cliente.get("/api/comparar?origen=Ushuaia&destino=Salta")
    algoritmos = datos.get_json()["algoritmos"]
    assert set(algoritmos) == {"BFS", "Dijkstra lista", "Dijkstra heap", "A*"}
    assert algoritmos["A*"]["explorados"] < algoritmos["BFS"]["explorados"]


def test_pagina_principal_dibuja_la_ruta(cliente):
    respuesta = cliente.get("/?origen=Mendoza&destino=Rosario")
    assert respuesta.status_code == 200
    assert b"<polyline" in respuesta.data
    assert b"Planificador" in respuesta.data


def test_estadisticas_de_cache(cliente):
    cliente.get("/api/ruta?origen=Ushuaia&destino=Salta")
    cliente.get("/api/ruta?origen=Ushuaia&destino=Salta")
    datos = cliente.get("/api/cache").get_json()
    assert datos["aciertos"] == 1
    assert datos["fallos"] == 1


def test_telemetria_genera_spans():
    # El exportador en memoria reemplaza a Jaeger: se verifica que la
    # instrumentacion produce los spans esperados sin levantar servidores.
    exportador = InMemorySpanExporter()
    telemetria.configurar_trazas(exportador=exportador, por_lotes=False)
    cliente = crear_app(telemetria=True).test_client()
    cliente.get("/api/ruta?origen=Ushuaia&destino=Salta")
    cliente.get("/api/ruta?origen=Ushuaia&destino=Salta")

    nombres = [span.name for span in exportador.get_finished_spans()]
    assert nombres.count("busqueda.a_estrella") == 1  # solo en el fallo
    assert nombres.count("servicio.ruta") == 2
    assert any(nombre.startswith("GET") for nombre in nombres)
    aciertos = [
        span.attributes["cache.acierto"]
        for span in exportador.get_finished_spans()
        if span.name == "servicio.ruta"
    ]
    assert aciertos == [False, True]
    # Regresion: en Windows con Python < 3.13 el reloj por defecto avanza
    # de a 0,5-15,6 ms y un A* de microsegundos aparecia con duracion 0.
    (busqueda,) = [
        span
        for span in exportador.get_finished_spans()
        if span.name == "busqueda.a_estrella"
    ]
    assert busqueda.end_time > busqueda.start_time


def test_cortar_con_json_que_no_es_objeto_responde_400(cliente):
    for cuerpo in ([1, 2], 5, "hola", {}):
        respuesta = cliente.post("/api/tramos/cortar", json=cuerpo)
        assert respuesta.status_code == 400


def test_cortar_recorta_espacios(cliente):
    respuesta = cliente.post(
        "/api/tramos/cortar",
        json={"a": " Bahia Blanca ", "b": "Buenos Aires "},
    )
    assert respuesta.status_code == 200
