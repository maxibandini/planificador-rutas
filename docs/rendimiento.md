# Rendimiento

La etapa 6 del pipeline mide cinco cosas: tiempos (benchmark), dónde se
va el tiempo (profiling), complejidad del código, **complejidad temporal
medida** y memoria. Todo se reproduce con:

```bash
python controles.py rendimiento
```

## Benchmarks

`benchmarks/test_benchmark.py` usa **pytest-benchmark**: repite cada
operación (al menos 5 rondas, calibrando automáticamente las más rápidas) y
guarda las estadísticas en `reportes/benchmark.json`.

| Operación | Mínimo | Media | Rondas | Relativo a la referencia |
|---|---:|---:|---:|---:|
| `test_referencia` (Python puro, trabajo fijo) | 9,92 ms | 10,28 ms | 95 | 1 |
| `test_a_estrella` (20 consultas, 3.600 nodos) | 12,70 ms | 13,05 ms | 68 | 1,336 |
| `test_dijkstra_heap` (las mismas 20 consultas) | 32,74 ms | 33,70 ms | 31 | 3,436 |
| `test_cache_acierto` (una consulta repetida) | 0,0002 ms | 0,0002 ms | 138.889 | 0,00002 |
| `test_procesar_archivo_por_lotes` (2.000 consultas) | 1.048,8 ms | 1.056,9 ms | 5 | 108,3 |

Medido en AMD Ryzen 7 7800X3D, Windows 11, Python 3.14.6.

**Lectura:** A* es 2,6 veces más rápido que Dijkstra con heap sobre las
mismas consultas (explora menos nodos), y un acierto de caché cuesta 0,2 µs
contra 0,6 ms de calcular la ruta: unas 3.000 veces menos.

### En el runner de GitHub (Linux)

La primera línea base se midió en Windows. En la primera corrida aprobada
del CI:

| Operación | Tiempo absoluto, PC → runner | Tiempo relativo contra la línea base de Windows |
|---|---:|---:|
| `test_referencia` | 9,92 → 12,54 ms (+26 %) | — |
| `test_a_estrella` | 12,70 → 18,29 ms (+44 %) | **+9 %** |
| `test_dijkstra_heap` | 32,74 → 48,44 ms (+48 %) | **+12 %** |
| `test_procesar_archivo_por_lotes` | 1.048,8 → 1.494,9 ms (+43 %) | **+10 %** |

Con un umbral en milisegundos, el CI hubiera marcado una regresión que no
existe (el runner es más lento, nada más). En tiempo relativo la diferencia
queda en +9 a +12 %.

Pero esa fue una corrida. En 11 corridas, sin cambios en el código que se
mide, el tiempo relativo contra la línea base de Windows varió de −5 % a
+44 %, y con el 30 % de tolerancia original varias corridas se rechazaron
en falso. Los runners son máquinas compartidas: en algunas corridas el
código del proyecto (que recorre estructuras grandes en memoria) se frena
más que la referencia (cuentas simples), y los que GitHub asigna ahora (AMD
EPYC 9V45 y 9V74) dan casi siempre más que la PC.

Por eso, desde el pull request #3 la línea base es la **mediana de 7
corridas en el runner** (`python controles.py linea-base` con sus
`benchmark.json`) y la tolerancia es 50 %. Contra esa línea base, las 11
corridas quedan así:

| Corrida | Procesador del runner | Tiempo relativo contra la línea base |
|---|---|---:|
| Primera aprobada (push a `main`) | Intel Xeon Platinum 8573C | −15 a −8 % |
| Pull request #2 | AMD EPYC 7763 | −5 a +8 % |
| Merge del pull request #2 | Intel Xeon Platinum 8573C | −16 a −5 % |
| Pull request #3, primera | AMD EPYC 7763 | −13 a −12 % (sin el caché, ver abajo) |
| Pull request #3, siete más | AMD EPYC 9V45 y 9V74 | −23 a +19 % |

El peor caso es +19 %: lejos del 50 %. Y el defecto plantado (A* calcula
dos veces la ruta) se sigue rechazando aun en el runner más rápido de los
11 (+60 %). En la PC de desarrollo esta línea base da alrededor de −20 %
(la PC es más rápida), así que localmente también pasa. Los controles que no
dependen de la máquina dieron lo mismo: exponentes 1,96 y 1,15 (en Windows,
2,00 y 1,14) y picos de memoria de 1.119,7 y 10.976,0 KiB (en Windows,
1.121,7 y 10.976,3).

