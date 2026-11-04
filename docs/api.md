# API y contratos

## API web (HTTP)

Se levanta con `python servidor.py` en <http://127.0.0.1:8000>. Todas las
respuestas son JSON. Los errores tienen siempre la forma `{"error": "mensaje"}`.

| Método y ruta | Entrada | Salida (200) | Errores |
|---|---|---|---|
| `GET /api/ciudades` | — | `{"ciudades": [...]}` ordenadas | — |
| `GET /api/ruta` | `origen`, `destino` (obligatorios), `algoritmo` (opcional: `A*`, `BFS`, `Dijkstra lista`, `Dijkstra heap`) | `origen`, `destino`, `algoritmo`, `ruta`, `costo`, `explorados`, `nodos_en_ruta`, `desde_cache` | 400 parámetro faltante, ciudad o algoritmo desconocidos; 404 sin ruta |
| `GET /api/comparar` | `origen`, `destino` | `algoritmos`: un objeto por algoritmo con `ruta`, `costo`, `explorados`, `nodos_en_ruta` | 400 |
| `POST /api/tramos/cortar` | JSON `{"a": ciudad, "b": ciudad}` | `{"tramo": [a, b], "invalidadas": n}` | 400 JSON inválido, ciudad o tramo inexistentes |
| `POST /api/reiniciar` | — | `{"ok": true}` | — |
| `GET /api/cache` | — | `consultas`, `aciertos`, `fallos`, `tasa_aciertos`, `guardadas`, `invalidadas`, `descartadas` | — |

### Ejemplos

Las salidas son reales, obtenidas con el cliente de pruebas de Flask.

```text
GET /api/ruta?origen=Ushuaia&destino=Salta                       -> 200
{"algoritmo": "A*", "costo": 4818.788, "desde_cache": false, "destino": "Salta",
 "explorados": 17, "nodos_en_ruta": 9, "origen": "Ushuaia",
 "ruta": ["Ushuaia", "Trelew", "Bahia Blanca", "Buenos Aires", "Parana",
          "Santa Fe", "Cordoba", "Tucuman", "Salta"]}

GET /api/ruta?origen=Ushuaia&destino=Salta    (otra vez)         -> 200
{... "desde_cache": true ...}

POST /api/tramos/cortar  {"a": "Santa Fe", "b": "Cordoba"}       -> 200
{"invalidadas": 1, "tramo": ["Santa Fe", "Cordoba"]}

GET /api/ruta?origen=Ushuaia&destino=Salta    (tramo cortado)    -> 200
{"costo": 4989.339, "desde_cache": false, "explorados": 20,
 "ruta": [..., "Buenos Aires", "Rosario", "Rio Cuarto", "Cordoba", ...]}

GET /api/ruta?origen=Ushuaia&destino=Gotham                      -> 400
{"error": "Ciudad desconocida: 'Gotham'"}

GET /api/ruta?origen=Ushuaia                                     -> 400
{"error": "Falta el parametro 'destino'"}

GET /api/ruta?origen=Ushuaia&destino=Salta&algoritmo=Magia       -> 400
{"error": "Algoritmo desconocido: 'Magia'"}

POST /api/tramos/cortar  {"a": "Rosario", "b": "Ushuaia"}        -> 400
{"error": "La ruta usa un tramo inexistente: Rosario-Ushuaia"}
```

Con `curl`:

```bash
curl "http://127.0.0.1:8000/api/ruta?origen=Ushuaia&destino=Salta"
curl -X POST -H "Content-Type: application/json" \
     -d '{"a": "Santa Fe", "b": "Cordoba"}' http://127.0.0.1:8000/api/tramos/cortar
```

## Contratos del paquete Python

Las funciones principales y lo que garantizan. El detalle completo, generado
desde los docstrings, está en la [referencia del código](referencia.md).

| Función | Entrada | Salida | Excepciones |
|---|---|---|---|
| `a_estrella(red, origen, destino)` (y los otros 3 algoritmos) | Red y dos nodos | `Resultado(ruta, costo, explorados)`; sin camino: `ruta=None`, `costo=inf` | `KeyError` si un nodo no está en la red (BFS devuelve `ruta=None`) |
| `Red.agregar_arista(a, b, peso)` | Nodos existentes y peso ≥ distancia recta (para que A* sea óptimo) | — | `KeyError` si un nodo no existe |
| `Red.peso(a, b)` | Dos nodos | Peso del tramo | `ValueError` si el tramo no existe |
| `CacheDeRutas.consultar(origen, destino)` | Dos nodos | `Resultado` (de la caché o calculado) | Las del algoritmo |
| `CacheDeRutas.cortar_tramo(a, b)` | Tramo existente | Cantidad de rutas invalidadas (0 si ninguna lo usaba) | — (la API valida antes con `Red.peso` y responde 400) |
| `archivos.en_lotes(iterable, tamanio)` | Cualquier iterable, `tamanio > 0` | Generador de listas | `ValueError` si `tamanio <= 0` |
| `archivos.procesar_por_lotes(red, entrada, salida)` | Archivo `origen;destino` por línea | Cantidad de consultas procesadas | `ValueError` si entrada y salida son el mismo archivo o una línea está mal formada; `FileNotFoundError` |

Ejemplo de uso:

```python
>>> from planificador.red import red_argentina
>>> from planificador.cache import CacheDeRutas
>>> cache = CacheDeRutas(red_argentina())
>>> resultado = cache.consultar("Ushuaia", "Salta")
>>> round(resultado.costo, 1), resultado.explorados
(4818.8, 17)

```

!!! info "Documentación viva"
    Los ejemplos `>>>` de estas páginas se ejecutan como pruebas (doctest) en
    cada push: si el código cambia y el ejemplo deja de ser cierto, el CI falla.
