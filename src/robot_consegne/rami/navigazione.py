"""Navigation subtree, shared by the pickup and the delivery branches.

It advances the robot ONE edge at a time towards a target node::

    -> <nome>                            e.g. "To the pick-up point" / "To the delivery point"
    ├── ? Stairs                         stay away from the stairs
    │   ├── C  am I away from the stairs?
    │   └── A  move away                 step away from the stairs (RUNNING)
    ├── ? Way                            make sure the next edge can be travelled
    │   ├── C  is the way clear?         nothing in the way
    │   ├── -> Door                      a closed door is in the way
    │   │   ├── C  is there a door?
    │   │   └── ? Open door
    │   │       ├── -> Push
    │   │       │   ├── C  does it need pushing?   door swings away from the robot
    │   │       │   └── A  push                    push it open
    │   │       └── A  use the key                 it would need pulling: use the key
    │   └── A  turn back                 an obstacle: remember it, re-plan (RUNNING)
    └── A  move forward                  move one edge (RUNNING), SUCCESS when arrived

Design note: in the drawing the node under "Reach the pick-up point" is a
"?" (Selector). Taken literally, the Selector would succeed as soon as "am I
away from the stairs?" succeeds and the road would never be checked. It is
implemented as a Sequence instead: stairs check, then clear the road, then move.

When "Way" succeeds by opening a door, "move forward" moves through it in the
same tick. When it succeeds through "turn back" it returns RUNNING, so the
tick ends and the next one plans a route around the newly found obstacle.
"""
from py_trees.common import Status

from robot_consegne.rami.comuni import Azione, Condizione, esito, selettore, sequenza


def crea_navigazione(mondo, nome, destinazione):
    """Build the subtree that moves the robot towards ``destinazione()``.

    ``destinazione`` is a zero-argument function, not a node name, because the
    target depends on the current order (``mondo.ordine.ritiro`` or
    ``mondo.ordine.consegna``), which changes over time; it is evaluated on
    every tick. ``nome`` is the label of the subtree's root.
    """
    scale = selettore(
        "Stairs",
        Condizione("am I away from the stairs?", mondo.lontano_dalle_scale),
        Azione("move away",
               lambda: esito(mondo.allontanati_dalle_scale(destinazione()), Status.RUNNING)),
    )
    porta = sequenza(
        "Door",
        Condizione("is there a door?", lambda: mondo.porta_chiusa(destinazione())),
        selettore(
            "Open door",
            sequenza(
                "Push",
                Condizione("does it need pushing?", lambda: mondo.porta_a_spinta(destinazione())),
                Azione("push", lambda: esito(mondo.spingi(destinazione()))),
            ),
            Azione("use the key", lambda: esito(mondo.usa_chiave(destinazione()))),
        ),
    )
    strada = selettore(
        "Way",
        Condizione("is the way clear?", lambda: mondo.strada_libera(destinazione())),
        porta,
        # obstacle: remember it and try another route on the next tick
        Azione("turn back", lambda: esito(mondo.torna_indietro(destinazione()), Status.RUNNING)),
    )
    vai_avanti = Azione(
        "move forward",
        # Already there -> SUCCESS. Otherwise move one edge: RUNNING if it moved,
        # FAILURE if it could not (e.g. flat battery).
        lambda: Status.SUCCESS if mondo.posizione == destinazione()
        else esito(mondo.avanza(destinazione()), Status.RUNNING),
    )
    return sequenza(nome, scale, strada, vai_avanti)
