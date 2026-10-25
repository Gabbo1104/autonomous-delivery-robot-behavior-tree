"""Battery branch: if the charge is low, go to the charger and charge up to 100%.

Structure (as in the drawing)::

    ? Batteria
    ├── C  livello > 20% (oltre al ritorno) e non in carica?   -> enough charge: SUCCESS, carry on
    └── -> Ricarica
        ├── ? Raggiungi caricabatterie
        │   ├── C  mi trovo al caricabatterie?
        │   └── A  go to charge                                 (one step per tick, RUNNING)
        └── A  charge                                           (RUNNING until 100%)

Because the root is a Sequence and this is its first child, while this branch
returns RUNNING nothing else in the tree is ticked: the robot "drops" whatever
it was doing (keeping the item in hand, if any) and resumes once charged.
"""
from py_trees.common import Status

from rami.comuni import Azione, Condizione, esito, selettore, sequenza


def crea_batteria(mondo):
    """Build the battery subtree for ``mondo`` (structure in the module docstring)."""
    # One automatic step towards the charger per tick (doors and obstacles are
    # handled inside Mondo.vai_verso). RUNNING while moving, FAILURE if stuck.
    vai_in_carica = Azione("go to charge",
                           lambda: esito(mondo.vai_verso("caricabatterie"), Status.RUNNING))
    # "complete the action only when it reaches 100%": RUNNING until full
    carica = Azione("charge", lambda: esito(mondo.ricarica(), Status.SUCCESS, Status.RUNNING))
    return selettore(
        "Batteria",
        # The threshold logic lives in Mondo.batteria_ok (20% reserve on top of
        # the energy needed to get back to the charger).
        Condizione("livello > 20% (oltre al ritorno) e non in carica?", mondo.batteria_ok),
        sequenza(
            "Ricarica",
            selettore("Raggiungi caricabatterie",
                      Condizione("mi trovo al caricabatterie?", mondo.al_caricabatterie),
                      vai_in_carica),
            carica,
        ),
    )
