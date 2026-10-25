from rich.console import Console

import mappa
import tui
from main import simula
from mondo import Mondo, Ordine


def schermata(vista, larghezza=130):
    console = Console(width=larghezza, color_system=None)
    with console.capture() as cattura:
        console.print(vista.disegna())
    return cattura.get()


def test_disegna_robot_ritiro_consegna_e_porte():
    m = Mondo([Ordine(1, "pacco", "r131", "r111")], posizione="c_103")
    m.attendi_ordine()
    out = schermata(tui.Vista(m, "prova", 1, affiancati=True))
    assert "@" in out and "A" in out and "B" in out
    console = Console(width=80, color_system=None)
    with console.capture() as cattura:
        console.print(tui.Vista(m, "prova", 1).pannello_mappa())
    assert cattura.get().count("▒") == len(mappa.CELLE_PORTE)   # tutte le porte chiuse
    assert "pacco: r131 → r111" in out


class LiveFinto:
    def update(self, _, refresh=False):
        pass


def test_animazione_casella_per_casella_senza_attraversare_muri(monkeypatch):
    monkeypatch.setattr(tui.time, "sleep", lambda s: None)
    m = Mondo([Ordine(1, "pacco", "r131", "r111")], posizione="lab_a")
    v = tui.Vista(m, "prova", 1)
    posizioni = []
    live = LiveFinto()
    live.update = lambda *_ , **__: posizioni.append(v.robot)
    simula(m, 500, dopo_tick=v.dopo_tick(live, 0))
    assert m.finito()
    for (c1, r1), (c2, r2) in zip(posizioni, posizioni[1:]):
        assert max(abs(c1 - c2), abs(r1 - r2)) <= 1          # mai salti
    porte = set(mappa.CELLE_PORTE.values())
    for c, r in posizioni:
        assert mappa.GRIGLIA[r][c] == mappa.LIBERO or (c, r) in porte
