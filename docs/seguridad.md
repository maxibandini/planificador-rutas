# Seguridad

## Riesgos identificados

| # | Riesgo | Dónde | Medida | Estado |
|---|---|---|---|---|
| R1 | Entradas inválidas en la API (ciudad inexistente, JSON mal formado, parámetro faltante) | `api.py` | `ConsultaInvalidaError` → HTTP 400 con mensaje; 14 pruebas de la API | Mitigado |
| R2 | Archivos de entrada mal formados o peligrosos (encoding, BOM, entrada = salida) | `archivos.py` | Validación antes de abrir la salida; error con número de línea; pruebas de archivos "raros" | Mitigado |
| R3 | Dependencias con vulnerabilidades conocidas (Flask, Werkzeug, OpenTelemetry...) | `requirements*.txt` | pip-audit en cada push + Dependabot semanal; versiones fijadas | Controlado en el CI |
| R4 | Secretos en el repositorio (tokens, contraseñas) | todo el repo | Gitleaks en cada push; el proyecto no usa credenciales (el endpoint OTLP es local y sin autenticación) | Controlado en el CI |
| R5 | Ejecución de comandos del sistema | `compiladores.py`, `controles.py` | Listas de argumentos fijas, nunca `shell=True` | Revisado (falso positivo, ver abajo) |
| R6 | Depurador de Werkzeug con `python servidor.py --desarrollo` (`debug=True` permite ejecutar código desde el navegador) | `servidor.py` | Solo se activa con la opción explícita y el servidor escucha únicamente en `127.0.0.1` | Riesgo aceptado, documentado |
| R7 | Consultas costosas que saturen el servidor (`/api/comparar` corre Dijkstra O(V²)) | `api.py` | El mapa de la API es fijo (24 ciudades); sin límite de peticiones | Fuera de alcance |
| R8 | Permisos del pipeline (un paso comprometido podría escribir en el repo) | `ci.yml` | `permissions: contents: read` por defecto; solo `publicar-docs` puede escribir, y solo en `main` | Mitigado |

**R6 lo encontramos leyendo el código, no con una herramienta.** Bandit tiene
la regla B201 (`flask_debug_true`), pero no la marcó: `servidor.py` no
importa `flask` directamente (recibe la app de `crear_app`) y la regla solo
mira archivos que lo importan. Es un **falso negativo**: las herramientas
reducen el trabajo de revisión, no lo reemplazan.

## Herramientas

| Requisito de la consigna | Herramienta | Qué analiza | Reporte |
|---|---|---|---|
| Analizar el código fuente | **Bandit** | Patrones inseguros en Python (`eval`, `shell=True`, `pickle`, hashes débiles, `debug=True`...) | `reportes/bandit.sarif` (SARIF, queda como artefacto del workflow) y salida de texto |
| Analizar las dependencias | **pip-audit** | Cada paquete fijado contra la base de vulnerabilidades de PyPI/OSV | `reportes/pip-audit.json` (JSON) y tabla legible |
| | **Dependabot** | Alertas de seguridad y pull requests semanales de actualización (pip y GitHub Actions) | Pull requests en GitHub |
| Detectar secretos | **Gitleaks** | Reglas para claves de AWS, tokens de GitHub, claves privadas, contraseñas en URLs... | `reportes/gitleaks.sarif` (SARIF) |
| Mantenibilidad / bugs (complementa) | **Ruff** (reglas `B` de bugbear) y **mypy** | Construcciones propensas a errores y contratos de tipos | Salida de texto |

Bandit y pip-audit se complementan: Bandit mira **nuestro** código y nunca
ve una vulnerabilidad de Werkzeug; pip-audit mira **las bibliotecas** y no
sabe qué hacemos con ellas.

## Política de bloqueo por severidad

