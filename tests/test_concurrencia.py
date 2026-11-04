"""Pruebas de la concurrencia: las tres variantes dan lo mismo."""

import pytest

from planificador import concurrencia
from planificador.consultas import generar_consultas


@pytest.mark.lento
def test_secuencial_hilos_y_procesos_coinciden(grilla):
    consultas = generar_consultas(grilla, 40, semilla=2)
    fila = concurrencia.comparar(grilla, consultas, trabajadores=2)
    assert fila["iguales"]
    assert fila["consultas"] == 40


@pytest.mark.lento
def test_rutas_con_procesos_conserva_el_orden(grilla):
    consultas = generar_consultas(grilla, 20, semilla=4)
    rutas = concurrencia.rutas_con_procesos(grilla, consultas, trabajadores=2)
    for (origen, destino), resultado in zip(consultas, rutas, strict=True):
        assert resultado.ruta[0] == origen
        assert resultado.ruta[-1] == destino


def test_con_hilos_no_necesita_procesos(red_ar):
    consultas = [("Ushuaia", "Salta"), ("Mendoza", "Rosario")]
    assert concurrencia.con_hilos(red_ar, consultas, 2) == (
        concurrencia.secuencial(red_ar, consultas)
    )
