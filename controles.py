"""Controles de calidad y eficiencia: los mismos que corre el CI.

El pipeline (.github/workflows/ci.yml) llama a este script en cada etapa,
asi que lo que pasa en la maquina de cada integrante es exactamente lo que
pasa en GitHub Actions.

    python controles.py                 # todas las etapas, en orden
    python controles.py calidad         # una sola etapa
    python controles.py linea-base      # regenerar la linea base

Etapas: calidad, pruebas, seguridad, documentacion, rendimiento.
Los reportes quedan en la carpeta ``reportes/``.
"""

import cProfile
import json
import pstats
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

REPORTES = Path("reportes")
LINEA_BASE = Path("benchmarks/linea_base.json")
TOLERANCIA_TIEMPO = 0.30  # mas de un 30 % sobre la linea base es regresion
EXCLUIR = "./tests,./benchmarks,./site,./reportes,./.venv"
PIP_AUDIT = (
    "pip_audit -r requirements.txt -r requirements-dev.txt"
    " --no-deps --disable-pip"
)

# Cada control: (nombre, comando). Los comandos de Python se ejecutan con
# "python -m" del entorno actual; "!" marca un programa externo (Gitleaks),
# y un nombre de funcion de este archivo se llama directamente.
ETAPAS = {
    "calidad": [
        ("Ruff: errores y estilo", "ruff check ."),
        ("Ruff: formato", "ruff format --check ."),
        ("mypy: tipos", "mypy"),
        (
            "Lizard: complejidad <= 10, <= 50 lineas, <= 6 parametros",
            "lizard planificador -C 10 -T nloc=50 -a 6 -w",
        ),
        (
            "Radon: indice de mantenibilidad (reporte)",
            "radon mi planificador -s -j -O reportes/radon_mi.json",
        ),
        (
            "Bandit: reporte SARIF completo",
            f"bandit -r . -x {EXCLUIR} -q --exit-zero"
            " -f sarif -o reportes/bandit.sarif",
        ),
        (
            "Bandit: bloquea severidad alta",
            f"bandit -r . -x {EXCLUIR} -q"
            " --severity-level high --confidence-level medium",
        ),
        (
            "Gitleaks: secretos",
            "!gitleaks dir . --redact"
            " --report-format sarif --report-path reportes/gitleaks.sarif",
        ),
    ],
    "pruebas": [
        (
            "pytest + cobertura >= 90 %",
            "pytest --cov --cov-report=term --junitxml=reportes/pruebas.xml"
            " --cov-report=xml:reportes/cobertura.xml"
            " --cov-report=html:reportes/cobertura",
        ),
    ],
    "seguridad": [
        (
            "pip-audit: dependencias (legible)",
            PIP_AUDIT + " --desc",
        ),
        (
            "pip-audit: dependencias (JSON)",
            PIP_AUDIT + " -f json -o reportes/pip-audit.json",
        ),
    ],
    "documentacion": [
        ("MkDocs: sitio y enlaces internos", "mkdocs build --strict"),
    ],
    "rendimiento": [
        # min-time: cada ronda dura al menos 0,1 ms. Asi el acierto de cache
        # (0,3 us) se repite ~1.000 veces por ronda; con 1 o 2 repeticiones
        # el reloj pesa mas que la operacion y da una regresion falsa.
        (
            "Benchmarks (pytest-benchmark)",
            "pytest benchmarks/test_benchmark.py --benchmark-only"
            " --benchmark-min-rounds=5 --benchmark-min-time=0.0001"
            " --benchmark-time-unit=ms"
            " --benchmark-columns=min,mean,stddev,rounds"
            " --benchmark-json=reportes/benchmark.json",
        ),
        ("Regresion contra la linea base", "comparar_benchmark"),
        ("Memoria (tracemalloc)", "pytest benchmarks/test_memoria.py"),
        (
            "Complejidad medida contra la teorica (tiempo y espacio)",
            "pytest benchmarks/test_complejidad.py",
        ),
        ("Profiling de CPU (cProfile, reporte)", "perfilar"),
    ],
}


