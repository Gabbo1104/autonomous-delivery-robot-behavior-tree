"""Branch "Raggiungi il punto di consegna" (reach the delivery point).

    ? Raggiungi il punto di consegna
    ├── C  sono già lì?          already at the delivery node
    └── -> Verso la consegna     navigation subtree (rami/navigazione.py)
"""
from rami.comuni import Condizione, selettore
from rami.navigazione import crea_navigazione


def crea_consegna(mondo):
    """Build the reach-delivery subtree for ``mondo`` (structure in the module docstring)."""
    return selettore(
        "Raggiungi il punto di consegna",
        Condizione("sono già lì?", lambda: mondo.posizione == mondo.ordine.consegna),
        crea_navigazione(mondo, "Verso la consegna", lambda: mondo.ordine.consegna),
    )
