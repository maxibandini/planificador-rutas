"""Pruebas de la entrada/salida de archivos grandes."""

import pytest

from planificador import archivos
from planificador.consultas import generar_consultas


@pytest.fixture
def entrada(tmp_path, red_ar):
    """Archivo con 300 consultas repetidas y dos lineas especiales."""
    ruta = tmp_path / "consultas.txt"
    consultas = generar_consultas(red_ar, 300, pares_distintos=20)
    archivos.escribir_consultas(ruta, consultas)
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write("\n")  # linea vacia: se ignora
        archivo.write("Ushuaia;Atlantida\n")  # ciudad inexistente
    return ruta


def test_en_lotes_como_el_ejercicio_del_practico():
    # Practico unidad 5, ejercicio 2: numeros del 1 al 50 en lotes de 10
    lotes = list(archivos.en_lotes(range(1, 51), 10))
    assert [sum(lote) for lote in lotes] == [55, 155, 255, 355, 455]


def test_en_lotes_rechaza_tamanio_invalido():
    with pytest.raises(ValueError):
        list(archivos.en_lotes([1, 2], 0))


def test_en_lotes_es_perezoso():
    def infinito():
        numero = 0
        while True:
            numero += 1
            yield numero

    primer_lote = next(archivos.en_lotes(infinito(), 3))
    assert primer_lote == [1, 2, 3]


def test_ida_y_vuelta_de_consultas(tmp_path, red_ar):
    ruta = tmp_path / "ida_vuelta.txt"
    consultas = generar_consultas(red_ar, 50)
    assert archivos.escribir_consultas(ruta, consultas, tamanio_lote=7) == 50
    assert list(archivos.leer_consultas(ruta)) == consultas
    assert archivos.leer_todo(ruta) == consultas


def test_linea_mal_formada():
    with pytest.raises(ValueError, match="mal formada"):
        archivos.parsear_consulta("solo-un-campo\n")


@pytest.mark.parametrize(
    "leer",
    [archivos.leer_todo, lambda ruta: list(archivos.leer_consultas(ruta))],
)
def test_error_indica_la_linea_mal_formada(tmp_path, leer):
    ruta = tmp_path / "con_error.txt"
    ruta.write_text("A;B\n\nA;B;C\n", encoding="utf-8")
    with pytest.raises(ValueError, match="linea 3"):
        leer(ruta)


def test_archivo_vacio(tmp_path, red_ar):
    entrada = tmp_path / "vacio.txt"
    entrada.write_text("", encoding="utf-8")
    salida = tmp_path / "salida.txt"
    assert archivos.procesar_por_lotes(red_ar, entrada, salida) == 0
    assert salida.read_text(encoding="utf-8") == ""


@pytest.mark.parametrize(
    "escribir",
    [
        archivos.escribir_abriendo_por_linea,
        archivos.escribir_con_buffer,
        archivos.escribir_por_lotes,
    ],
)
def test_las_escrituras_generan_el_mismo_archivo(tmp_path, escribir):
    lineas = [f"linea {numero}\n" for numero in range(250)]
    referencia = tmp_path / "referencia.txt"
    referencia.write_text("".join(lineas), encoding="utf-8", newline="\n")
    salida = tmp_path / "salida.txt"
    assert escribir(salida, iter(lineas)) == 250
    assert salida.read_bytes() == referencia.read_bytes()


# Las 4 versiones de la tuberia generan el mismo archivo.
@pytest.mark.lento
def test_las_cuatro_tuberias_dan_la_misma_salida(tmp_path, red_ar, entrada):
    salidas = []
    for indice, procesar in enumerate(
        [
            archivos.procesar_ingenuo,
            archivos.procesar_streaming,
            archivos.procesar_por_lotes,
        ]
    ):
        salida = tmp_path / f"v{indice}.txt"
        assert procesar(red_ar, entrada, salida) == 301
        salidas.append(salida.read_bytes())
    paralela = tmp_path / "v3.txt"
    procesadas = archivos.procesar_en_paralelo(
        red_ar, entrada, paralela, tamanio_lote=40, trabajadores=2
    )
    assert procesadas == 301
    salidas.append(paralela.read_bytes())
    assert all(salida == salidas[0] for salida in salidas)


def test_ciudad_inexistente_queda_marcada(tmp_path, red_ar, entrada):
    salida = tmp_path / "resultados.txt"
    archivos.procesar_por_lotes(red_ar, entrada, salida)
    filas = list(archivos.leer_resultados(salida))
    assert filas[-1] == ("Ushuaia", "Atlantida", float("inf"), 0)
    assert all(fila[3] > 0 for fila in filas[:-1])


def test_sqlite_por_lotes_y_uno_a_uno_guardan_lo_mismo(tmp_path):
    filas = [(f"o{numero}", "d", float(numero), 2) for numero in range(2500)]
    uno = tmp_path / "uno.db"
    lotes = tmp_path / "lotes.db"
    assert archivos.guardar_en_sqlite_uno_a_uno(uno, filas[:30]) == 30
    assert archivos.guardar_en_sqlite_por_lotes(lotes, filas, 1000) == 2500
    assert archivos.contar_filas(uno) == 30
    assert archivos.contar_filas(lotes) == 2500


def test_archivo_con_bom_de_excel(tmp_path, red_ar):
    entrada = tmp_path / "con_bom.txt"
    entrada.write_bytes(b"\xef\xbb\xbfUshuaia;Salta\n")
    salida = tmp_path / "salida.txt"
    archivos.procesar_por_lotes(red_ar, entrada, salida)
    assert salida.read_text(encoding="utf-8") == "Ushuaia;Salta;4818.788;9\n"


def test_espacios_alrededor_de_las_ciudades(tmp_path, red_ar):
    entrada = tmp_path / "espacios.txt"
    entrada.write_text(" Ushuaia ; Salta \n", encoding="utf-8")
    salida = tmp_path / "salida.txt"
    archivos.procesar_streaming(red_ar, entrada, salida)
    assert salida.read_text(encoding="utf-8").startswith("Ushuaia;Salta;4818")


@pytest.mark.parametrize(
    "procesar",
    [
        archivos.procesar_ingenuo,
        archivos.procesar_streaming,
        archivos.procesar_por_lotes,
    ],
)
def test_misma_entrada_y_salida_no_borra_los_datos(tmp_path, red_ar, procesar):
    ruta = tmp_path / "datos.txt"
    ruta.write_text("Ushuaia;Salta\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mismo archivo"):
        procesar(red_ar, ruta, ruta)
    assert ruta.read_text(encoding="utf-8") == "Ushuaia;Salta\n"


def test_entrada_inexistente_no_vacia_la_salida(tmp_path, red_ar):
    salida = tmp_path / "salida.txt"
    salida.write_text("resultado anterior\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        archivos.procesar_por_lotes(red_ar, tmp_path / "no.txt", salida)
    assert salida.read_text(encoding="utf-8") == "resultado anterior\n"


def test_archivo_que_no_es_utf8(tmp_path):
    ruta = tmp_path / "utf16.txt"
    ruta.write_text("Ushuaia;Salta\n", encoding="utf-16")
    with pytest.raises(ValueError, match="UTF-8"):
        list(archivos.leer_consultas(ruta))
