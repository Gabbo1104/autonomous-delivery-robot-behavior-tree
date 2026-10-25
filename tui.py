"""Simulazione animata nel terminale: mappa, robot che si muove casella per casella,
porte che si aprono e stato del behavior tree.

Esempi:
    uv run tui.py
    uv run tui.py --seed 42 --velocita 25
    uv run tui.py --batteria 10 --ostacoli 4
"""
import argparse
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import mappa
from main import crea_scenario, opzioni_scenario, riepilogo, simula
from mondo import arco

STILE = {
    "muro": "grey62 on grey23", "scale": "magenta", "etichetta": "grey50",
    "porta_chiusa": "bold yellow on grey23", "porta_aperta": "bold green",
    "carica": "bold bright_green", "ritiro": "bold black on green", "consegna": "bold white on red",
    "ostacolo_nascosto": "red dim", "ostacolo": "bold white on dark_red",
    "robot": "bold white on blue", "robot_carico": "bold white on magenta",
}
# (simbolo, descrizione, stile)
LEGENDA = [("@", "robot", "robot"), ("A", "ritiro", "ritiro"), ("B", "consegna", "consegna"),
           ("+", "carica", "carica"), ("▒", "porta chiusa", "porta_chiusa"),
           ("░", "porta aperta", "porta_aperta"), ("X", "ostacolo", "ostacolo")]


LARGHEZZA_MINIMA = mappa.LARGHEZZA + 2   # mappa + bordo del riquadro


