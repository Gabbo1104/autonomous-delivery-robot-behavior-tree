"""Leaf "posa l'oggetto" (put the item down at the delivery node).

A single action directly under the root. It is ticked only after the delivery
branch succeeded, and in the same tick "chiudi l'ordine" follows it.
"""
from rami.comuni import Azione, esito


def crea_posa(mondo):
    """Build the put-down leaf for ``mondo``."""
    return Azione("posa l'oggetto", lambda: esito(mondo.posa()))
