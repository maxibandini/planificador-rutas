# Planificador inteligente de rutas — Tercer parcial

Programación Eficiente · Maximo Bandini y Lucas Caminos

Encuentra la ruta de menor costo en una red de ciudades, responde miles de
consultas con caché, procesa archivos grandes por lotes y se expone como API
web (Flask). Este tercer parcial le agrega al proyecto:

1. **Documentación externa** con MkDocs + Material for MkDocs: carpeta
   `docs/`, publicada en GitHub Pages por el CI.
2. **Integración continua** con GitHub Actions (`.github/workflows/ci.yml`):
   pruebas, cobertura, análisis estático, tipado, complejidad, seguridad,
   dependencias, documentación, benchmark y memoria en cada push y pull
   request a `main`.

| Consigna | Dónde |
|---|---|
| 1. Documentación externa (9 secciones) | `docs/` (se publica en GitHub Pages desde el CI) |
| Cómo correr localmente los controles del CI | `python controles.py` · `docs/mantenimiento.md` |
| 2. Pipeline de CI y matriz de controles | `.github/workflows/ci.yml` · `docs/ci.md` |
| Requisitos de seguridad y política de bloqueo | `docs/seguridad.md` · `.gitleaks.toml` · `.github/dependabot.yml` |
| 3. Diseño del pipeline por etapas | `docs/ci.md#etapas-del-pipeline` |
| 3.1. Qué pasa si un control falla (y prueba de que falla) | `docs/ci.md#prueba-de-los-controles` |

## Inicio rápido

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt    # versiones fijadas

python main.py Ushuaia Salta           # demostración
python servidor.py                     # API en http://127.0.0.1:8000
python controles.py                    # los mismos controles que el CI
mkdocs serve                           # la documentación
```

Todo lo demás está en la documentación (`docs/index.md`).

`INFORME-parcial-2.md` y `resultados/` son el informe y las mediciones del segundo
parcial, sin cambios.
