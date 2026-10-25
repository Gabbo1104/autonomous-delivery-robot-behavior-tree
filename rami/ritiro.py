"""Branch "Reach the pick-up point".

    ? Reach the pick-up point
    ├── C  am I holding the item?    already carrying the item: nothing to do
    ├── C  am I already there?       already at the pickup node
    └── -> To the pick-up point      navigation subtree (rami/navigazione.py)

The first condition matters because the root Sequence restarts from the top on
every tick: once the item is picked up, this branch must succeed immediately so
that the tree moves on to the delivery branch instead of going back for pickup.
"""
from rami.comuni import Condizione, selettore
from rami.navigazione import crea_navigazione


def crea_ritiro(mondo):
    """Build the reach-pickup subtree for ``mondo`` (structure in the module docstring)."""
    return selettore(
        "Reach the pick-up point",
        Condizione("am I holding the item?", lambda: mondo.oggetto_in_mano is not None),
        Condizione("am I already there?", lambda: mondo.posizione == mondo.ordine.ritiro),
        crea_navigazione(mondo, "To the pick-up point", lambda: mondo.ordine.ritiro),
    )
