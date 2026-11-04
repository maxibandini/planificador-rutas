# Informe del tercer parcial

**Planificador inteligente de rutas** · Programación Eficiente ·
Máximo Bandini y Lucas Caminos

Este informe recorre la consigna punto por punto. Cada sección empieza con
lo que dice la cátedra sobre el tema (con el número de diapositiva) y cómo lo
aplicamos. El detalle técnico está en la documentación (`docs/`, se ve con
`mkdocs serve`). Todo se reproduce con `python controles.py`.

**Equipo de medición:** AMD Ryzen 7 7800X3D, Windows 11, Python 3.14.6.

## Resumen

| Consigna | Qué hicimos | Resultado |
|---|---|---|
| 1. Documentación externa | MkDocs + Material, 13 páginas en el repositorio | Los 9 contenidos mínimos; los ejemplos se ejecutan como pruebas |
| 1. Controles en local | `controles.py`: el CI y cada integrante corren los mismos comandos | `python controles.py` → APROBADO en ~40 s |
| 2. Pipeline de CI | GitHub Actions en cada push y pull request a `main` | 7 etapas y un único check obligatorio |
| 2.2. Matriz de controles | Las 11 filas, con herramienta, comando, reporte y criterio | 12 controles que bloquean y 2 reportes |
| 2.2. Seguridad | Bandit, pip-audit, Gitleaks, Dependabot | Política por severidad, falsos positivos documentados |
| 3. Diseño por etapas | Lo rápido primero, lo independiente en paralelo | Calidad → pruebas / seguridad / documentación → rendimiento |
| 3.1. Si un control falla | Un defecto plantado por control | 13 de 13 rechazados |
| Evolución | El pipeline nuevo corrido sobre el código del parcial 2 | Parcial 2: RECHAZADO; parcial 3: APROBADO, mismo rendimiento |

---

## 1. Documentación externa

> **De la cátedra · diap. 340 y 349.** La documentación externa (README,
> guías, documentación técnica) da la visión general del proyecto: cómo está
> estructurado, qué decisiones de diseño se tomaron y cómo usar o modificar
> las optimizaciones. Hay que documentar el *qué* y el *por qué*.
>
> **Cómo y por qué lo aplicamos.** Cada decisión de la documentación tiene
> al lado la medición que la justifica (`diseno.md`), así quien la lea sabe
> qué no tocar. Y la escribimos en el mismo repositorio que el código para
> que se revise junto con cada cambio y no quede atrasada.

**Herramienta:** MkDocs con Material for MkDocs. En el parcial 2 usamos
Sphinx; MkDocs permite escribir en Markdown y, con mkdocstrings, sigue
generando la referencia del código desde los docstrings.

**Lugar compartido y acceso:** el repositorio (solo los colaboradores
escriben; `main` protegida con pull request y aprobación del otro
integrante). El CI publica el sitio en GitHub Pages cuando un cambio llega a
`main` y pasa todos los controles.

| Contenido mínimo | Página |
|---|---|
| Descripción funcional | `funcional.md`: problema, alcance, requisitos funcionales y no funcionales (cada uno con el control que lo verifica) |
| Arquitectura | `arquitectura.md`: diagrama de componentes y de secuencia, módulos y dependencias |
| Instalación y ejecución | `instalacion.md` |
| Diseño técnico | `diseno.md`: estructuras de datos, complejidades y decisiones con su medición |
| API y contratos | `api.md` (salidas reales de la API) y `referencia.md` (desde los docstrings) |
| Pruebas | `pruebas.md`: estrategia, 121 casos por tipo, cobertura por módulo |
| Rendimiento | `rendimiento.md`: benchmark, profiling, complejidad teórica y medida, memoria |
| Seguridad | `seguridad.md`: riesgos, política de bloqueo, falsos positivos |
| Mantenimiento | `mantenimiento.md`: cómo contribuir y una tabla *fallo → cómo reproducirlo → cómo se resuelve* |

**Requisito adicional (controles en local):** cada job del CI ejecuta
`python controles.py <etapa>`. La lista de controles existe una sola vez,
así que lo que corremos antes de hacer push es exactamente lo que corre el
CI. Si una herramienta externa no está instalada (Gitleaks), el script no la
da por aprobada: la informa como *sin verificar*.

## 2. El pipeline de integración continua

> **De la cátedra · diap. 350 y 351.** La integración continua incorpora
> frecuentemente los cambios a un repositorio compartido y ejecuta
> automáticamente controles para **detectar errores cuanto antes**. La
> validación de eficiencia comprueba que el software use bien los recursos y
> cumpla los requisitos de rendimiento. CI puede detectar problemas con
> tests, benchmarks, profiling, análisis estático, cobertura, complejidad y
> consumo de memoria.
>
> **Cómo y por qué lo aplicamos.** Usamos exactamente esa lista como etapas
> del pipeline. "Cuanto antes" lo tomamos literal: primero lo que tarda
> segundos, y lo costoso solo si lo anterior pasó.

