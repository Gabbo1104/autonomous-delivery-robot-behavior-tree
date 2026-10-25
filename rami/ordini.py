"""Order branch: carry on only if there is an order, otherwise wait for one.

    ? Ordine
    ├── C  ho un ordine?     ("do I have an order?")
    └── A  attendi ordine    ("wait for an order": SUCCESS as soon as one is
                              taken from the queue, RUNNING while waiting)

Taking an order and serving it can happen in the same tick: when "attendi
ordine" succeeds the root Sequence moves straight on to the pickup branch.
"""
from py_trees.common import Status

from rami.comuni import Azione, Condizione, esito, selettore


def crea_ordini(mondo):
    """Build the order subtree for ``mondo`` (structure in the module docstring)."""
    return selettore(
        "Ordine",
        Condizione("ho un ordine?", lambda: mondo.ordine is not None),
        Azione("attendi ordine", lambda: esito(mondo.attendi_ordine(), Status.SUCCESS, Status.RUNNING)),
    )
