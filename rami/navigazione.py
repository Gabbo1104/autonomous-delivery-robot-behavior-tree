"""Sotto-albero di navigazione, uguale per il punto di ritiro e quello di consegna.

Un passo alla volta: stai lontano dalle scale, libera la strada (porta o
ostacolo), poi vai avanti di un nodo.
"""
from py_trees.common import Status

from rami.comuni import Azione, Condizione, esito, selettore, sequenza


def crea_navigazione(mondo, nome, destinazione):
    """destinazione: funzione senza argomenti che restituisce il nodo da raggiungere."""
    scale = selettore(
        "Scale",
        Condizione("sono lontano dalle scale?", mondo.lontano_dalle_scale),
        Azione("allontanati",
               lambda: esito(mondo.allontanati_dalle_scale(destinazione()), Status.RUNNING)),
    )
    porta = sequenza(
        "Porta",
        Condizione("c'è una porta?", lambda: mondo.porta_chiusa(destinazione())),
        selettore(
            "Apri porta",
            sequenza(
                "Spingi",
                Condizione("bisogna spingere?", lambda: mondo.porta_a_spinta(destinazione())),
                Azione("spingi", lambda: esito(mondo.spingi(destinazione()))),
            ),
            Azione("usa la chiave", lambda: esito(mondo.usa_chiave(destinazione()))),
        ),
    )
    strada = selettore(
        "Strada",
        Condizione("strada libera?", lambda: mondo.strada_libera(destinazione())),
        porta,
        # ostacolo: lo memorizza e al prossimo tick prova un altro percorso
        Azione("torna indietro", lambda: esito(mondo.torna_indietro(destinazione()), Status.RUNNING)),
    )
    vai_avanti = Azione(
        "vai avanti",
        lambda: Status.SUCCESS if mondo.posizione == destinazione()
        else esito(mondo.avanza(destinazione()), Status.RUNNING),
    )
    return sequenza(nome, scale, strada, vai_avanti)
