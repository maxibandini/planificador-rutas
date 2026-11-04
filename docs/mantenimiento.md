# Mantenimiento

## Flujo de trabajo

1. Crear una rama desde `main`: `git switch -c feature/nombre-del-cambio`.
2. Hacer el cambio **con su prueba** (o su medición, si es una optimización)
   y, si cambia el comportamiento, actualizar la página de `docs/` que
   corresponda.
3. Correr los controles localmente: `python controles.py`.
4. Push y abrir un pull request hacia `main`.
5. El CI corre solo. Con el check `resultado` en verde y la aprobación del
   otro integrante, se integra.

Configuración del repositorio (*Settings*), hecha una sola vez:

| Dónde | Qué |
|---|---|
| *Branches → Branch protection rules → `main`* | Exigir pull request con 1 aprobación; exigir el status check `resultado`; no permitir push directo |
| *Collaborators* | Solo los dos integrantes (y el docente, con permiso de lectura) |
| *Pages* | Fuente: rama `gh-pages` (la crea `mkdocs gh-deploy`) |
| *Code security* | Activar *Dependabot alerts* y *Dependabot security updates* |

## Estilo

- **PEP 8** con líneas de hasta 79 caracteres. No hace falta acomodar a mano:
  `ruff format .` reescribe el código y `ruff check --fix .` arregla lo que
  puede.
- **Nombres** en castellano y descriptivos: `snake_case` para funciones y
  variables, `CamelCase` para clases, `MAYUSCULAS` para constantes; las
  excepciones terminan en `Error`.
- **Docstrings** estilo Google en todo módulo, clase y función pública, con
  `Args`, `Returns`, `Raises` y, si se puede, un `Example` (es un doctest).
- **Tipos** en las firmas del paquete: mypy los controla.

## Controles locales

`controles.py` tiene la lista de controles y el CI la usa tal cual: lo que
pasa localmente es lo que pasa en GitHub.

```bash
python controles.py                 # todo, en el orden del pipeline (~1 min)
python controles.py calidad         # Ruff, mypy, Lizard, Radon, Bandit, Gitleaks
python controles.py pruebas         # pytest + cobertura >= 90 %
python controles.py seguridad       # pip-audit
python controles.py documentacion   # mkdocs build --strict
python controles.py rendimiento     # benchmark, regresión, memoria, complejidad, cProfile
python controles.py calidad pruebas # varias etapas
```

Al final imprime `APROBADO` o `RECHAZADO` con la lista de controles que
fallaron, y termina con código 1 si alguno falló. Los reportes quedan en
`reportes/` (ignorada por git).

**Gitleaks** (secretos) no es de Python: se instala con `winget install
Gitleaks.Gitleaks`. Si no está instalado, `controles.py` no lo da por
aprobado: al final lo lista como **sin verificar en esta máquina**. En el
CI corre siempre (se descarga en una versión fija).