### Línea base y criterio de regresión

El problema de comparar tiempos en un CI es que el runner de GitHub, la
notebook (i7-13620H) y la PC de escritorio (Ryzen 7800X3D) tienen
velocidades distintas: un umbral en milisegundos fallaría o pasaría según la
máquina.

Por eso `controles.py` divide el mínimo de cada operación por el de
`test_referencia`, medida en la misma corrida y en la misma máquina, y
compara ese **tiempo relativo** con `benchmarks/linea_base.json`:

- Se usa el **mínimo** de las rondas: el ruido (otros procesos, la CPU
  cambiando de frecuencia) solo puede sumar tiempo.
- Cada ronda dura **al menos 0,1 ms** (`--benchmark-min-time=0.0001`). Un
  acierto de caché tarda 0,3 µs: si la ronda lo repite una o dos veces, el
  reloj y el propio bucle de medición pesan más que la operación. Pasó en
  el pull request #3: pytest-benchmark eligió 2 repeticiones por ronda (en
  vez de 40) y el acierto de caché dio +40 %, una regresión falsa. En local
  se reproduce igual: +33 % con 1 repetición por ronda, +8 a +12 % con 32
  o con 1.000.
- La **línea base** es la mediana de varias corridas en el runner de
  GitHub, el mismo entorno donde corre el control: la mediana no depende de
  una corrida extrema. Cómo regenerarla está en
  [Mantenimiento](mantenimiento.md#actualizar-la-linea-base-de-rendimiento).
- **Se rechaza** si una operación es más de un **50 %** más lenta que la
  línea base. En la misma máquina la variación entre corridas fue de ±4 %,
  pero entre corridas en GitHub fue de −23 % a +19 % alrededor de la
  mediana. Un 50 % deja pasar ese ruido y detecta una regresión real (el
  defecto plantado da al menos +60 %). Los cambios de algoritmo más sutiles
  los detecta la complejidad medida, que no depende de la máquina: cambiar
  el heap por `min()` sube el exponente de 1,14 a 1,51.

Salida real en una corrida del pull request #3 (AMD EPYC 9V74):

```text
=== Regresion contra la linea base
operacion                              base     actual  cambio
test_a_estrella                       1.673      1.602     -4%
test_dijkstra_heap                    4.191      3.963     -5%
test_cache_acierto                2.394e-05  2.383e-05     -0%
test_procesar_archivo_por_lotes       137.8      129.2     -6%
```

Para comparar dos versiones en la misma máquina también sirve
pytest-benchmark directamente:

```bash
pytest benchmarks/test_benchmark.py --benchmark-only --benchmark-autosave
# ... cambio ...
pytest benchmarks/test_benchmark.py --benchmark-only --benchmark-compare --benchmark-compare-fail=min:10%
```

## Profiling de CPU

`controles.py` perfila con **cProfile** el procesamiento de un archivo de
2.000 consultas sobre 3.600 nodos y guarda `reportes/perfil.prof` (se abre
con `snakeviz reportes/perfil.prof`) y `reportes/perfil.txt`:

```text
8562310 function calls in 2.333 seconds   (ordenado por tiempo propio)

 ncalls  tottime  cumtime  function
   2000    1.164    2.239  algoritmos.py:141(_busqueda_con_heap)
1448649    0.307    0.432  red.py:96(distancia_recta)
1207539    0.232    0.232  {built-in method _heapq.heappop}
1879612    0.177    0.177  {method 'get' of 'dict' objects}
1446649    0.148    0.148  {built-in method _heapq.heappush}
1448649    0.125    0.125  {built-in method math.hypot}
   2000    0.018    0.057  cache.py:152(_guardar)
```

**Conclusión:** el 96 % del tiempo es la búsqueda A* (`cumtime` 2,24 de
2,33 s), y dentro de ella la heurística (`distancia_recta`, 18 %) y el heap
(16 %). La lectura y escritura del archivo no aparecen entre las 15
funciones más costosas: el buffer y los lotes del parcial 2 ya resolvieron
la E/S. El profiling no bloquea la integración: es un reporte para decidir
qué optimizar.

## Complejidad

### Complejidad temporal de los algoritmos

| Algoritmo | Tiempo | Memoria |
|---|---|---|
| BFS | O(V + E) | O(V) |
| Dijkstra con lista | O(V²) | O(V) |
| Dijkstra con heap / A* | O((V + E) log V) | O(V) |
| Acierto de caché | O(1) | — |
| Cortar un tramo en la caché | O(rutas afectadas) | — |
| Procesar un archivo por streaming | O(n · costo de A*) | O(1) respecto del tamaño del archivo |

### Complejidad temporal medida (control del CI)

La tabla de arriba es teoría. `benchmarks/test_complejidad.py` la
**comprueba en cada cambio**: mide cada algoritmo en grillas de 400, 784,
1.600 y 3.136 nodos y ajusta una recta en escala log-log. Si el tiempo crece
como c·Vᵏ, la pendiente de esa recta es **k**. La velocidad de la máquina
solo cambia c, no k: el control da lo mismo en cualquier runner, sin línea
base. Cada tiempo se mide con `timeit.Timer.autorange()`, que repite la
operación hasta que la medición dure al menos 0,2 s, y se toma el mínimo de
3 mediciones: así los grafos chicos no quedan a merced del ruido de un
runner compartido.

| Contrato | Teoría | k medido (3 corridas) | Se rechaza si |
|---|---|---|---|
| Dijkstra con lista | O(V²) → k ≈ 2 | 2,00 · 2,00 · 2,00 | k < 1,7 o k > 2,3 |
| Dijkstra con heap | O(V log V) → k ≈ 1,1 | 1,14 · 1,14 · 1,14 | k > 1,4 |
| Leer un archivo 10 veces más grande, streaming | O(1) | memoria ×1,00 (146 KiB en los dos) | crece más de ×1,5 |
| Lo mismo con `readlines` (control del control) | O(n) | memoria ×11,26 | crece menos de ×5 |

El último contrato verifica que la prueba sabe distinguir: si `readlines` no
creciera, el control de streaming no estaría midiendo nada.

**¿Detecta un error real?** Plantamos el error clásico: en
`_busqueda_con_heap`, reemplazar `heapq.heappop` por `min()` sobre la lista
de pendientes. Todas las pruebas funcionales siguen pasando (las rutas son
las mismas), pero el exponente sube de **1,14 a 1,50** y el control rechaza
el cambio. No sube a 2 porque en una grilla la frontera tiene del orden de
√V nodos: el costo pasa a ser O(V·√V), es decir k ≈ 1,5. La medición
coincide con la teoría también en el error.

### Complejidad del código (control del CI)

**Lizard** rechaza el cambio si alguna función tiene complejidad ciclomática
mayor que 10, más de 50 líneas de código o más de 6 parámetros. **Radon**
genera el índice de mantenibilidad como reporte (`reportes/radon_mi.json`).

| Métrica | Límite | Valor actual |
|---|---:|---|
| Complejidad ciclomática máxima | 10 | 9 (`generar_red`); luego 7 (`dijkstra_lista`, `_busqueda_con_heap`, `red_argentina`) |
| Complejidad promedio | — | 2,1 según Lizard; 2,19 según Radon (111 bloques: 103 en rango A y 8 en rango B) |
| Líneas de código máximas por función | 50 | 28 (`mapa_svg`, `configurar_trazas`) |
| Parámetros máximos | 6 | 5 (`procesar_en_paralelo`, `_conectar`) |
| Índice de mantenibilidad (Radon) | — | todos los módulos en rango A (52 a 100) |

## Consumo de memoria

`benchmarks/test_memoria.py` mide el pico de memoria con **tracemalloc** y
falla si supera en más de un **20 %** la línea base:

| Operación | Pico medido | Límite (+20 %) |
|---|---:|---:|
| A* sobre 10.000 nodos, esquina a esquina | 1.121,7 KiB | 1.346 KiB |
| Procesar 5.000 consultas por lotes (con caché) | 10.976,3 KiB | 13.172 KiB |

- tracemalloc cuenta los objetos que crea Python, no la memoria total del
  proceso. Por eso da casi el mismo número en Windows y en Linux con la misma
  versión de Python: es una medición **reproducible**, que es lo que necesita
  un control automático.
- La memoria se mide en una prueba aparte de los tiempos: tracemalloc
  multiplica por 3 o 4 el tiempo del código que crea muchos objetos.
- En el procesamiento del archivo el pico lo pone la caché de rutas, no el
  archivo: la misma entrada procesada por streaming **sin** caché tiene un
  pico de 1.472 KiB contra 10.976 KiB con caché. Es el precio, medido, de no
  recalcular las consultas repetidas.
