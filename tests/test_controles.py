"""Pruebas de controles.py: el script que decide si un cambio se integra."""

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
