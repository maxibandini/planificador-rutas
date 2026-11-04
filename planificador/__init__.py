"""Planificador inteligente de rutas.

Paquete del segundo parcial de Programacion Eficiente. Reune el codigo del
primer parcial (grafo, algoritmos de busqueda, cache y concurrencia)
refactorizado, y agrega las piezas nuevas: entrada/salida de archivos
grandes, una API web con Flask y telemetria con OpenTelemetry.

Modulos:
    red: grafo no dirigido con pesos y generadores de mapas.
    algoritmos: BFS, Dijkstra (lista y heap) y A*.
    cache: memoizacion con ``lru_cache`` y cache con invalidacion.
    concurrencia: secuencial, hilos y procesos.
    consultas: generacion reproducible de lotes de consultas.
    archivos: lectura y escritura de archivos grandes por lotes.
    mediciones: cronometro y pico de memoria.
    formato: unidades legibles para tiempos y memoria.
    consola: impresion de titulos y rutas.
    api: aplicacion web Flask.
    telemetria: trazas OpenTelemetry exportadas a Jaeger.
"""

__version__ = "2.0.0"
