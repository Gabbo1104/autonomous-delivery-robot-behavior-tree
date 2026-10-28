"""Leaf "put down the item" (at the delivery node).

A single action directly under the root. It is ticked only after the delivery
branch succeeded, and in the same tick "close the order" follows it.
"""
from robot_consegne.rami.comuni import Azione, esito


def crea_posa(mondo):
    """Build the put-down leaf for ``mondo``."""
    return Azione("put down the item", lambda: esito(mondo.posa()))
