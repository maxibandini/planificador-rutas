# Registro de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [3.0.0] — Tercer parcial

### Agregado
- Documentación externa con MkDocs + Material for MkDocs (`docs/`,
  `mkdocs.yml`): descripción funcional, arquitectura, instalación, diseño
  técnico, API y contratos, pruebas, rendimiento, seguridad, integración
  continua y mantenimiento. La referencia del código se genera desde los
  docstrings con mkdocstrings.
- Pipeline de CI en GitHub Actions (`.github/workflows/ci.yml`) con siete
  etapas: calidad estática, pruebas y cobertura, seguridad de dependencias,
  documentación, rendimiento y memoria, resultado final y publicación de la
  documentación en GitHub Pages.
- `controles.py`: los controles del CI para correr localmente.
- `benchmarks/`: benchmark con pytest-benchmark, control de memoria con
  tracemalloc y `linea_base.json`.
- `benchmarks/test_complejidad.py`: contratos de complejidad. El exponente
  de crecimiento medido (regresion log-log) tiene que coincidir con el
  teorico: Dijkstra con lista k ~ 2, con heap k ~ 1,1; streaming con
  memoria constante.
- Documentacion viva: los ejemplos `>>>` de `docs/*.md` se ejecutan como
  doctests en el CI.
- `docs/evolucion.md`: el pipeline del parcial 3 aplicado al codigo del
  parcial 2.
- Configuración de mypy, umbral de cobertura (90 %), Lizard, Bandit con
  reporte SARIF, pip-audit, Gitleaks (`.gitleaks.toml`) y Dependabot.

### Cambiado
- `requirements.txt` y `requirements-dev.txt` fijan todas las versiones,
  también las de las dependencias indirectas.
- Python mínimo: 3.12 (sintaxis de tipos genéricos de PEP 695 en
  `archivos.en_lotes`).
- Las 6 correcciones que pidió mypy: globales de los procesos hijos sin `None`,
  tipo de retorno de `_abrir_salida`, clave del `sorted` de `red_argentina`
  con `functools.partial`, tupla de dos elementos explícita y `type: ignore`
  con código en la corrección del reloj de `telemetria`.

### Eliminado
- Sphinx (reemplazado por MkDocs), `ARCHITECTURE.md` y `CONTRIBUTING.md`
  (su contenido está en `docs/arquitectura.md` y `docs/mantenimiento.md`).
- `calidad.py`: el reporte local estilo SonarQube lo reemplazan los
  controles del CI.

## [2.0.0] — Segundo parcial

### Agregado
- `planificador/archivos.py`: lectura en streaming y por lotes, escritura con
  buffer y con `writelines`, tubería completa en cuatro versiones (ingenua,
  streaming, lotes + caché, paralela) e inserción en SQLite fila por fila
  contra `executemany` por lotes.
- `banco_es.py`: mediciones de E/S con archivos de hasta 1.000.000 de líneas.
- `planificador/api.py`: API web con Flask (rutas JSON, página con mapa SVG,
  corte de tramos, estadísticas de caché) servida con waitress.
- `planificador/telemetria.py`: trazas OpenTelemetry exportadas a Jaeger por
  OTLP, con spans propios para la capa de servicio y para cada cálculo de A*.
- `perfilado.py`: perfil de la tubería de archivos, memoria de la lectura y
  modo `--carga` para perfilar con py-spy y Scalene.
- `calidad.py`: reporte estilo SonarQube con Pylint, Ruff, pycodestyle,
  Bandit, Radon y pytest-cov, comparando ambos parciales.
- Suite de 116 tests (pytest): unitarios, integración con el cliente de Flask,
  regresión, rendimiento con `timeit`, mocks y doctests. Cobertura: 96 %.
- Documentación con Sphinx (`docs/`), `ARCHITECTURE.md`, `CONTRIBUTING.md`.
- `pyproject.toml` con la configuración de todas las herramientas.
- `mediciones.mejor_de`: mínimo de varias corridas, como `timeit`.
- `compiladores.py`: las mismas cargas en CPython y en PyPy (compilador JIT).

### Cambiado
- Código organizado como paquete `planificador/` con los scripts afuera.
- Docstrings estilo Google en todos los módulos, clases y funciones, con
  ejemplos ejecutables (doctest) y anotaciones de tipo (PEP 484).
