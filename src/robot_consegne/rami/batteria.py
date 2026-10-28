"""Battery branch: if the energy plan needs a recharge now, go to the charger and charge up to 100%.

Structure (as in the drawing)::

    ? Battery
    ├── C  enough charge for the plan and not charging?   -> SUCCESS, carry on
    └── -> Recharge
        ├── ? Reach the charger
        │   ├── C  am I at the charger?
        │   └── A  go to charge                                 (one step per tick, RUNNING)
        └── A  charge                                           (RUNNING until 100%)

Because the root is a Sequence and this is its first child, while this branch
returns RUNNING nothing else in the tree is ticked: the robot "drops" whatever
it was doing (keeping the item in hand, if any) and resumes once charged.

The plan (Mondo.calcola_piano) decides in advance where the recharge goes: if
the charge is not enough for pickup + delivery, the robot charges before the
pickup or between pickup and delivery, whichever route is shorter.
"""
from py_trees.common import Status

from robot_consegne.rami.comuni import Azione, Condizione, esito, selettore, sequenza


def crea_batteria(mondo):
    """Build the battery subtree for ``mondo`` (structure in the module docstring)."""
    # One automatic step towards the charger per tick (doors and obstacles are
    # handled inside Mondo.vai_verso). RUNNING while moving, FAILURE if stuck.
    vai_in_carica = Azione("go to charge",
                           lambda: esito(mondo.vai_verso(mondo.caricatore), Status.RUNNING))
    # "complete the action only when it reaches 100%": RUNNING until full
    carica = Azione("charge", lambda: esito(mondo.ricarica(), Status.SUCCESS, Status.RUNNING))
    return selettore(
        "Battery",
        # The planning logic lives in Mondo.calcola_piano (RISERVA % left after
        # every leg plus the way to the charger).
        Condizione("enough charge for the plan and not charging?", mondo.batteria_ok),
        sequenza(
            "Recharge",
            selettore("Reach the charger",
                      Condizione("am I at the charger?", mondo.al_caricabatterie),
                      vai_in_carica),
            carica,
        ),
    )
