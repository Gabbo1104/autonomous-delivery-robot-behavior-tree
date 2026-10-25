"""Branch "Raggiungi il punto di ritiro" (reach the pickup point).

    ? Raggiungi il punto di ritiro
    ├── C  ho l'oggetto in mano?   already carrying the item: nothing to do
    ├── C  sono già lì?            already at the pickup node
    └── -> Verso il ritiro         navigation subtree (rami/navigazione.py)

The first condition matters because the root Sequence restarts from the top on
every tick: once the item is picked up, this branch must succeed immediately so
that the tree moves on to the delivery branch instead of going back for pickup.
"""
from rami.comuni import Condizione, selettore
from rami.navigazione import crea_navigazione


def crea_ritiro(mondo):
    """Build the reach-pickup subtree for ``mondo`` (structure in the module docstring)."""
    return selettore(
        "Raggiungi il punto di ritiro",
        Condizione("ho l'oggetto in mano?", lambda: mondo.oggetto_in_mano is not None),
        Condizione("sono già lì?", lambda: mondo.posizione == mondo.ordine.ritiro),
        crea_navigazione(mondo, "Verso il ritiro", lambda: mondo.ordine.ritiro),
    )
