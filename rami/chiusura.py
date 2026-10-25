"""Foglia Chiudi l'ordine."""
from rami.comuni import Azione, esito


def crea_chiusura(mondo):
    return Azione("chiudi l'ordine", lambda: esito(mondo.chiudi_ordine()))
