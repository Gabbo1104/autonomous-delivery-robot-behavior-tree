"""Ramo Raggiungi il punto di ritiro."""
from rami.comuni import Condizione, selettore
from rami.navigazione import crea_navigazione


def crea_ritiro(mondo):
    return selettore(
        "Raggiungi il punto di ritiro",
        Condizione("ho l'oggetto in mano?", lambda: mondo.oggetto_in_mano is not None),
        Condizione("sono già lì?", lambda: mondo.posizione == mondo.ordine.ritiro),
        crea_navigazione(mondo, "Verso il ritiro", lambda: mondo.ordine.ritiro),
    )
