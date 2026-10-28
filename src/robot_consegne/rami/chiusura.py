"""Leaf "close the order".

Last child of the root. Mondo.chiudi_ordine checks that the item really lies at
the delivery node before closing; afterwards ``mondo.ordine`` is None again, so
on the next tick the order branch waits for (or takes) the next order.
"""
from robot_consegne.rami.comuni import Azione, esito


def crea_chiusura(mondo):
    """Build the close-order leaf for ``mondo``."""
    return Azione("close the order", lambda: esito(mondo.chiudi_ordine()))