```text
push / PR ──► calidad ──┬──► pruebas ──► rendimiento ──┐
                        ├──► seguridad ─────────────────┼──► resultado ──► publicar docs
                        └──► documentación ─────────────┘                  (solo main)
```

- **Lo rápido primero:** Ruff, mypy, Lizard, Bandit y Gitleaks tardan
  segundos. Si fallan, no se gasta tiempo en lo demás.
- **En paralelo lo independiente:** seguridad y documentación no dependen de
  las pruebas.
- **Lo costoso al final:** el rendimiento espera a las pruebas, porque medir
  código incorrecto no sirve.
- **Un resultado único:** el job `resultado` resume todas las etapas y es el
  check que exige la protección de `main`.
- **Reproducible:** Python 3.14 y las 97 dependencias con versión exacta;
  los reportes quedan como artefactos aunque la etapa falle.

## 3. Matriz de controles

| Control | Herramienta | Reporte | Rechaza si |
|---|---|---|---|
| Pruebas | pytest (+ doctest y unittest) | JUnit XML | Falla una prueba |
| Cobertura | coverage.py | XML y HTML | Cobertura de ramas < 90 % (hoy 94,85 %) |
| Análisis estático | Ruff | Texto | Cualquier error o archivo sin formatear |
| Tipado | mypy | Texto | Cualquier error en `planificador/` |
| Complejidad | Lizard (+ Radon, reporte) | JSON | Complejidad ciclomática > 10, > 50 líneas o > 6 parámetros |
| Vulnerabilidades | Bandit | SARIF | Severidad alta |
| Secretos | Gitleaks | SARIF | Cualquier secreto |
| Dependencias | pip-audit + Dependabot | JSON | Vulnerabilidad conocida |
| Documentación | MkDocs `--strict` | Sitio | No construye o hay un enlace roto |
| Benchmark | pytest-benchmark | JSON | > 30 % más lento que la línea base |
| Memoria | tracemalloc | JSON | Pico > 20 % sobre la línea base |
| Profiling | cProfile | `.prof` y texto | No bloquea: sirve para decidir qué optimizar |

> **De la cátedra · diap. 284 y 293.** Las pruebas de rendimiento con
> `timeit` sirven para asegurar que las optimizaciones *realmente* mejoran el
> código. Y no se optimiza sin medir: primero código claro y correcto, después
> se mide y se optimiza solo donde hay evidencia.
>
> **Cómo y por qué lo aplicamos.** El benchmark y la memoria corren en cada
> cambio, así que una optimización que empeora algo se ve antes de integrarla.
> Pero un CI tiene un problema que la diapositiva no tiene: la máquina cambia.

Por eso **no todos los controles usan el mismo criterio**:

- Pruebas y análisis estático son deterministas: tolerancia cero.
- **Benchmark:** el runner de GitHub, la notebook y la PC tienen velocidades
  distintas, así que un umbral en milisegundos no sirve. Cada operación se
  divide por una referencia en Python puro medida en la misma corrida, se
  toma el mínimo de varias rondas (el ruido solo suma tiempo) y ese cociente
  se compara con la línea base. Entre corridas la variación fue de ±4 %; la
  tolerancia es 30 %.
- **Memoria:** tracemalloc cuenta objetos Python, no memoria del sistema
  operativo, y da casi el mismo número en Windows y en Linux. Tolerancia 20 %.

El profiling confirma lo que ya sabíamos del parcial 2: el 96 % del tiempo de
procesar un archivo es A*, y la E/S ya no figura entre las 15 funciones más
costosas.

## 4. Seguridad

> **De la cátedra · diap. 355.** Herramientas para detectar
> vulnerabilidades: Bandit (patrones inseguros en código Python), Semgrep,
> OSV-Scanner (dependencias), **Gitleaks** (secretos y credenciales expuestas)
> y Trivy.
>
> **Cómo y por qué lo aplicamos.** Elegimos una herramienta por cada cosa
> que pide la consigna: Bandit para el código, pip-audit para las
> dependencias y Gitleaks para los secretos. Agregar Semgrep u OSV-Scanner
> repetiría lo mismo con otra herramienta.

| Hallazgo | Acción |
|---|---|
| Bandit, severidad alta | **Bloquea** |
| Bandit, severidad media | Se revisa en el pull request: se corrige o se documenta |
| Bandit, severidad baja | Queda en el reporte SARIF |
| pip-audit, cualquier vulnerabilidad | **Bloquea**; se sube la versión fijada |
| Gitleaks, cualquier secreto | **Bloquea**; el secreto se revoca y se cambia |

