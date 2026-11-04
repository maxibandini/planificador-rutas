# Diseño técnico

## Estructuras de datos

| Estructura | Dónde | Por qué |
|---|---|---|
| **Lista de adyacencia** `dict[nodo, list[(vecino, peso)]]` | `Red.adyacencia` | La red es dispersa (cada ciudad tiene pocos vecinos): ocupa O(V + E) y recorrer los vecinos de un nodo cuesta O(grado). Una matriz ocuparía O(V²). |
| **dict** de coordenadas | `Red.coordenadas` | La heurística de A* pide la posición de un nodo en O(1). |
| **Heap** (`heapq`) | `_busqueda_con_heap` | Sacar el nodo pendiente de menor costo en O(log V) en lugar de O(V). |
| **deque** | `bfs`, ventana de lotes en `archivos` | `popleft` en O(1); `list.pop(0)` es O(n). |
| **OrderedDict** | `CacheDeRutas._rutas` | Política LRU: `move_to_end` y `popitem(last=False)` en O(1). |
| **Índice invertido** `dict[tramo, set[(origen, destino)]]` | `CacheDeRutas._por_tramo` | Al cortar un tramo se sabe qué rutas borrar sin recorrer toda la caché. |
| **NamedTuple** `Resultado(ruta, costo, explorados)` | `algoritmos` | Inmutable, liviano y con nombres: se puede guardar en la caché y serializar entre procesos. |
| **Generadores** | `archivos.leer_consultas`, `resolver_consultas` | Procesan el archivo línea por línea: la memoria no crece con el tamaño del archivo. |

## Algoritmos

| Algoritmo | Complejidad temporal | Memoria | Óptimo | Cuándo usarlo |
|---|---|---|---|---|
| BFS | O(V + E) | O(V) | Solo en cantidad de tramos | Pesos iguales; minimizar escalas |
| Dijkstra con lista | O(V²) | O(V) | Sí | Línea base para comparar |
| Dijkstra con heap | O((V + E) log V) | O(V) | Sí | Sin información geométrica |
| **A\*** (el que usa la app) | O((V + E) log V) en el peor caso, explora mucho menos en la práctica | O(V) | Sí, con heurística admisible | Con coordenadas: la distancia en línea recta nunca sobreestima |

**Heurística admisible.** Cada tramo cuesta al menos la distancia recta entre
sus extremos (los generadores multiplican esa distancia por un factor ≥ 1).
Por eso `distancia_recta(nodo, destino)` nunca sobreestima y A* sigue
encontrando la ruta óptima.

**Dijkstra es A\* con h = 0.** `dijkstra_heap` y `a_estrella` comparten
`_busqueda_con_heap(heuristica)`: solo cambia la función heurística. Hay un
único lugar que mantener.

**Caché con invalidación.** `CacheDeRutas.consultar` busca la clave en el
`OrderedDict` (O(1)); si no está, corre A* y guarda la ruta indexando cada
uno de sus tramos. `cortar_tramo(a, b)` consulta el índice y borra solo esas
rutas: O(rutas afectadas), no O(rutas guardadas).

```python
>>> from planificador.cache import CacheDeRutas
>>> from planificador.red import red_argentina
>>> cache = CacheDeRutas(red_argentina())
>>> _ = cache.consultar("Ushuaia", "Salta")    # pasa por Santa Fe - Cordoba
>>> _ = cache.consultar("Rosario", "Mendoza")  # no pasa
>>> cache.cortar_tramo("Santa Fe", "Cordoba")  # invalida solo la primera
1
>>> len(cache)
1

```

## Decisiones de implementación

| Decisión | Por qué | Medición que la respalda |
|---|---|---|
| A* como algoritmo por defecto | Explora menos nodos que Dijkstra con la misma ruta | 17 contra 24 nodos explorados en Ushuaia–Salta; 2,6x más rápido en el benchmark |
| No memoizar la heurística dentro de A* | El 28 % de las llamadas se repiten, pero consultar un dict cuesta lo mismo que `math.hypot` | Entre 0 % y 10 % más lento con memoización (parcial 2) |
| Lock en `ServicioDeRutas` y no en `CacheDeRutas` | La caché queda rápida para el uso de un solo hilo (bancos, archivos); solo la API la comparte entre hilos | — |
| Tubería de generadores en `archivos.py` | Cada técnica de E/S se puede cambiar y medir por separado | Tubería completa 238x más rápida que la ingenua (parcial 2) |
| Ventana acotada de lotes en el paralelo | `Executor.map` consume todo el archivo antes de empezar | Memoria constante con archivos de millones de líneas |
| El proceso hijo devuelve el lote como un único `str` | Serializar un string es mucho más barato que miles de tuplas | — |
| `newline="\n"` en todas las escrituras | Las cuatro estrategias generan archivos idénticos byte a byte, también en Windows | Test `test_las_cuatro_tuberias_dan_la_misma_salida` |
| OpenTelemetry en lugar de un agente propietario | Estándar abierto: el mismo código sirve para Jaeger, Elastic APM o New Relic | — |
| Globales de los procesos hijos declaradas sin valor (`_red_del_trabajador: Red`) | mypy marcaba que podían ser `None`; se asignan siempre en el initializer del pool | mypy: 6 errores → 0 (ver [Evolución](evolucion.md#los-6-errores-que-encontro-mypy)) |
| Benchmark relativo a una referencia en Python puro | Los tiempos absolutos cambian entre la notebook, la PC y el runner | Variación ±4 % en la misma máquina y hasta +27 % entre runners, con tolerancia de 30 % (ver [Rendimiento](rendimiento.md)) |