Cada herramienta también se puede correr suelta, con los mismos argumentos
que figuran en la [matriz de controles](ci.md#matriz-de-controles).

## Resolver fallos del pipeline

Primero, abrir el job en rojo en la pestaña *Actions* y ver qué control
falló; el detalle está en el log y en el artefacto `reportes-*`. Después,
reproducirlo localmente con la etapa correspondiente.

| Falla | Reproducir | Cómo se resuelve |
|---|---|---|
| Ruff | `ruff check .` | `ruff check --fix .` y `ruff format .`; lo que quede se corrige a mano. Un falso positivo se ignora en la línea con `# noqa: <regla>` y un comentario |
| Ruff formato | `ruff format --check .` | `ruff format .` |
| mypy | `mypy` | Corregir el tipo. `# type: ignore[<código>]` solo si es un falso positivo, siempre con el código (mypy avisa si queda un ignore sin usar) |
| Lizard | `lizard planificador -C 10 -T nloc=50 -a 6 -w` | Dividir la función (extraer funciones), agrupar parámetros en una tupla o clase |
| Bandit | `bandit -r . -x ./tests,./benchmarks` | Corregir el patrón inseguro. Si es un falso positivo, `# nosec <regla>` con justificación y registrarlo en [Seguridad](seguridad.md#falsos-positivos-y-excepciones) |
| Gitleaks | `gitleaks dir . --redact -v` | **Revocar y rotar el secreto** (ya está en el historial); sacarlo del código y leerlo de una variable de entorno. Falso positivo: `.gitleaksignore` |
| pytest | `pytest -x --lf` | Corregir el código o, si el comportamiento cambió a propósito, la prueba |
| Cobertura | `pytest --cov --cov-report=term-missing` | Agregar pruebas para las líneas listadas en *Missing* |
| pip-audit | `python controles.py seguridad` | Subir el pin a la versión corregida que indica la columna *Fix Versions* en `requirements*.txt`; si no hay corrección, ver [excepciones](seguridad.md#falsos-positivos-y-excepciones) |
| MkDocs | `mkdocs build --strict` | El mensaje dice el archivo y el enlace o ancla rota |
| Benchmark | `python controles.py rendimiento` | Ver qué operación marcó `REGRESION`, perfilar (`reportes/perfil.txt`, `snakeviz reportes/perfil.prof`) y corregir. Si el cambio es a propósito (por ejemplo, más funcionalidad), regenerar la línea base y justificarlo en el PR |
| Complejidad medida | `pytest benchmarks/test_complejidad.py` | El exponente no coincide con la teoría: casi siempre es una estructura de datos equivocada (una lista donde iba un heap, `list.pop(0)` donde iba un `deque`, una lista donde iba un `set`). No tiene línea base: se corrige el código |
| Ejemplo de la documentación | `pytest docs` | El mensaje muestra `Expected` y `Got`: si el comportamiento nuevo es el correcto, se actualiza el ejemplo en el mismo PR |
| Memoria | `pytest benchmarks/test_memoria.py` | El mensaje dice el pico y el límite. Buscar listas o copias innecesarias; igual que el benchmark, la línea base solo se actualiza con justificación |
| Falla al instalar | `pip install -r requirements-dev.txt` | Una versión fijada se retiró de PyPI o no tiene wheel para la versión de Python: actualizar el pin |

### Actualizar la línea base de rendimiento

```bash
python controles.py linea-base      # mide en esta máquina y reescribe benchmarks/linea_base.json
```

O desde GitHub: *Actions → CI → Run workflow* con *linea_base* marcado; el
archivo nuevo queda en el artefacto `reportes-rendimiento`. En los dos casos
el cambio entra por pull request, para que se vea y se discuta.

### Actualizar dependencias

Dependabot abre un pull request por semana con las versiones nuevas (las de
OpenTelemetry agrupadas en uno solo, porque se publican juntas). El CI corre
sobre ese pull request: si pasa, se integra. Para agregar una dependencia a
mano: instalarla en un entorno limpio, `pip freeze` y copiar las líneas
nuevas a `requirements.txt` (o `requirements-dev.txt` si es una
herramienta).

## Documentación

```bash
mkdocs serve           # vista previa con recarga en http://127.0.0.1:8000
mkdocs build --strict  # lo mismo que el CI
```

Las páginas están en `docs/`; la referencia del código se arma sola desde
los docstrings. Se publica en GitHub Pages cuando el cambio llega a `main`.

!!! note "Fin de vida de Material for MkDocs"
    MkDocs avisa que Material for MkDocs recibe correcciones de seguridad
    hasta el 5 de mayo de 2027. Su sucesor, Zensical (del mismo equipo), lee
    el mismo `mkdocs.yml`: la migración es cambiar la herramienta en
    `requirements-dev.txt` y el comando de construcción. Mientras tanto la
    variable `NO_MKDOCS_2_WARNING=1` del CI oculta el aviso.
