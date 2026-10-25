"""Ramo Ordine: prosegue solo se c'è un ordine, altrimenti lo attende."""
from py_trees.common import Status

from rami.comuni import Azione, Condizione, esito, selettore


def crea_ordini(mondo):
    return selettore(
        "Ordine",
        Condizione("ho un ordine?", lambda: mondo.ordine is not None),
        Azione("attendi ordine", lambda: esito(mondo.attendi_ordine(), Status.SUCCESS, Status.RUNNING)),
    )
