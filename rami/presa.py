"""Ramo Prendere l'oggetto."""
from rami.comuni import Azione, Condizione, esito, selettore


def crea_presa(mondo):
    return selettore(
        "Prendere l'oggetto",
        Condizione("ho già l'oggetto in mano?", lambda: mondo.oggetto_in_mano is not None),
        Azione("prendi", lambda: esito(mondo.prendi())),
    )
