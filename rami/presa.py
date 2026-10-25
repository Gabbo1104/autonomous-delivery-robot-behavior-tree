"""Branch "Prendere l'oggetto" (pick up the item).

    ? Prendere l'oggetto
    ├── C  ho già l'oggetto in mano?   already holding it: SUCCESS
    └── A  prendi                      pick it up (SUCCESS / FAILURE)

Only reached when the pickup branch succeeded, i.e. the robot is at the pickup
node (or already carrying the item).
"""
from rami.comuni import Azione, Condizione, esito, selettore


def crea_presa(mondo):
    """Build the pick-up subtree for ``mondo`` (structure in the module docstring)."""
    return selettore(
        "Prendere l'oggetto",
        Condizione("ho già l'oggetto in mano?", lambda: mondo.oggetto_in_mano is not None),
        Azione("prendi", lambda: esito(mondo.prendi())),
    )
