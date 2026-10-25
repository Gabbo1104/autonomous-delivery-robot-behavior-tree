"""Branches of the behaviour tree: one module per child of the root.

The root (built in main.crea_albero) is a Sequence that ticks these branches in
order, left to right, exactly as in the hand-drawn tree:

    batteria   -> make sure there is enough charge (or go and recharge)
    ordini     -> make sure there is an order (or wait for one)
    ritiro     -> reach the pickup point
    presa      -> pick up the item
    consegna   -> reach the delivery point
    posa       -> put the item down
    chiusura   -> close the order

Every module exposes one ``crea_<name>(mondo)`` factory that returns the
subtree. ``comuni`` holds the generic leaf classes and helpers; ``navigazione``
holds the movement subtree shared by ``ritiro`` and ``consegna``.

To add a branch: write ``rami/<name>.py`` with a ``crea_<name>(mondo)`` function
built from the helpers in ``comuni``, then insert it in the children list of the
root in main.crea_albero at the right position.
"""
