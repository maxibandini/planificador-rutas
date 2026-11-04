"""Pruebas de la cache y de la memoizacion."""

from unittest import mock

import pytest

from planificador.algoritmos import a_estrella
from planificador.cache import CacheDeRutas, clave_de_tramo, crear_memoizado


# Mock: un acierto de cache no llama al algoritmo.
def test_acierto_no_vuelve_a_calcular(red_ar):
    algoritmo = mock.Mock(side_effect=a_estrella)
    cache = CacheDeRutas(red_ar, algoritmo=algoritmo)
    primera = cache.consultar("Ushuaia", "Salta")
    segunda = cache.consultar("Ushuaia", "Salta")
    assert primera is segunda
    algoritmo.assert_called_once_with(red_ar, "Ushuaia", "Salta")
    assert cache.estadisticas()["aciertos"] == 1
    assert cache.estadisticas()["fallos"] == 1


def test_lru_respeta_la_capacidad(grilla):
    cache = CacheDeRutas(grilla, capacidad=3)
    for destino in range(1, 6):
        cache.consultar(0, destino)
    assert len(cache) == 3
    assert (0, 1) not in cache  # la mas vieja se descarto
    assert (0, 5) in cache
    assert cache.contadores.descartadas == 2


def test_lru_usar_una_ruta_la_renueva(grilla):
    cache = CacheDeRutas(grilla, capacidad=2)
    cache.consultar(0, 1)
    cache.consultar(0, 2)
    cache.consultar(0, 1)  # (0, 1) pasa a ser la mas nueva
    cache.consultar(0, 3)  # se descarta (0, 2)
    assert (0, 1) in cache
    assert (0, 2) not in cache


def test_cortar_tramo_invalida_solo_las_rutas_afectadas(red_ar):
    cache = CacheDeRutas(red_ar)
    afectada = cache.consultar("Ushuaia", "Salta")
    cache.consultar("Mendoza", "San Juan")  # no usa ese tramo
    a, b = afectada.ruta[2], afectada.ruta[3]

    assert cache.cortar_tramo(a, b) == 1
    assert ("Ushuaia", "Salta") not in cache
    assert ("Mendoza", "San Juan") in cache

    nueva = cache.consultar("Ushuaia", "Salta")
    assert nueva.costo > afectada.costo
    red_ar.costo_de_ruta(nueva.ruta)  # no lanza: la ruta es valida


def test_memoizacion_devuelve_ruta_obsoleta(red_ar):
    memoizado = crear_memoizado(red_ar)
    vieja = memoizado("Ushuaia", "Salta")
    red_ar.cortar_arista(vieja.ruta[2], vieja.ruta[3])
    assert memoizado("Ushuaia", "Salta") is vieja
    with pytest.raises(ValueError):
        red_ar.costo_de_ruta(vieja.ruta)


def test_precargar_no_cuenta_como_consulta(red_ar):
    cache = CacheDeRutas(red_ar)
    cache.precargar("Ushuaia", "Salta", a_estrella(red_ar, "Ushuaia", "Salta"))
    assert cache.estadisticas()["consultas"] == 0
    cache.consultar("Ushuaia", "Salta")
    assert cache.contadores.tasa_aciertos == 1.0


def test_clave_de_tramo_no_depende_del_sentido():
    assert clave_de_tramo(3, 12) == clave_de_tramo(12, 3)
