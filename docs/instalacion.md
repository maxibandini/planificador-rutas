# Instalación y ejecución

## Requisitos

- Python 3.12 o superior (el CI usa 3.14; probado también en Windows 11 con
  3.14).
- Git.
- Opcional: [Gitleaks](https://github.com/gitleaks/gitleaks) para detectar
  secretos localmente y [Jaeger](https://www.jaegertracing.io/download/)
  para ver las trazas.

## Instalación

```bash
git clone https://github.com/maxibandini/planificador-rutas.git
cd planificador-rutas
python -m venv .venv
.venv\Scripts\activate              # Windows
source .venv/bin/activate           # Linux / macOS
pip install -r requirements-dev.txt # app + herramientas, versiones fijadas
```

`requirements.txt` alcanza para ejecutar la aplicación;
`requirements-dev.txt` lo incluye y agrega las herramientas de prueba,
análisis y documentación. Los dos fijan **todas** las versiones, también las
de las dependencias indirectas: la instalación es idéntica en cada máquina y
en el runner del CI.

!!! tip "OneDrive / Dropbox"
    Si el proyecto está en una carpeta sincronizada, conviene crear el
    entorno virtual fuera de ella: sincronizar miles de archivos del entorno
    enlentece todo.

Gitleaks (opcional, un solo ejecutable):

```bash
winget install Gitleaks.Gitleaks      # Windows
brew install gitleaks                 # macOS
```

## Configuración

No hace falta configurar nada para usar la aplicación. Los únicos parámetros
son argumentos de línea de comandos:

| Parámetro | Dónde | Por defecto |
|---|---|---|
| `--puerto` | `servidor.py` | `8000` (escucha en `127.0.0.1`) |
| `--telemetria`, `--endpoint` | `servidor.py` | apagada, endpoint OTLP de Jaeger local |
| `--desarrollo` | `servidor.py` | waitress (con la opción, el servidor de Flask) |
| `--rapido` | `banco.py`, `banco_es.py` | mediciones completas |

Las herramientas se configuran en archivos versionados: `pyproject.toml`
(Ruff, mypy, pytest, coverage), `mkdocs.yml` (documentación),
`.gitleaks.toml` (secretos), `.github/workflows/ci.yml` (pipeline),
`.github/dependabot.yml` y `benchmarks/linea_base.json` (rendimiento).

## Comandos

| Comando | Qué hace |
|---|---|
| `python main.py [origen] [destino]` | Demostración: 4 algoritmos, caché y corte de tramo |
| `python servidor.py [--telemetria]` | API web en <http://127.0.0.1:8000> |
| `python banco.py [--rapido]` | Tabla comparativa de algoritmos, caché y concurrencia |
| `python banco_es.py [--rapido]` | Archivos grandes: lectura, escritura, tubería, paralelo, SQLite |
| `pytest` | Las 122 pruebas (incluye los ejemplos de esta documentación) |
| `python controles.py` | **Todos los controles del CI** (ver [Mantenimiento](mantenimiento.md#controles-locales)) |
| `mkdocs serve` | Esta documentación en <http://127.0.0.1:8000> con recarga automática |

Ejemplo:

```text
$ python main.py Ushuaia Salta
  algoritmo         complejidad          distancia ciudades  explorados
  ----------------------------------------------------------------------
  BFS               O(V + E)               4,937 u.         8          24
  Dijkstra lista    O(V^2)                 4,819 u.         9          24
  Dijkstra heap     O((V+E) log V)         4,819 u.         9          24
  A*                O((V+E) log V)         4,819 u.         9          17
```
