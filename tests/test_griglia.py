"""Consistency checks between the graph and the character grid in mappa.py.

Run these after editing the map: they catch nodes placed inside walls, doors
without a cell, edges that would cross a wall when animated, rooms that leak
into the corridor and walkable stairs.
"""
import math

from robot_consegne import mappa


def test_nodi_su_caselle_libere():
    """Every graph node sits on a free grid cell (not in a wall or on the stairs)."""
    for nodo, (c, r) in mappa.CELLE.items():
        assert mappa.GRIGLIA[r][c] == mappa.LIBERO, nodo


def test_ogni_porta_sta_in_un_muro_e_ha_un_verso():
    """Door edges and door cells match one-to-one; each door is in a wall and swings towards one of its two nodes."""
    archi_con_porta = {frozenset((a, b)): verso for a, b, verso in mappa.ARCHI if verso}
    assert set(mappa.CELLE_PORTE) == set(archi_con_porta)
    for e, verso in archi_con_porta.items():
        assert verso in e
        c, r = mappa.CELLE_PORTE[e]
        assert mappa.GRIGLIA[r][c] == mappa.MURO


def test_ogni_arco_si_percorre_senza_attraversare_muri():
    """Every edge has a grid path that only uses free cells plus its own door, and is not absurdly long."""
    for a, b, _ in mappa.ARCHI:
        celle = mappa.celle_arco(a, b)
        assert celle and celle[0] == mappa.CELLE[a] and celle[-1] == mappa.CELLE[b], (a, b)
        porta = mappa.CELLE_PORTE.get(frozenset((a, b)))
        for c, r in celle[1:-1]:
            assert mappa.GRIGLIA[r][c] == mappa.LIBERO or (c, r) == porta, (a, b, c, r)
        if porta:
            assert porta in celle
        # no strange detours: at most a bit longer than the straight line
        assert len(celle) - 1 <= math.dist(mappa.CELLE[a], mappa.CELLE[b]) * 1.6 + 4, (a, b)


def test_stanze_chiuse_se_le_porte_sono_chiuse():
    """With all doors closed, no room can reach the corridor, while every corridor node can."""
    corridoio = mappa.CELLE["c_103"]
    for nodo, cella in mappa.CELLE.items():
        stanza = not nodo.startswith("c_") and nodo != "charger"
        assert (mappa.percorso_griglia(cella, corridoio) is None) == stanza, nodo


def test_scale_invalicabili():
    """The stairs are stairs cells and cannot be entered from the corridor."""
    sotto, sopra = (15, 25), mappa.CELLE["c_stairs"]
    assert mappa.GRIGLIA[25][15] == mappa.SCALINI
    assert mappa.percorso_griglia(sopra, sotto) is None
