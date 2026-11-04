"""Pruebas de controles.py: el script que decide si un cambio se integra."""

import json

import pytest

import controles


def _correr_main(monkeypatch, etapas, argumentos):
    monkeypatch.setattr(controles, "ETAPAS", etapas)
    monkeypatch.setattr(controles, "OMITIDOS", [])
    monkeypatch.setattr("sys.argv", ["controles.py", *argumentos])
    controles.main()


def test_un_control_que_falla_rechaza_con_codigo_1(monkeypatch, capsys):
    monkeypatch.setattr(controles, "falla", lambda: False, raising=False)
    with pytest.raises(SystemExit) as salida:
        _correr_main(monkeypatch, {"x": [("Control roto", "falla")]}, ["x"])
    assert salida.value.code == 1
    assert "RECHAZADO" in capsys.readouterr().out


def test_etapa_desconocida_sale_con_codigo_2(monkeypatch):
    with pytest.raises(SystemExit) as salida:
        _correr_main(monkeypatch, {"x": []}, ["no-existe"])
    assert salida.value.code == 2


def test_programa_externo_ausente_queda_como_omitido(monkeypatch, capsys):
    etapas = {"x": [("Externo", "!programa-que-no-existe --version")]}
    _correr_main(monkeypatch, etapas, ["x"])
    salida = capsys.readouterr().out
    assert "APROBADO" in salida
    assert "Sin verificar en esta maquina" in salida


def test_linea_base_de_varias_corridas_es_la_mediana(monkeypatch, tmp_path):
    corridas = []
    for numero, (referencia, operacion) in enumerate([(1, 2), (1, 3), (2, 2)]):
        archivo = tmp_path / f"benchmark_{numero}.json"
        benchmarks = [
            {"name": "test_referencia", "stats": {"min": referencia}},
            {"name": "test_operacion", "stats": {"min": operacion}},
        ]
        archivo.write_text(json.dumps({"benchmarks": benchmarks}))
        corridas.append(str(archivo))
    linea_base = tmp_path / "linea_base.json"
    linea_base.write_text(json.dumps({"memoria_kib": {"pico": 100.0}}))
    monkeypatch.setattr(controles, "LINEA_BASE", linea_base)

    _correr_main(monkeypatch, {}, ["linea-base", *corridas])

    # tiempos relativos 2, 3 y 1: la mediana es 2; la memoria no cambia
    assert json.loads(linea_base.read_text()) == {
        "tiempos": {"test_operacion": 2.0},
        "memoria_kib": {"pico": 100.0},
    }
