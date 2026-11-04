"""Pruebas del script del servidor."""

import socket

import servidor


def test_detecta_un_puerto_ocupado():
    with socket.socket() as ocupante:
        ocupante.bind((servidor.HOST, 0))  # el sistema elige un puerto libre
        ocupante.listen()
        puerto = ocupante.getsockname()[1]
        assert servidor.puerto_ocupado(puerto)
    assert not servidor.puerto_ocupado(puerto)
