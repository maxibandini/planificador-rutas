# Pruebas

## Estrategia

- **pytest** corre todo: las pruebas de `tests/`, los ejemplos de los
  docstrings (`--doctest-modules`), las clases escritas con `unittest` y los
  ejemplos `>>>` de esta documentación (`--doctest-glob=*.md`).
- Cada corrección de un error lleva un test que lo reproduce, y cada
  optimización una medición antes y después.
- Las pruebas funcionales son **deterministas**: los mapas y las consultas se
  generan con semilla fija. Las de rendimiento comparan **relaciones** (A más
  rápido que B), nunca tiempos absolutos.
- El CI rechaza el cambio si falla una sola prueba o si la cobertura de
  ramas baja del **90 %**.

```bash
pytest                                  # las 121 pruebas (~4 s)
pytest -m "not rendimiento"             # sin las de rendimiento relativo
python controles.py pruebas             # igual que el CI: con cobertura y reportes
```

## Casos de prueba

| Tipo | Archivo | Cant. | Ejemplos |
|---|---|---:|---|
| Unitarias: algoritmos | `test_algoritmos.py` | 20 | los tres óptimos dan el mismo costo con 5 semillas; costo informado = costo de la ruta; origen = destino; sin camino → `None` e `inf` |
| Unitarias: grafo | `test_red.py` | 12 | heurística admisible en todos los tramos; cortar un tramo lo saca en ambos sentidos; clase `unittest.TestCase` |
| Unitarias: caché | `test_cache.py` | 7 | un acierto no recalcula (con `unittest.mock`); LRU respeta la capacidad; cortar un tramo invalida solo las rutas afectadas |
| Integración: archivos | `test_archivos.py` | 21 | las cuatro tuberías dan la misma salida; archivo vacío, con BOM de Excel, en UTF-16; entrada = salida no borra los datos |
| Integración: API | `test_api.py` | 14 | cliente de pruebas de Flask: 200, 400 y 404; cortar tramo invalida y recalcula; la telemetría genera spans |
| Concurrencia | `test_concurrencia.py` | 3 | secuencial, hilos y procesos dan los mismos resultados en el mismo orden |
| Funcionales y utilidades | `test_formato.py`, `test_servidor.py` | 15 | `main.py` de punta a punta como lo usaría una persona; puerto ocupado |
| Rendimiento relativo | `test_rendimiento.py` | 5 | heap 5x más rápido que lista; acierto de caché 50x más rápido que calcular; streaming 20x menos memoria |
| Doctests | `planificador/*.py` | 19 | los `Example:` de los docstrings |
| Documentación viva | `docs/api.md`, `docs/diseno.md` | 2 | los ejemplos de la documentación: si el código cambia y el ejemplo deja de ser cierto, falla |
| Controles del CI | `test_controles.py` | 3 | un control que falla termina con código 1; una etapa desconocida, con código 2; un programa externo ausente queda *sin verificar*, no aprobado |
| **Total** | | **121** | |

Además, `benchmarks/` tiene 5 benchmarks, 2 controles de memoria y 3
contratos de complejidad que corren en la etapa de rendimiento (ver [Rendimiento](rendimiento.md)).

## Resultados

Corrida local (Ryzen 7 7800X3D, Windows 11, Python 3.14.6):

```text
121 passed in 3.38s
TOTAL   776 sentencias   35 sin cubrir   176 ramas   10 parciales   95 %
Required test coverage of 90.0% reached. Total coverage: 94.85%
```

| Módulo | Cobertura | Qué falta |
|---|---:|---|
| `algoritmos`, `red`, `consola`, `consultas` | 99-100 % | — |
| `api`, `archivos`, `cache` | 96-97 % | Caminos de error poco probables |
| `formato`, `mediciones` | 85-91 % | El bloque `__main__` de `formato` y `guardar_json`, que usan los scripts de medición |
| `concurrencia` | 79 % | Código que corre dentro de los procesos hijos: coverage no los mide por defecto |
| `telemetria` | 71 % | La corrección del reloj (solo corre en Windows con Python < 3.13) y el exportador OTLP real (los tests usan uno en memoria) |

Los reportes que deja el CI como artefacto (`reportes-pruebas`):
`pruebas.xml` (JUnit), `cobertura.xml` (Cobertura) y `cobertura/index.html`
(navegable línea por línea).

## Los controles también se prueban

Un control que nunca falla no controla nada. Para cada uno plantamos un
defecto en una copia del proyecto y verificamos que el pipeline lo rechaza.
El detalle está en [Integración continua](ci.md#prueba-de-los-controles).
