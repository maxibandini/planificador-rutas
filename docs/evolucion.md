# Evolución desde el parcial 2

El tercer parcial no cambia qué hace el planificador: cambia **cómo se
garantiza** que siga haciéndolo bien. En el parcial 2 la calidad se medía a
mano (`python calidad.py` generaba un reporte); en el parcial 3 se exige
automáticamente en cada cambio, y un cambio que no cumple no se integra.

## De medir a exigir

| Aspecto | Parcial 2 | Parcial 3 |
|---|---|---|
| Cuándo se controla la calidad | Cuando alguien se acuerda de correr `calidad.py` | En cada push y pull request, automáticamente |
| Qué pasa si algo empeora | El reporte lo muestra; nada lo impide | El pull request no se puede integrar |
| Controles que bloquean | 0 (solo reporte) | 12: Ruff, formato, mypy, Lizard, Bandit, Gitleaks, pytest + cobertura, pip-audit, MkDocs, benchmark, memoria, complejidad |
| Rendimiento | Medido una vez para el informe (`banco.py`) | Medido en cada cambio contra una línea base, con tolerancia |
| Complejidad temporal | Explicada en el informe (O(V²) contra O((V+E) log V)) | **Medida en cada cambio**: el exponente de crecimiento tiene que coincidir con la teoría |
| Dependencias | 5 de ejecución y 16 de desarrollo con `>=` (cada instalación podía traer otra versión) | 97 versiones exactas, incluidas las indirectas; Dependabot propone las actualizaciones |
| Seguridad | Bandit dentro del reporte | Bandit + pip-audit + Gitleaks, política de bloqueo por severidad y falsos positivos documentados |
| Tipado | Anotaciones sin verificar | mypy en el CI: **6 errores reales** encontrados y corregidos |
| Documentación | Sphinx, 7 páginas, se generaba a mano | MkDocs, 13 páginas, publicada sola en cada cambio a `main` |
| Ejemplos de la documentación | Podían quedar viejos sin que nadie lo notara | Se ejecutan como pruebas (doctest): si dejan de ser ciertos, el CI falla |
| Reproducir los controles | Cada herramienta con su comando | `python controles.py`: los mismos comandos que el CI |

## El pipeline del parcial 3 aplicado al código del parcial 2

Para medir la evolución con el mismo instrumento, corrimos `controles.py`
del parcial 3 sobre una copia del código del parcial 2 (mismo
`pyproject.toml`, mismos tests, misma línea base):

| Etapa | Código del parcial 2 | Código del parcial 3 |
|---|---|---|
| Ruff | **Rechazado**: `UP047` (sintaxis de tipos genéricos vieja para Python ≥ 3.12) | Aprobado |
| mypy | **Rechazado**: 6 errores | Aprobado |
| Lizard, Bandit | Aprobado | Aprobado |
| pytest + cobertura | Aprobado: las 118 pruebas del parcial 3 (116 + 2 de la documentación), 94,85 % | Aprobado: 118 pruebas + 3 de `controles.py`, 94,85 % |
| pip-audit | **Rechazado**: `requirement flask is not pinned to an exact version: flask>=3.0` | Aprobado: 97 dependencias, 0 vulnerabilidades |
| Benchmark | +0 % a +4 % contra la línea base | −1 % a +5 % |
| Memoria y complejidad | Aprobado | Aprobado |
| **Resultado** | **RECHAZADO** (3 controles) | **APROBADO** |

Lo que dice esta tabla:

1. **El código del parcial 2 funcionaba** (las mismas pruebas pasan) y
   **rendía igual** (el benchmark no cambia): el parcial 3 no tocó la lógica.
2. **Pero no era verificable**: tenía errores de tipos que nadie había
   detectado y dependencias que podían cambiar solas. El CI convirtió eso en
   errores concretos, con archivo y línea.
3. **Las correcciones no costaron rendimiento**: el benchmark del código del
   parcial 3 queda dentro del ruido (±5 %) del código del parcial 2.

## Los 6 errores que encontró mypy

| Archivo | Error | Corrección |
|---|---|---|
| `concurrencia.py:46` | `a_estrella` recibe `Red \| None` | La global del proceso hijo se declara `Red`, sin `None`: el initializer siempre la asigna |
| `archivos.py:505` | `CacheDeRutas \| None` no tiene `.red` | Igual que el anterior |
| `archivos.py:310` | `open()` devuelve `IO[Any]`, se declaraba `TextIO` | Tipo de retorno `IO[str]` |
| `red.py:293` | No puede inferir el tipo de una `lambda` con argumento por defecto | `functools.partial(red.distancia_recta, ciudad)` |
| `red.py:298` | `tuple(sorted(...))` es `tuple[str, ...]`, no un par | `a, b = sorted(...)` y `(a, b)` |
| `telemetria.py:80` | Asignar `time_ns` a un módulo | Es a propósito (corrige el reloj de Windows): `# type: ignore[attr-defined]` con el código exacto |

Ninguno rompía las pruebas, y ese es justamente el punto: eran contratos
falsos (una función decía recibir algo que no siempre recibía) que un cambio
futuro podía convertir en un error real.

## Qué se mantuvo

Los algoritmos, la caché, la API, la telemetría y las 116 pruebas del
parcial 2 están igual. El parcial 3 agregó 5 pruebas (los 2 ejemplos de esta
documentación y 3 de `controles.py`) y 10 controles de rendimiento en `benchmarks/` (5 benchmarks,
2 de memoria y 3 de complejidad).
