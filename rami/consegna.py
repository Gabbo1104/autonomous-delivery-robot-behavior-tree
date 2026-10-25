"""Branch "Reach the delivery point".

    ? Reach the delivery point
    ├── C  am I already there?       already at the delivery node
    └── -> To the delivery point     navigation subtree (rami/navigazione.py)
"""
from rami.comuni import Condizione, selettore
from rami.navigazione import crea_navigazione


def crea_consegna(mondo):
    """Build the reach-delivery subtree for ``mondo`` (structure in the module docstring)."""
    return selettore(
        "Reach the delivery point",
        Condizione("am I already there?", lambda: mondo.posizione == mondo.ordine.consegna),
        crea_navigazione(mondo, "To the delivery point", lambda: mondo.ordine.consegna),
    )