def centro(celle):
    return celle[len(celle) // 2]


class Vista:
    def __init__(self, mondo, intestazione, ordini, affiancati=False, compatta=False):
        self.mondo = mondo
        self.affiancati = affiancati   # stato accanto alla mappa invece che sotto
        self.compatta = compatta       # terminale basso: stato essenziale nel bordo della mappa
        self.intestazione = intestazione
        self.ordini = ordini
        self.robot = mappa.CELLE[mondo.posizione]
        self.porta_in_transito = None
        self.albero = None
        self.ostacoli = {e: centro(mappa.celle_arco(*e)) for e in mondo.ostacoli}

    # --- disegno -------------------------------------------------------------
    def _caselle(self):
        """Griglia di (carattere, stile)."""
        m = self.mondo
        g = [[(" ", "") if ch == mappa.LIBERO else
              ("≡", STILE["scale"]) if ch == mappa.SCALINI else ("█", STILE["muro"])
              for ch in riga] for riga in mappa.GRIGLIA]
        for nome, (c, r) in mappa.ETICHETTE.items():
            for i, ch in enumerate(nome):
                g[r][c + i] = (ch, STILE["etichetta"])
        for e, (c, r) in mappa.CELLE_PORTE.items():
            aperta = e in m.porte_aperte or (c, r) == self.porta_in_transito
            g[r][c] = ("░", STILE["porta_aperta"]) if aperta else ("▒", STILE["porta_chiusa"])
        c, r = mappa.CELLE["caricabatterie"]
        g[r][c] = ("+", STILE["carica"])
        for e, (c, r) in self.ostacoli.items():
            g[r][c] = ("X", STILE["ostacolo"]) if e in m.bloccati_noti else ("x", STILE["ostacolo_nascosto"])
        if m.ordine:
            if m.oggetti.get(m.ordine.oggetto) == m.ordine.ritiro:
                c, r = mappa.CELLE[m.ordine.ritiro]
                g[r][c] = ("A", STILE["ritiro"])
            c, r = mappa.CELLE[m.ordine.consegna]
            g[r][c] = ("B", STILE["consegna"])
        c, r = self.robot
        g[r][c] = ("@", STILE["robot_carico" if m.oggetto_in_mano else "robot"])
        return g

    def pannello_mappa(self):
        t = Text(no_wrap=True)
        for i, riga in enumerate(self._caselle()):
            for ch, stile in riga:
                t.append(ch, stile)
            if i < mappa.ALTEZZA - 1:
                t.append("\n")
        if self.compatta:
            m = self.mondo
            titolo = (f"t{m.tick} · batteria {m.batteria:.0f}%{' ⚡' if m.in_carica else ''} · "
                      + (f"{m.ordine.ritiro}→{m.ordine.consegna}" if m.ordine else "nessun ordine")
                      + (f" · in mano {m.oggetto_in_mano}" if m.oggetto_in_mano else ""))
            evento = m.log[-1].split("] ", 1)[1] if m.log else self.intestazione
            sottotitolo = f"{self._ramo_attivo().split(' › ')[-1]} · {evento}"
            return Panel(t, title=titolo, subtitle=sottotitolo[:LARGHEZZA_MINIMA - 6], expand=False, padding=0)
        return Panel(t, title="Piano del laboratorio", subtitle=self.intestazione, expand=False, padding=0)

    def _ramo_attivo(self):
        if self.albero is None:
            return "-"
        nodo, catena = self.albero.root.tip(), []
        while nodo is not None:
            catena.append(nodo.name)
            nodo = nodo.parent
        return " › ".join(reversed(catena[:-1])) or catena[-1]

    def pannello_stato(self):
        m = self.mondo
        tab = Table.grid(padding=(0, 1))
        tab.add_column(style="bold", no_wrap=True)
        tab.add_column()
        pieni = round(m.batteria / 5)
        colore = "green" if m.batteria > 50 else "yellow" if m.batteria > 20 else "red"
        barra = Text("█" * pieni, colore) + Text("░" * (20 - pieni), "grey37")
        barra.append(f" {m.batteria:3.0f}%" + ("  ⚡ in carica" if m.in_carica else ""))
        o = m.ordine
        tab.add_row("tick", str(m.tick))
        tab.add_row("batteria", barra)
        tab.add_row("ordine", f"{o.oggetto}: {o.ritiro} → {o.consegna}" if o else
                    f"nessuno ({len(m.completati)}/{self.ordini} completati)")
        tab.add_row("in mano", m.oggetto_in_mano or "-")
        tab.add_row("nodo", m.posizione)
        tab.add_row("albero", Text(self._ramo_attivo(), "cyan"))
        legenda = Text()
        for simbolo, nome, stile in LEGENDA:
            legenda.append(f" {simbolo} ", STILE[stile])
            legenda.append(f"{nome}  ")
        righe_eventi = 14 if self.affiancati else 4
        eventi = Text("\n".join(r.split("] ", 1)[1] for r in m.log[-righe_eventi:]), "grey70")
        larghezza = 52 if self.affiancati else LARGHEZZA_MINIMA
        return Panel(Group(tab, Text(), eventi, Text(), legenda), title="Stato", width=larghezza)

    def disegna(self):
        if self.compatta:
            return self.pannello_mappa()
        if self.affiancati:
            griglia = Table.grid(padding=(0, 1))
            griglia.add_row(self.pannello_mappa(), self.pannello_stato())
            return griglia
        return Group(self.pannello_mappa(), self.pannello_stato())

    # --- animazione ---------------------------------------------------------
    def dopo_tick(self, live, ritardo):
        def aggiorna(albero):
            self.albero = albero
            m = self.mondo
            if m.ultimo_passo:
                da, a = m.ultimo_passo
                m.ultimo_passo = None
                self.porta_in_transito = mappa.CELLE_PORTE.get(arco(da, a))
                for cella in mappa.celle_arco(da, a)[1:]:
                    self.robot = cella
                    live.update(self.disegna(), refresh=True)
                    time.sleep(ritardo)
                self.porta_in_transito = None
            # pausa breve anche per azioni senza movimento (porte, ricarica, presa)
            live.update(self.disegna(), refresh=True)
            time.sleep(ritardo * 4)
        return aggiorna


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opzioni_scenario(ap)
    ap.add_argument("--velocita", type=float, default=12, help="caselle al secondo (default 12)")
    args = ap.parse_args()

    mondo, intestazione = crea_scenario(args)
    console = Console()
    if console.width < LARGHEZZA_MINIMA:
        console.print(f"[bold yellow]Il terminale è largo {console.width} colonne, la mappa ne richiede "
                      f"{LARGHEZZA_MINIMA}: allarga la finestra o rimpicciolisci il carattere, "
                      f"altrimenti il lato est viene tagliato.[/]")
        time.sleep(3)
    affiancati = console.width >= LARGHEZZA_MINIMA + 53
    compatta = not affiancati and console.height < mappa.ALTEZZA + 2 + 17
    vista = Vista(mondo, intestazione, args.ordini, affiancati, compatta)
    try:
        with Live(vista.disegna(), console=console, auto_refresh=False) as live:
            time.sleep(1)
            simula(mondo, args.max_tick, dopo_tick=vista.dopo_tick(live, 1 / args.velocita))
            live.update(vista.disegna(), refresh=True)
    except KeyboardInterrupt:
        console.print("[yellow]simulazione interrotta[/]")
    console.print(f"[bold]{riepilogo(mondo, args.ordini)}[/]")


if __name__ == "__main__":
    main()