- PEP 8 con líneas de 79 caracteres, formateado con Ruff.
- `banco.py`: `main()` de 95 sentencias dividido en funciones `medir_*` e
  `imprimir_*`; la tabla comparativa ahora se arma desde una lista de etapas.
- `main.py`: dividido en funciones; reutiliza el resultado de A* en lugar de
  calcularlo dos veces.
- `CacheDeRutas`: los cuatro contadores pasaron a un `dataclass Contadores`
  (Pylint marcaba demasiados atributos); una sola búsqueda en el diccionario
  por consulta; `itertools.pairwise` en lugar de `zip(ruta, ruta[1:])`.
- `Red._conectar`: el rango del factor se pasa como tupla (lista larga de
  parámetros); nuevo método `Red.peso` y soporte de `nodo in red`.
- `concurrencia.crear_pool` acepta un inicializador y lo reutilizan los
  procesos de archivos.
- Nombres más descriptivos (`frontera`, `costo_hasta`, `fila`/`columna`,
  `ConsultaInvalidaError`).

### Eliminado (código redundante)
- `titulo()` copiada en `main.py`, `banco.py` y `perfilado.py` → `consola.py`.
- `cronometrar()` copiada en `banco.py` y `concurrencia.py` → `mediciones.py`.
- `generar_lote()` y `generar_consultas()`, casi iguales → `consultas.py`.
- `dijkstra_heap` y `a_estrella` (mismo algoritmo, solo 4 líneas distintas) →
  `_busqueda_con_heap`.
- `con_procesos`, `rutas_con_procesos` y `medir_arranque_de_pool` repetían la
  creación del pool → `crear_pool` y `_mapear_en_procesos`.
- Demostraciones en los `__main__` de `algoritmos.py`, `cache.py`,
  `concurrencia.py` y `red.py` que repetían lo que ya muestran `main.py` y
  `banco.py`.
- Segundo cálculo de A* en `main.py` y de `factor_v` en `banco.py`.
- Cronómetros escritos a mano en `banco.medir_escalabilidad` y
  `concurrencia.medir_arranque_de_pool` → `cronometrar()`.
- "Resolver todas las consultas" repetido en `concurrencia` y `banco` →
  `concurrencia.secuencial(red, consultas, algoritmo)`.
- `Red.version`: se incrementaba pero nadie lo leía (código muerto).

### Corregido
- `main.py` fallaba con `IndexError` cuando la ruta óptima tenía menos de
  cuatro ciudades (por ejemplo `python main.py Rosario "Santa Fe"` o con
  origen igual a destino).
- Los mensajes de conclusión de los bancos dependen de lo medido y no son
  fijos.
- La tabla comparativa medía el tiempo con `tracemalloc` activo, que hacía
  3 o 4 veces más lentos a Dijkstra con heap y a A* y no veía a los procesos
  hijos. Ahora el tiempo y la memoria se miden en pasadas separadas.
- Spans de OpenTelemetry con duración 0 en Windows con Python < 3.13: el SDK
  usa un reloj basado en `perf_counter_ns`.
- `tracemalloc` se importa solo al medir memoria: PyPy no lo implementa.
- Encontrado con una prueba adversarial:
  - `servidor.py` avisa y sale si el puerto ya está en uso (en Windows
    arrancaba igual y respondía el servidor viejo).
  - `POST /api/tramos/cortar` con un JSON que no es objeto daba 500;
    ahora 400. También recorta los espacios.
  - Archivos con BOM se leen bien (`utf-8-sig`); espacios alrededor de
    las ciudades se recortan; un archivo que no es UTF-8 da un error con
    número de línea.
  - Si la entrada no existe o es el mismo archivo que la salida, se
    rechaza antes de abrir la salida (antes se perdían los datos).
  - `--rapido` guarda en `*_rapido.json` y no pisa las mediciones del
    informe.
  - `compiladores.py` y `calidad.py` validan sus argumentos.

## [1.0.0] — Primer parcial

- Grafo con lista de adyacencia, BFS, Dijkstra con lista y con heap, A*.
- Memoización con `lru_cache` y caché con invalidación selectiva y LRU.
- Secuencial, hilos y procesos; perfilado con cProfile, line_profiler y
  memory_profiler; tabla comparativa sobre 12.100 nodos.
