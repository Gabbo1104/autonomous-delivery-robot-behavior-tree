"""Tests for the terminal view (tui.py) without a real terminal.

Frames are rendered into a string with rich's Console.capture(); the rich Live
display is replaced by a fake object so the animation can run instantly
(time.sleep is patched out) while recording every robot position.
"""
from rich.console import Console

from robot_consegne import mappa
from robot_consegne import tui
from robot_consegne.main import simula
from robot_consegne.mondo import Mondo, Ordine


def schermata(vista, larghezza=130):
    """Render the whole frame of ``vista`` to plain text (no colours) at the given width."""
    console = Console(width=larghezza, color_system=None)
    with console.capture() as cattura:
        console.print(vista.disegna())
    return cattura.get()


def test_disegna_robot_ritiro_consegna_e_porte():
    """A frame shows robot, pickup and delivery markers, the order, and every door closed at start."""
    m = Mondo([Ordine(1, "pacco", "r131", "r111")], posizione="c_103")
    m.attendi_ordine()
    out = schermata(tui.Vista(m, "prova", 1, affiancati=True))
    assert "@" in out and "A" in out and "B" in out
    console = Console(width=80, color_system=None)
    with console.capture() as cattura:
        console.print(tui.Vista(m, "prova", 1).pannello_mappa())
    assert cattura.get().count("▒") == len(mappa.CELLE_PORTE)   # every door closed
    assert "pacco: r131 → r111" in out


class LiveFinto:
    """Stand-in for rich.live.Live: accepts update() calls and draws nothing."""
    def update(self, _, refresh=False):
        pass


def test_animazione_casella_per_casella_senza_attraversare_muri(monkeypatch):
    """Recorded robot positions move one cell at a time and only ever on free cells or door cells."""
    monkeypatch.setattr(tui.time, "sleep", lambda s: None)
    m = Mondo([Ordine(1, "pacco", "r131", "r111")], posizione="lab_a")
    v = tui.Vista(m, "prova", 1)
    posizioni = []
    live = LiveFinto()
    live.update = lambda *_ , **__: posizioni.append(v.robot)
    simula(m, 500, dopo_tick=v.dopo_tick(live, 0))
    assert m.finito()
    for (c1, r1), (c2, r2) in zip(posizioni, posizioni[1:]):
        assert max(abs(c1 - c2), abs(r1 - r2)) <= 1          # never jumps
    porte = set(mappa.CELLE_PORTE.values())
    for c, r in posizioni:
        assert mappa.GRIGLIA[r][c] == mappa.LIBERO or (c, r) in porte


def test_modalita_compatta_sta_in_30_righe():
    """Compact mode fits in map height + 2 rows and 73 columns, with the status in the frame title."""
    m = Mondo([Ordine(1, "pacco", "r131", "r111")], posizione="c_103", batteria=40)
    m.attendi_ordine()
    out = schermata(tui.Vista(m, "prova", 1, compatta=True), larghezza=73)
    righe = out.splitlines()
    assert len(righe) == mappa.ALTEZZA + 2 and max(len(r) for r in righe) <= 73
    assert "battery 40%" in righe[0] and "r131→r111" in righe[0]
