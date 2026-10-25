"""Ramo Raggiungi il punto di consegna."""
from rami.comuni import Condizione, selettore
from rami.navigazione import crea_navigazione


def crea_consegna(mondo):
    return selettore(
        "Raggiungi il punto di consegna",
        Condizione("sono già lì?", lambda: mondo.posizione == mondo.ordine.consegna),
        crea_navigazione(mondo, "Verso la consegna", lambda: mondo.ordine.consegna),
    )