def comparar_benchmark():
    """Falla si alguna operacion es mas de un 30 % mas lenta que la base.

    Compara tiempos relativos a ``test_referencia`` y no tiempos absolutos:
    asi la misma linea base sirve en cualquier maquina.
    """
    relativos = _tiempos_relativos()
    base = json.loads(LINEA_BASE.read_text(encoding="utf-8"))["tiempos"]
    ok = True
    print(f"{'operacion':32} {'base':>10} {'actual':>10} {'cambio':>7}")
    for nombre, actual in relativos.items():
        cambio = actual / base[nombre] - 1
        marca = "REGRESION" if cambio > TOLERANCIA_TIEMPO else ""
        ok = ok and not marca
        print(
            f"{nombre:32} {base[nombre]:10.4g} {actual:10.4g} "
            f"{cambio:+7.0%} {marca}"
        )
    return ok


def _tiempos_relativos():
    datos = json.loads((REPORTES / "benchmark.json").read_text("utf-8"))
    minimos = {b["name"]: b["stats"]["min"] for b in datos["benchmarks"]}
    referencia = minimos.pop("test_referencia")
    return {n: float(f"{t / referencia:.4g}") for n, t in minimos.items()}


def perfilar():
    """Perfila el procesamiento de un archivo y guarda las 15 funciones top."""
    # Imports aca: el resto del script no necesita el paquete.
    from planificador import archivos
    from planificador.consultas import generar_consultas
    from planificador.red import generar_red

    red = generar_red(60)
    entrada, salida = REPORTES / "consultas.txt", REPORTES / "salida.txt"
    archivos.escribir_consultas(entrada, generar_consultas(red, 2_000))
    perfil = cProfile.Profile()
    perfil.runcall(archivos.procesar_por_lotes, red, entrada, salida)
    perfil.dump_stats(REPORTES / "perfil.prof")
    with open(REPORTES / "perfil.txt", "w", encoding="utf-8") as texto:
        estadisticas = pstats.Stats(perfil, stream=texto)
        estadisticas.strip_dirs().sort_stats("tottime").print_stats(15)
    entrada.unlink()
    salida.unlink()
    print((REPORTES / "perfil.txt").read_text(encoding="utf-8")[:1500])
    return True


OMITIDOS = []  # controles externos que no estan instalados en esta maquina


def correr(nombre, comando):
    """Ejecuta un control y devuelve True si paso (o si se omitio)."""
    print(f"\n=== {nombre}", flush=True)
    if comando in globals():
        return globals()[comando]()
    if comando.startswith("!"):
        argumentos = comando[1:].split()
        if shutil.which(argumentos[0]) is None:
            print(
                f"OMITIDO: {argumentos[0]} no esta instalado (en el CI corre)."
            )
            OMITIDOS.append(nombre)
            return True
    else:
        argumentos = [sys.executable, "-m", *comando.split()]
    # Bandit B404/B603: solo comandos fijos de ETAPAS, sin shell.
    resultado = subprocess.run(argumentos, check=False)  # nosec B603
    return resultado.returncode == 0


def generar_linea_base():
    """Mide en esta maquina y guarda la nueva linea base."""
    for nombre, comando in ETAPAS["rendimiento"]:
        if nombre.startswith(("Benchmarks", "Memoria")):
            correr(nombre, comando)
    memoria = json.loads((REPORTES / "memoria.json").read_text("utf-8"))
    base = {"tiempos": _tiempos_relativos(), "memoria_kib": memoria}
    texto = json.dumps(base, indent=2) + "\n"
    LINEA_BASE.write_text(texto, encoding="utf-8")
    print(f"\nLinea base guardada en {LINEA_BASE}:\n{texto}")


def main():
    """Corre las etapas pedidas y termina con codigo 1 si alguna fallo."""
    REPORTES.mkdir(exist_ok=True)
    pedidas = sys.argv[1:] or list(ETAPAS)
    if pedidas == ["linea-base"]:
        generar_linea_base()
        return
    desconocidas = [etapa for etapa in pedidas if etapa not in ETAPAS]
    if desconocidas:
        print(f"Etapa desconocida: {', '.join(desconocidas)}")
        print(f"Etapas: {', '.join(ETAPAS)} (o linea-base)")
        sys.exit(2)
    fallidos = [
        nombre
        for etapa in pedidas
        for nombre, comando in ETAPAS[etapa]
        if not correr(nombre, comando)
    ]
    print("\n" + "=" * 60)
    if fallidos:
        print("RECHAZADO. Controles que fallaron:")
        for nombre in fallidos:
            print(f"  - {nombre}")
        sys.exit(1)
    print(f"APROBADO: {', '.join(pedidas)}")
    if OMITIDOS:
        print("Sin verificar en esta maquina (el CI si los corre):")
        for nombre in OMITIDOS:
            print(f"  - {nombre}")


if __name__ == "__main__":
    main()
