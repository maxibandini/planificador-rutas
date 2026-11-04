# Planificador inteligente de rutas

Programación Eficiente · Tercer parcial · Máximo Bandini y Lucas Caminos

El planificador encuentra la ruta de menor costo en una red de ciudades,
responde miles de consultas con caché, procesa archivos de millones de
pedidos y se expone como API web con Flask. Es el proyecto de los dos
parciales anteriores; este tercer parcial le agrega **documentación externa**
y un **pipeline de integración continua** que impide integrar código que no
cumpla las condiciones mínimas de calidad y eficiencia.

## Qué hay en esta documentación

| Sección | Qué responde |
|---|---|
| [Descripción funcional](funcional.md) | Qué problema resuelve, alcance y requisitos |
| [Arquitectura](arquitectura.md) | Módulos, responsabilidades, dependencias y diagrama de componentes |
| [Instalación y ejecución](instalacion.md) | Dependencias, configuración y comandos |
| [Diseño técnico](diseno.md) | Estructuras de datos, algoritmos y decisiones de implementación |
| [API web](api.md) y [referencia del código](referencia.md) | Entradas, salidas, excepciones y ejemplos |
| [Pruebas](pruebas.md) | Estrategia, casos de prueba y resultados |
| [Rendimiento](rendimiento.md) | Benchmarks, profiling, complejidad y memoria |
| [Seguridad](seguridad.md) | Riesgos, dependencias, política de bloqueo y falsos positivos |
| [Integración continua](ci.md) | Etapas del pipeline y matriz de controles |
| [Mantenimiento](mantenimiento.md) | Cómo contribuir, correr los controles y resolver fallos del CI |
| [Evolución desde el parcial 2](evolucion.md) | Qué cambió y qué detecta el pipeline nuevo en el código viejo |

## Dónde vive y quién la edita

- **Herramienta:** MkDocs con el tema Material for MkDocs. Las páginas son
  archivos Markdown en la carpeta `docs/` del mismo repositorio que el
  código, así que la documentación se revisa en el mismo pull request que el
  cambio que documenta.
- **Lugar compartido:** el repositorio de GitHub. El CI publica el sitio en
  GitHub Pages cada vez que un cambio llega a `main` y pasa todos los
  controles: lo publicado nunca queda atrás del código.
- **Control de acceso:** solo los colaboradores del repositorio pueden
  escribir. La rama `main` está protegida: todo cambio entra por pull
  request, con al menos una aprobación del otro integrante y el check
  `resultado` del CI en verde (ver [Mantenimiento](mantenimiento.md#flujo-de-trabajo)).
- **Colaboración:** cada página tiene el botón *Editar* que abre el archivo
  en GitHub; la edición genera un pull request como cualquier otro cambio.

## En una línea

```bash
python controles.py        # corre localmente los mismos controles que el CI
```