pip-audit bloquea todo porque no informa la gravedad (CVSS) y son pocas
dependencias: es más seguro bloquear y exceptuar a mano, con fecha de
revisión, que dejar pasar. Hay 9 falsos positivos documentados en el código
con su regla (`# nosec B311`: el `random` genera mapas reproducibles, no
claves).

**Un falso negativo que encontramos leyendo el código:** `servidor.py
--desarrollo` arranca Flask con `debug=True`, que permite ejecutar código
desde el navegador. Bandit tiene una regla para eso, pero no lo marcó porque
el archivo no importa `flask` directamente. Quedó documentado como riesgo
aceptado (el servidor solo escucha en `127.0.0.1`).

**Medida correctiva:** en el parcial 2 las dependencias decían `flask>=3.0`,
así que cada instalación podía traer otra versión. Ahora las 97 versiones
están fijadas y pip-audit audita exactamente lo que se instala.

## 5. Qué pasa si un control falla

> **De la cátedra · diap. 272.** Los tests aseguran que los cambios no rompan
> lo que ya funcionaba y que el software sea confiable.
>
> **Cómo y por qué lo aplicamos.** Con los controles pasa lo mismo: si nunca
> los vimos fallar, no sabemos si controlan algo. Por eso plantamos un
> defecto por control y comprobamos que el pipeline lo rechaza.

| Control | Defecto plantado | Resultado |
|---|---|---|
| Ruff | `import os` sin usar | Rechazado (F401) |
| mypy | `def doble(x: int) -> int: return str(x * 2)` | Rechazado |
| Lizard | Función con 12 `if` encadenados | Rechazado: complejidad 13 |
| Bandit | `subprocess.run(comando, shell=True)` | Rechazado: B602, severidad alta |
| pytest | El sentido de vuelta de cada tramo con el doble de peso | Rechazado: Ushuaia–Salta de 4.818,8 a 6.111,2 |
| Cobertura | Módulo de 80 líneas sin pruebas | Rechazado: 87,43 % |
| pip-audit | `requests==2.19.0` | Rechazado: 10 vulnerabilidades conocidas |
| MkDocs | Enlace a una página que no existe | Rechazado |
| Benchmark | A* calcula dos veces la misma ruta | Rechazado: +107 % |
| Memoria | A* copia la lista de adyacencia | Rechazado: 2.070 KiB, límite 1.346 |
| Complejidad | `min()` sobre una lista en lugar del heap | Rechazado: k = 1,51 (las pruebas pasaban) |
| Documentación | Un ejemplo de `api.md` con un número viejo | Rechazado |
| Gitleaks | Un token de GitHub de prueba en el código | Rechazado: regla `github-pat` |

Cuando falla un control, su etapa queda en rojo, las que dependen de ella no
corren, `resultado` falla y GitHub no deja integrar el pull request. Se
reproduce localmente con `python controles.py <etapa>`.

## 6. Lo que agregamos desde la materia

Revisamos el proyecto buscando qué más podía verificar el CI con lo que
vimos en la cursada. Agregamos dos cosas chicas, cada una con un defecto que
la hace fallar.

### 6.1. La complejidad se mide en cada cambio

> **De la cátedra · diap. 8 y 28.** La complejidad indica cuántos recursos
> (tiempo y espacio) necesita un algoritmo y responde "¿cuál escalará mejor
> cuando haya millones de datos?". Se descartan las constantes y se conserva
> el término dominante.
>
> **Cómo y por qué lo aplicamos.** En el primer parcial mostramos un gráfico
> log-log donde "la pendiente es el exponente", medido una vez. Ahora ese
> gráfico es un control: si alguien cambia el heap por una lista, el CI lo
> detecta aunque las rutas sigan siendo correctas.

