"""Nodi foglia generici: condizioni (cerchi C nel disegno) e azioni (ovali)."""
import py_trees
from py_trees.common import Status


class Condizione(py_trees.behaviour.Behaviour):
    """SUCCESS se test() è vero, altrimenti FAILURE."""

    def __init__(self, nome, test):
        super().__init__(nome)
        self.test = test

    def update(self):
        return Status.SUCCESS if self.test() else Status.FAILURE


class Azione(py_trees.behaviour.Behaviour):
    """Esegue azione(), che restituisce direttamente uno Status."""

    def __init__(self, nome, azione):
        super().__init__(nome)
        self.azione = azione

    def update(self):
        return self.azione()


def esito(riuscito, se_vero=Status.SUCCESS, se_falso=Status.FAILURE):
    return se_vero if riuscito else se_falso


def selettore(nome, *figli):
    return py_trees.composites.Selector(nome, memory=False, children=list(figli))


def sequenza(nome, *figli):
    return py_trees.composites.Sequence(nome, memory=False, children=list(figli))
