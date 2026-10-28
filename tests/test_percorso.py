"""Tests for percorso.py (shortest paths on the floor graph).

These tests were written first and used as the specification when percorso.py
was delegated to the local model (delega-locale skill): the model could see but
not modify this file. They cover a small hand-made graph (a unit square plus an
isolated node) and the real map from mappa.py.
"""
import math

import pytest

from robot_consegne import mappa
from robot_consegne.percorso import costruisci_grafo, distanza, lunghezza, percorso

# Unit square A(0,0) B(1,0) C(1,1) D(0,1) without diagonals, plus E isolated.
# The third item of each edge is ignored by percorso.py ("spinta" is a leftover
# door marker from an older version of the map format; any value works).
NODI = {"A": (0, 0), "B": (1, 0), "C": (1, 1), "D": (0, 1), "E": (5, 5)}
ARCHI = [("A", "B", None), ("B", "C", "spinta"), ("C", "D", None), ("D", "A", None)]


def test_distanza():
    """Euclidean distance (3-4-5 triangle) and distance of a point from itself."""
    assert distanza((0, 0), (3, 4)) == 5
    assert distanza((1, 1), (1, 1)) == 0


def test_grafo_non_orientato_con_pesi():
    """Edges go both ways with Euclidean weights; isolated nodes still get an (empty) entry."""
    g = costruisci_grafo(NODI, ARCHI)
    assert g["A"]["B"] == 1 and g["B"]["A"] == 1
    assert set(g["A"]) == {"B", "D"}
    assert g["E"] == {}


def test_stesso_nodo():
    """Start == goal returns a one-node path."""
    assert percorso(NODI, ARCHI, "A", "A") == ["A"]


def test_percorso_breve():
    """Direct neighbour, and a two-step path (either way around the square is fine)."""
    assert percorso(NODI, ARCHI, "A", "B") == ["A", "B"]
    assert percorso(NODI, ARCHI, "A", "C") in (["A", "B", "C"], ["A", "D", "C"])


def test_bloccati_in_entrambi_i_versi():
    """A blocked pair forbids the edge in both directions, whatever order it is given in."""
    assert percorso(NODI, ARCHI, "A", "B", bloccati=[("B", "A")]) == ["A", "D", "C", "B"]
    assert percorso(NODI, ARCHI, "A", "C", bloccati={("A", "B")}) == ["A", "D", "C"]


def test_irraggiungibile():
    """Unreachable goals (isolated node, or all routes blocked) return None."""
    assert percorso(NODI, ARCHI, "A", "E") is None
    assert percorso(NODI, ARCHI, "A", "B", bloccati=[("A", "B"), ("D", "A")]) is None


def test_nodo_sconosciuto():
    """Unknown start or goal raises ValueError instead of returning None."""
    with pytest.raises(ValueError):
        percorso(NODI, ARCHI, "A", "Z")
    with pytest.raises(ValueError):
        percorso(NODI, ARCHI, "Z", "A")


def test_sceglie_il_piu_corto_non_quello_con_meno_archi():
    """Shortest means fewest metres, not fewest edges: the long detour via X has fewer hops."""
    nodi = {"S": (0, 0), "M1": (1, 0), "M2": (2, 0), "M3": (3, 0), "T": (4, 0), "X": (2, 10)}
    archi = [("S", "M1", None), ("M1", "M2", None), ("M2", "M3", None), ("M3", "T", None),
             ("S", "X", None), ("X", "T", None)]
    assert percorso(nodi, archi, "S", "T") == ["S", "M1", "M2", "M3", "T"]


def test_lunghezza():
    """Path length is the sum of step lengths; a single node has length 0."""
    assert lunghezza(NODI, ["A", "B", "C"]) == 2
    assert lunghezza(NODI, ["A"]) == 0


def test_mappa_vera():
    """Sanity checks on the real map (direct door edge, cross-building route, lab A -> lab C via lab B)."""
    p = percorso(mappa.NODI, mappa.ARCHI, "c_103", "r103")
    assert p == ["c_103", "r103"]
    p = percorso(mappa.NODI, mappa.ARCHI, "r101", "r131")
    assert p[0] == "r101" and p[-1] == "r131"
    # from lab_a to lab_c the shortest way is through lab_b
    assert percorso(mappa.NODI, mappa.ARCHI, "lab_a", "lab_c") == ["lab_a", "lab_b", "lab_c"]


def test_mappa_vera_tutto_raggiungibile():
    """Every node of the real map is reachable from the default start (no missing edges or typos)."""
    for n in mappa.NODI:
        assert percorso(mappa.NODI, mappa.ARCHI, mappa.PARTENZA, n) is not None, n


def test_mappa_vera_aggira_il_blocco():
    """Blocking the corridor next to the stairs forces a route around the ring; checks one exact length too."""
    libero = percorso(mappa.NODI, mappa.ARCHI, "c_103", "c_south_west")
    assert "c_stairs" in libero
    aggirato = percorso(mappa.NODI, mappa.ARCHI, "c_103", "c_south_west", bloccati=[("c_stairs", "c_101")])
    assert aggirato is not None and "c_stairs" not in aggirato
    assert math.isclose(lunghezza(mappa.NODI, libero), 29.0)
