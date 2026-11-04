# Descripción funcional

## Problema que resuelve

Una empresa de logística necesita saber, para cada pedido, cuál es el camino
más barato entre dos puntos de una red (ciudades, depósitos o puntos de
entrega). Las consultas llegan de a miles, muchas se repiten y el mapa
cambia: un tramo se corta por obras y las rutas que lo usaban dejan de ser
válidas.

El planificador resuelve tres cosas:

1. **Encontrar la ruta de menor costo** entre dos nodos de un grafo con pesos.
2. **Responder muchas consultas rápido:** caché de rutas, concurrencia y
   procesamiento de archivos grandes por lotes.
3. **Adaptarse a los cambios del mapa:** al cortar un tramo se invalidan solo
   las rutas que pasaban por él.

## Alcance

| Incluido | Fuera de alcance |
|---|---|
| Mapa de 24 ciudades argentinas (45 tramos) y grillas generadas de hasta 10⁴-10⁵ nodos | Datos viales reales: las distancias son de un modelo didáctico |
| Cuatro algoritmos: BFS, Dijkstra con lista, Dijkstra con heap y A* | Rutas con restricciones (horarios, capacidad de vehículos) |
| Caché LRU con invalidación por tramo | Persistencia del mapa entre reinicios del servidor |
| Procesamiento de archivos de consultas por streaming, lotes y procesos | Autenticación de usuarios en la API |
| API web y página con mapa (Flask) | Despliegue en producción |
| Trazas con OpenTelemetry (Jaeger) | |

## Requisitos funcionales

| Id | Requisito | Dónde se cumple |
|---|---|---|
| RF1 | Calcular la ruta de menor costo entre dos nodos | `algoritmos.a_estrella` |
| RF2 | Comparar los cuatro algoritmos sobre la misma consulta | `GET /api/comparar`, `banco.py` |
| RF3 | Informar cuando no hay ruta (red desconectada) | `Resultado(ruta=None, costo=inf)`, HTTP 404 |
| RF4 | Cortar un tramo e invalidar solo las rutas afectadas | `CacheDeRutas.cortar_tramo`, `POST /api/tramos/cortar` |
| RF5 | Procesar un archivo de consultas y escribir un archivo de resultados | `archivos.procesar_por_lotes` / `procesar_en_paralelo` |
| RF6 | Resolver lotes de consultas en paralelo | `concurrencia.con_procesos` |
| RF7 | Rechazar datos inválidos con un mensaje claro | `ConsultaInvalidaError` → HTTP 400 |

## Requisitos no funcionales

Cada uno tiene un control automático en el CI (ver [Integración continua](ci.md)).

| Id | Requisito | Cómo se verifica |
|---|---|---|
| RNF1 | Correctitud: las rutas de los cuatro algoritmos tienen el mismo costo | 121 pruebas, cobertura ≥ 90 % |
| RNF2 | Rendimiento: ninguna operación representativa empeora más de un 30 % | Benchmark contra línea base |
| RNF3 | Memoria: A* sobre 10.000 nodos y el procesamiento de archivos no superan su línea base en más de un 20 % | `tracemalloc` |
| RNF3b | Complejidad: el tiempo de Dijkstra con lista crece como V² y el de Dijkstra con heap como V log V; la lectura por streaming usa memoria constante | Exponente medido en escala log-log |
| RNF4 | Mantenibilidad: complejidad ciclomática ≤ 10 y funciones de ≤ 50 líneas | Lizard |
| RNF5 | Seguridad: sin vulnerabilidades de severidad alta en el código, ni dependencias vulnerables, ni secretos | Bandit, pip-audit, Gitleaks |
| RNF6 | Reproducibilidad: todas las dependencias con versión fija | `requirements*.txt` |
