"""Navigation subtree, shared by the pickup and the delivery branches.

It advances the robot ONE edge at a time towards a target node::

    -> <nome>                          e.g. "Verso il ritiro" / "Verso la consegna"
    ├── ? Scale                         stay away from the stairs
    │   ├── C  sono lontano dalle scale?
    │   └── A  allontanati              step away from the stairs (RUNNING)
    ├── ? Strada                        make sure the next edge can be travelled
    │   ├── C  strada libera?           nothing in the way
    │   ├── -> Porta                    a closed door is in the way
    │   │   ├── C  c'è una porta?
    │   │   └── ? Apri porta
    │   │       ├── -> Spingi
    │   │       │   ├── C  bisogna spingere?   door swings away from the robot
    │   │       │   └── A  spingi              push it open
    │   │       └── A  usa la chiave           it would need pulling: use the key
    │   └── A  torna indietro           an obstacle: remember it, re-plan (RUNNING)
    └── A  vai avanti                   move one edge (RUNNING), SUCCESS when arrived

Design note: in the drawing the node under "raggiungi il punto di ritiro" is a
"?" (Selector). Taken literally, the Selector would succeed as soon as "sono
lontano dalle scale?" succeeds and the road would never be checked. It is
implemented as a Sequence instead: stairs check, then clear the road, then move.

When "Strada" succeeds by opening a door, "vai avanti" moves through it in the
same tick. When it succeeds through "torna indietro" it returns RUNNING, so the
tick ends and the next one plans a route around the newly found obstacle.
"""
from py_trees.common import Status

from rami.comuni import Azione, Condizione, esito, selettore, sequenza


def crea_navigazione(mondo, nome, destinazione):
    """Build the subtree that moves the robot towards ``destinazione()``.

    ``destinazione`` is a zero-argument function, not a node name, because the
    target depends on the current order (``mondo.ordine.ritiro`` or
    ``mondo.ordine.consegna``), which changes over time; it is evaluated on
    every tick. ``nome`` is the label of the subtree's root.
    """
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
        # obstacle: remember it and try another route on the next tick
        Azione("torna indietro", lambda: esito(mondo.torna_indietro(destinazione()), Status.RUNNING)),
    )
    vai_avanti = Azione(
        "vai avanti",
        # Already there -> SUCCESS. Otherwise move one edge: RUNNING if it moved,
        # FAILURE if it could not (e.g. flat battery).
        lambda: Status.SUCCESS if mondo.posizione == destinazione()
        else esito(mondo.avanza(destinazione()), Status.RUNNING),
    )
    return sequenza(nome, scale, strada, vai_avanti)