`benchmarks/test_complejidad.py` mide Dijkstra en grillas de 400 a 3.136
nodos y calcula la pendiente en escala log-log. Si el tiempo crece como
c·Vᵏ, la pendiente es k: la máquina cambia la constante c, no k. Por eso este
control **no necesita línea base** (es justamente "descartar las
constantes").

| Contrato | Teoría | Medido (3 corridas) |
|---|---|---|
| Dijkstra con lista | O(V²), k ≈ 2 | 2,00 · 2,00 · 2,00 |
| Dijkstra con heap | O(V log V), k ≈ 1,1 | 1,14 · 1,14 · 1,14 |
| Leer un archivo 10 veces más grande con un generador | O(1) en memoria | ×1,00 |
| Lo mismo con `readlines` | O(n) | ×11,26 |

Con el defecto plantado (`min()` en lugar de `heappop`) todas las pruebas
pasan, pero k sube a 1,51. No llega a 2 porque en una grilla la frontera
tiene unos √V nodos: el costo pasa a O(V·√V), o sea k ≈ 1,5. La medición
coincide con la teoría también en el error.

### 6.2. La documentación se ejecuta

> **De la cátedra · diap. 278 y 280.** Doctest permite escribir pruebas
> dentro de la documentación: las líneas con `>>>` son a la vez ejemplo de
> uso y prueba automatizada, y si no coinciden muestra lo esperado contra lo
> obtenido.
>
> **Cómo y por qué lo aplicamos.** En el parcial 2 lo usamos en los
> docstrings. Ahora también en la documentación externa: los ejemplos de
> `docs/*.md` corren en cada push, así un ejemplo de la documentación nunca
> queda desactualizado.

## 7. Evolución: del parcial 1 al 3

> **De la cátedra · diap. 295.** Primero, que funcione. Después, identificar
> los cuellos de botella reales con herramientas. Y optimizar de forma
> progresiva.
>
> **Cómo y por qué lo aplicamos.** Los tres parciales siguieron ese orden, y
> el tercero cierra el ciclo: lo que antes medíamos una vez, ahora se exige
> en cada cambio.

| | Parcial 1 | Parcial 2 | Parcial 3 |
|---|---|---|---|
| Idea | Que funcione y sea eficiente | Medir con herramientas y ordenar el código | Exigirlo en cada cambio |
| Complejidad | Gráfico log-log medido una vez | Explicada en el informe | Medida por el CI en cada push |
| Calidad | — | `calidad.py` genera un reporte | 12 controles que bloquean |
| Rendimiento | `banco.py`, a mano | Informe con mediciones | Benchmark contra línea base en cada cambio |
| Documentación | Docstrings y la presentación | Sphinx, generado a mano | MkDocs, publicado por el CI; ejemplos ejecutables |
| Dependencias | — | 21 con `>=` | 97 con versión exacta |
| Pruebas | — | 116 | 121 |

**El pipeline del parcial 3 corrido sobre el código del parcial 2** (mismas
pruebas, misma configuración, misma línea base):

| Control | Código del parcial 2 | Código del parcial 3 |
|---|---|---|
| Ruff | Rechazado (sintaxis de tipos vieja) | Aprobado |
| mypy | Rechazado: 6 errores | Aprobado |
| pytest + cobertura | Aprobado, 94,85 % | Aprobado, 94,85 % |
| pip-audit | Rechazado: `flask>=3.0` sin versión fija | Aprobado |
| Benchmark | +0 % a +4 % | −1 % a +5 % |
| **Resultado** | **RECHAZADO** | **APROBADO** |

El código del parcial 2 funcionaba y rendía igual, pero **no era
verificable**: tenía 6 contratos de tipos falsos que ninguna prueba
detectaba (por ejemplo, `a_estrella` podía recibir `None` en los procesos
hijos) y dependencias que podían cambiar solas. Corregirlo no costó
rendimiento.

## 8. Limitaciones

1. **El pipeline todavía no corrió en una plataforma de CI.** Lo verificamos
   localmente con los mismos comandos que usa cada job, pero falta subir el
   repositorio y adjuntar una corrida en verde.
2. **La línea base del benchmark se midió en Windows.** El tiempo relativo
   compensa la velocidad de la máquina, pero si la primera corrida en Linux
   marca regresión, se regenera en el runner (*Run workflow* → *linea_base*).
   El control de complejidad no tiene este problema.

## 9. Conclusiones

- **Medir no alcanza: hay que exigir.** En el parcial 2 sabíamos cuánto
  rendía el código; ahora un cambio que lo empeora no entra. Y el código
  viejo, con el mismo pipeline, no hubiera pasado.
- **Cada control necesita su criterio.** Las pruebas no toleran nada; el
  benchmark necesita repetición, mínimo, tiempo relativo y tolerancia; la
  complejidad se controla con un exponente, sin línea base.
- **Las herramientas no reemplazan la revisión.** Bandit no vio el
  `debug=True` y mypy encontró 6 errores que ninguna prueba detectaba.
- **Los controles también se prueban.** Sin los defectos plantados no
  sabríamos si el CI controla algo.

## Cómo reproducir

```bash
pip install -r requirements-dev.txt
python controles.py                 # todo: APROBADO en ~40 s
python controles.py rendimiento     # benchmark, memoria, complejidad
mkdocs serve                        # la documentación
```

El informe del segundo parcial está en `INFORME-parcial-2.md`.
