"""Foglia Posa l'oggetto."""
from rami.comuni import Azione, esito


def crea_posa(mondo):
    return Azione("posa l'oggetto", lambda: esito(mondo.posa()))