| Hallazgo | Severidad | Acción |
|---|---|---|
| Bandit | **Alta** (con confianza media o alta) | **Bloquea** la integración |
| Bandit | Media | No bloquea. Se revisa en el pull request: se corrige o se registra como excepción con `# nosec <regla>` y justificación |
| Bandit | Baja | Informativa (queda en el SARIF) |
| pip-audit | Cualquier vulnerabilidad conocida | **Bloquea**. Si hay versión corregida, se actualiza el pin. Si no hay, se registra una excepción temporal (ver abajo) |
| Gitleaks | Cualquier secreto | **Bloquea** siempre. Un secreto que llegó a un commit se considera filtrado: se revoca y se rota, borrarlo del archivo no alcanza |
| Dependabot | Alerta crítica o alta | El pull request de actualización se revisa e integra en la semana |

¿Por qué pip-audit bloquea todo y no por severidad? Porque su salida no trae
puntaje CVSS, y nuestras dependencias son pocas (30 de ejecución): cada
alerta se puede analizar. Bloquear por defecto y exceptuar a mano es más
seguro que dejar pasar por defecto.

Con esto, la política cumple el ejemplo de la consigna: las vulnerabilidades
críticas confirmadas bloquean siempre, y las altas y medias se revisan antes
de integrar.

## Falsos positivos y excepciones

Cada excepción queda en el código, junto a la línea, con la regla exacta
(`# nosec B311`, nunca un `# nosec` genérico) y un comentario de por qué.
Bandit cuenta las excepciones en cada corrida (`Total potential issues
skipped due to specifically being disabled`), así que no pueden aparecer
sin que se note.

| Regla | Severidad | Dónde | Por qué es un falso positivo |
|---|---|---|---|
| B311 `random` no criptográfico | Baja | `red.py` (×2), `consultas.py` | Genera mapas y consultas **reproducibles** con semilla fija. No es criptografía: un generador seguro haría imposible repetir los experimentos |
| B404 / B603 `subprocess` | Baja | `compiladores.py`, `controles.py` | Ejecutan herramientas con listas de argumentos fijas, sin `shell=True` ni datos del usuario |
| B310 `urlopen` | Media | `carga_api.py` | La URL es la de la API local que levanta quien corre el script de carga. Revisado en el PR |

Excepciones de dependencias: hoy **ninguna**. Si una vulnerabilidad no
tuviera versión corregida, el procedimiento es:

1. Analizar si el código vulnerable se usa (por ejemplo, una falla en una
   función de Werkzeug que el proyecto no llama).
2. Agregar `--ignore-vuln <ID>` a `PIP_AUDIT` en `controles.py`, con un
   comentario que diga el motivo y la fecha de revisión.
3. Registrarla en esta tabla. Dependabot avisa cuando salga la corrección y
   la excepción se quita.

Excepciones de secretos: `.gitleaks.toml` excluye solo las carpetas
generadas (`reportes/`, `site/`). Un falso positivo puntual se agrega a
`.gitleaksignore` con su *fingerprint* y se documenta acá.

## Resultados actuales

| Control | Resultado |
|---|---|
| Bandit, severidad alta | 0 hallazgos (3.665 líneas analizadas; 9 excepciones documentadas arriba) |
| pip-audit | `No known vulnerabilities found` en las 97 dependencias fijadas |
| Gitleaks | **Sin verificar todavía.** No estaba instalado en la máquina donde escribimos esto (`controles.py` lo informa como *sin verificar* en lugar de aprobarlo) y el pipeline todavía no corrió en GitHub. Es lo primero que hay que confirmar en la primera corrida del CI |

## Medidas correctivas aplicadas

- **Versiones fijadas con dependencias indirectas.** En el parcial 2,
  `requirements.txt` decía `flask>=3.0`: cada instalación podía traer una
  versión distinta, y una auditoría de hoy no garantizaba nada sobre la de
  mañana. Ahora todas las versiones están fijadas y pip-audit audita
  exactamente lo que se instala.
- **Permisos mínimos en el pipeline** (R8).
- **Tipado estricto en los procesos hijos.** mypy encontró que las globales
  de los procesos hijos podían ser `None`; se corrigió la declaración (ver
  [Diseño técnico](diseno.md#decisiones-de-implementacion)).
- **Prueba de los controles:** plantamos `subprocess.run(..., shell=True)` y
  una dependencia vieja con vulnerabilidades conocidas para comprobar que el
  pipeline las rechaza (ver [Integración continua](ci.md#prueba-de-los-controles)).
