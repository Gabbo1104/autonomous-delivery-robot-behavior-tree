import math

import pytest

import mappa
from percorso import costruisci_grafo, distanza, lunghezza, percorso

# Quadrato con diagonale lunga: A(0,0) B(1,0) C(1,1) D(0,1), E isolato
NODI = {"A": (0, 0), "B": (1, 0), "C": (1, 1), "D": (0, 1), "E": (5, 5)}
ARCHI = [("A", "B", None), ("B", "C", "spinta"), ("C", "D", None), ("D", "A", None)]


def test_distanza():
    assert distanza((0, 0), (3, 4)) == 5
    assert distanza((1, 1), (1, 1)) == 0


def test_grafo_non_orientato_con_pesi():
    g = costruisci_grafo(NODI, ARCHI)
    assert g["A"]["B"] == 1 and g["B"]["A"] == 1
    assert set(g["A"]) == {"B", "D"}
    assert g["E"] == {}


def test_stesso_nodo():
    assert percorso(NODI, ARCHI, "A", "A") == ["A"]


def test_percorso_breve():
    assert percorso(NODI, ARCHI, "A", "B") == ["A", "B"]
    assert percorso(NODI, ARCHI, "A", "C") in (["A", "B", "C"], ["A", "D", "C"])


def test_bloccati_in_entrambi_i_versi():
    assert percorso(NODI, ARCHI, "A", "B", bloccati=[("B", "A")]) == ["A", "D", "C", "B"]
    assert percorso(NODI, ARCHI, "A", "C", bloccati={("A", "B")}) == ["A", "D", "C"]


def test_irraggiungibile():
    assert percorso(NODI, ARCHI, "A", "E") is None
    assert percorso(NODI, ARCHI, "A", "B", bloccati=[("A", "B"), ("D", "A")]) is None


def test_nodo_sconosciuto():
    with pytest.raises(ValueError):
        percorso(NODI, ARCHI, "A", "Z")
    with pytest.raises(ValueError):
        percorso(NODI, ARCHI, "Z", "A")


def test_sceglie_il_piu_corto_non_quello_con_meno_archi():
    nodi = {"S": (0, 0), "M1": (1, 0), "M2": (2, 0), "M3": (3, 0), "T": (4, 0), "X": (2, 10)}
    archi = [("S", "M1", None), ("M1", "M2", None), ("M2", "M3", None), ("M3", "T", None),
             ("S", "X", None), ("X", "T", None)]
    assert percorso(nodi, archi, "S", "T") == ["S", "M1", "M2", "M3", "T"]


def test_lunghezza():
    assert lunghezza(NODI, ["A", "B", "C"]) == 2
    assert lunghezza(NODI, ["A"]) == 0


def test_mappa_vera():
    p = percorso(mappa.NODI, mappa.ARCHI, "c_103", "r103")
    assert p == ["c_103", "r103"]
    p = percorso(mappa.NODI, mappa.ARCHI, "r101", "r131")
    assert p[0] == "r101" and p[-1] == "r131"
    # tra lab_a e lab_c conviene passare per lab_b
    assert percorso(mappa.NODI, mappa.ARCHI, "lab_a", "lab_c") == ["lab_a", "lab_b", "lab_c"]


def test_mappa_vera_tutto_raggiungibile():
    for n in mappa.NODI:
        assert percorso(mappa.NODI, mappa.ARCHI, mappa.PARTENZA, n) is not None, n


def test_mappa_vera_aggira_il_blocco():
    libero = percorso(mappa.NODI, mappa.ARCHI, "c_103", "c_sud_ovest")
    assert "c_scale" in libero
    aggirato = percorso(mappa.NODI, mappa.ARCHI, "c_103", "c_sud_ovest", bloccati=[("c_scale", "c_101")])
    assert aggirato is not None and "c_scale" not in aggirato
    assert math.isclose(lunghezza(mappa.NODI, libero), 29.0)
