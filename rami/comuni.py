"""Generic leaf nodes and small helpers shared by all branches.

In the hand-drawn tree, circles marked "C" are *conditions* and ovals are
*actions*. Here both are thin wrappers around a plain Python callable, so each
branch module can be written declaratively, e.g.::

    selettore("Ordine",
              Condizione("ho un ordine?", lambda: mondo.ordine is not None),
              Azione("attendi ordine", lambda: ...))

py_trees refresher (version 2.x):
* Every node returns a Status when ticked: SUCCESS, FAILURE or RUNNING.
* Sequence ("->" in the drawing): ticks children left to right and stops at the
  first one that does not return SUCCESS, returning that status. SUCCESS only
  if every child succeeds.
* Selector ("?" in the drawing, a.k.a. fallback): ticks children left to right
  and stops at the first one that does not return FAILURE. FAILURE only if every
  child fails.
* RUNNING means "not done yet, tick me again": the whole tick ends there.

All composites are created with ``memory=False`` (reactive): on every tick
evaluation restarts from the first child, so higher-priority checks (battery,
"am I already there?") are re-evaluated continuously instead of being skipped
while a long action is running.

Glossary: condizione = condition, azione = action, esito = outcome,
selettore = selector, sequenza = sequence, nome = name, figli = children.
"""
import py_trees
from py_trees.common import Status


class Condizione(py_trees.behaviour.Behaviour):
    """Condition leaf: SUCCESS if ``test()`` is true, otherwise FAILURE.

    ``test`` is a zero-argument callable, usually a Mondo perception method or a
    lambda around one. It must not change the world (conditions only look).
    """

    def __init__(self, nome, test):
        super().__init__(nome)   # nome = name shown in the tree printout and in the terminal view
        self.test = test

    def update(self):
        # update() is the py_trees hook called on every tick of this node.
        return Status.SUCCESS if self.test() else Status.FAILURE


class Azione(py_trees.behaviour.Behaviour):
    """Action leaf: runs ``azione()``, which must return a py_trees Status directly.

    Actions usually wrap a Mondo action method with ``esito(...)`` to choose
    which Status success and failure map to (see below).
    """

    def __init__(self, nome, azione):
        super().__init__(nome)
        self.azione = azione

    def update(self):
        return self.azione()


def esito(riuscito, se_vero=Status.SUCCESS, se_falso=Status.FAILURE):
    """Convert a boolean into a Status: ``se_vero`` if ``riuscito``, else ``se_falso``.

    Typical uses:
    * ``esito(mondo.prendi())`` -> SUCCESS / FAILURE (one-shot action);
    * ``esito(mondo.avanza(d), Status.RUNNING)`` -> RUNNING while it makes
      progress, FAILURE if it cannot (a step of a longer journey);
    * ``esito(mondo.ricarica(), Status.SUCCESS, Status.RUNNING)`` -> keep
      RUNNING until the action is complete.
    """
    return se_vero if riuscito else se_falso


def selettore(nome, *figli):
    """Reactive Selector ("?" node): the first child that does not fail wins."""
    return py_trees.composites.Selector(nome, memory=False, children=list(figli))


def sequenza(nome, *figli):
    """Reactive Sequence ("->" node): all children must succeed, in order."""
    return py_trees.composites.Sequence(nome, memory=False, children=list(figli))
