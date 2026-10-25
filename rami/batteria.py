"""Ramo Batteria: se la carica è bassa va al caricabatterie e ricarica fino al 100%."""
from py_trees.common import Status

from rami.comuni import Azione, Condizione, esito, selettore, sequenza


def crea_batteria(mondo):
    vai_in_carica = Azione("go to charge",
                           lambda: esito(mondo.vai_verso("caricabatterie"), Status.RUNNING))
    # "completa l'azione solo se raggiunge il 100%": RUNNING finché non è carica
    carica = Azione("charge", lambda: esito(mondo.ricarica(), Status.SUCCESS, Status.RUNNING))
    return selettore(
        "Batteria",
        Condizione("livello > 20% (oltre al ritorno) e non in carica?", mondo.batteria_ok),
        sequenza(
            "Ricarica",
            selettore("Raggiungi caricabatterie",
                      Condizione("mi trovo al caricabatterie?", mondo.al_caricabatterie),
                      vai_in_carica),
            carica,
        ),
    )
