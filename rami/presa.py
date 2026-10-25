"""Branch "Pick up the item".

    ? Pick up the item
    ├── C  am I already holding the item?   already holding it: SUCCESS
    └── A  pick up                          pick it up (SUCCESS / FAILURE)

Only reached when the pickup branch succeeded, i.e. the robot is at the pickup
node (or already carrying the item).
"""
from rami.comuni import Azione, Condizione, esito, selettore


def crea_presa(mondo):
    """Build the pick-up subtree for ``mondo`` (structure in the module docstring)."""
    return selettore(
        "Pick up the item",
        Condizione("am I already holding the item?", lambda: mondo.oggetto_in_mano is not None),
        Azione("pick up", lambda: esito(mondo.prendi())),
    )
