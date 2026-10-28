"""Animated simulation in the terminal: map, robot moving cell by cell,
doors opening and status of the behavior tree.

Examples:
    uv run robot-tui
    uv run robot-tui --seed 42 --velocita 25
    uv run robot-tui --batteria 10 --ostacoli 4
"""
# NOTE: the docstring above is the --help text (description=__doc__).
#
# Animated terminal view of the simulation, built with the `rich` library.
#
# How it works
# ------------
# The simulation itself is exactly the one of main.py: main.simula() ticks the
# behaviour tree in a loop. This module only adds a callback (Vista.dopo_tick)
# that runs after every tick:
#   * if the robot moved along an edge during that tick (Mondo.ultimo_passo),
#     the robot marker is moved cell by cell along mappa.celle_arco(from, to),
#     redrawing the screen and sleeping between cells. That path comes from a
#     grid search that cannot cross walls, so the animation respects the walls;
#   * otherwise (door opened, charging, item picked up...) the screen is simply
#     redrawn, with a short pause so that the action is visible.
# The world state is never changed here: the view only reads Mondo.
#
# Screen layouts (chosen in main() from the terminal size)
# --------------------------------------------------------
#   * side by side: map on the left, status panel on the right (>= 126 columns);
#   * stacked: map above, status panel below (needs about 47 rows);
#   * compact: map only, with tick/battery/order in the frame title and the
#     active tree node + latest event in the frame subtitle (fits in 30 rows).
# The map always needs LARGHEZZA_MINIMA (73) columns; narrower terminals get a
# warning because rich would crop the east side.
#
# How to customise
# ----------------
#   * colours: edit STILE (rich style strings, e.g. "bold white on blue");
#   * symbols: edit the characters in Vista._caselle and keep LEGENDA in sync;
#   * speed: --velocita (cells per second); pause after non-moving actions is
#     4 cells' worth of time (see dopo_tick).
#
# Glossary: vista = view, disegna = draw, pannello = panel, caselle = cells,
# stile = style, legenda = legend, compatta = compact, affiancati = side by side,
# ritardo = delay, velocita = speed, ramo attivo = active branch,
# porta in transito = door being crossed, intestazione = header.
import argparse
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from robot_consegne import mappa
from robot_consegne.main import crea_scenario, opzioni_scenario, riepilogo, simula
from robot_consegne.mondo import arco

# rich style of every kind of cell / marker.
STILE = {
    "muro": "grey62 on grey23", "scale": "magenta", "etichetta": "grey50",
    "porta_chiusa": "bold yellow on grey23", "porta_aperta": "bold green",
    "carica": "bold bright_green", "ritiro": "bold black on green", "consegna": "bold white on red",
    "ostacolo_nascosto": "red dim", "ostacolo": "bold white on dark_red",
    "robot": "bold white on blue", "robot_carico": "bold white on magenta",
}
# Legend shown in the status panel: (symbol, description, key in STILE).
LEGENDA = [("@", "robot", "robot"), ("A", "pick-up", "ritiro"), ("B", "delivery", "consegna"),
           ("+", "charger", "carica"), ("▒", "closed door", "porta_chiusa"),
           ("░", "open door", "porta_aperta"), ("X", "obstacle", "ostacolo")]


LARGHEZZA_MINIMA = mappa.LARGHEZZA + 2   # map + panel border (one column per side)


def centro(celle):
    """Middle cell of a list of cells (where an obstacle on an edge is drawn)."""
    return celle[len(celle) // 2]


class Vista:
    """Renders the world on screen and animates the robot between ticks.

    Attributes worth knowing when modifying it:
    * ``robot``: cell where the robot marker is currently drawn. During an
      animation it runs ahead of/behind ``mondo.posizione`` (which is already
      the destination node), so drawing always uses this, not the node.
    * ``porta_in_transito``: door cell being crossed right now. The world closes
      a door as soon as the move is made, so without this the door would be
      drawn closed while the robot is still walking through it.
    * ``albero``: the BehaviourTree, set after the first tick; used to show
      which node of the tree is active.
    * ``ostacoli``: obstacle edge -> cell where it is drawn (middle of the edge).
    """

    def __init__(self, mondo, intestazione, ordini, affiancati=False, compatta=False):
        self.mondo = mondo
        self.affiancati = affiancati   # status panel beside the map instead of below it
        self.compatta = compatta       # short terminal: essential status in the map's frame
        self.intestazione = intestazione   # "seed ...: start ..., battery ...%"
        self.ordini = ordini               # total number of orders (for "n/total completed")
        self.robot = mappa.CELLE[mondo.posizione]
        self.porta_in_transito = None
        self.albero = None
        self.ostacoli = {e: centro(mappa.celle_arco(*e)) for e in mondo.ostacoli}

    # --- drawing ---------------------------------------------------------------
    def _caselle(self):
        """Grid of (character, style) for the current frame.

        Layers are painted in order, later ones on top: walls/stairs/floor,
        room labels, doors, charger, obstacles, pickup/delivery markers, robot.
        """
        m = self.mondo
        # Base layer from the logical grid.
        g = [[(" ", "") if ch == mappa.LIBERO else
              ("≡", STILE["scale"]) if ch == mappa.SCALINI else ("█", STILE["muro"])
              for ch in riga] for riga in mappa.GRIGLIA]
        for nome, (c, r) in mappa.ETICHETTE.items():
            for i, ch in enumerate(nome):
                g[r][c + i] = (ch, STILE["etichetta"])
        # Doors: open if the world says so or if the robot is crossing it now.
        for e, (c, r) in mappa.CELLE_PORTE.items():
            aperta = e in m.porte_aperte or (c, r) == self.porta_in_transito
            g[r][c] = ("░", STILE["porta_aperta"]) if aperta else ("▒", STILE["porta_chiusa"])
        c, r = mappa.CELLE[m.caricatore]
        g[r][c] = ("+", STILE["carica"])
        # Obstacles: faint "x" while still unknown to the robot, red "X" once discovered.
        for e, (c, r) in self.ostacoli.items():
            g[r][c] = ("X", STILE["ostacolo"]) if e in m.bloccati_noti else ("x", STILE["ostacolo_nascosto"])
        if m.ordine:
            # "A" only while the item is still waiting at the pickup point.
            if m.oggetti.get(m.ordine.oggetto) == m.ordine.ritiro:
                c, r = mappa.CELLE[m.ordine.ritiro]
                g[r][c] = ("A", STILE["ritiro"])
            c, r = mappa.CELLE[m.ordine.consegna]
            g[r][c] = ("B", STILE["consegna"])
        # Robot last, so it is always visible; magenta while carrying an item.
        c, r = self.robot
        g[r][c] = ("@", STILE["robot_carico" if m.oggetto_in_mano else "robot"])
        return g

    def pannello_mappa(self):
        """The map inside a frame. In compact mode the frame also carries the status."""
        t = Text(no_wrap=True)
        for i, riga in enumerate(self._caselle()):
            for ch, stile in riga:
                t.append(ch, stile)
            if i < mappa.ALTEZZA - 1:
                t.append("\n")
        if self.compatta:
            m = self.mondo
            # Title: tick, battery, current order and carried item.
            titolo = (f"t{m.tick} · battery {m.batteria:.0f}%{' ⚡' if m.in_carica else ''} · "
                      + (f"{m.ordine.ritiro}→{m.ordine.consegna}" if m.ordine else "no order")
                      + (f" · holding {m.oggetto_in_mano}" if m.oggetto_in_mano else ""))
            # Subtitle: active tree leaf + latest log event (without its "[tNNNN]" prefix),
            # cut to fit inside the frame.
            evento = m.log[-1].split("] ", 1)[1] if m.log else self.intestazione
            sottotitolo = f"{self._ramo_attivo().split(' › ')[-1]} · {evento}"
            return Panel(t, title=titolo, subtitle=sottotitolo[:LARGHEZZA_MINIMA - 6], expand=False, padding=0)
        return Panel(t, title="Laboratory floor", subtitle=self.intestazione, expand=False, padding=0)

    def _ramo_attivo(self):
        """Path in the tree from the root's child to the node that ended the last tick.

        py_trees' ``tip()`` returns the deepest node that ran in the last tick
        (e.g. "move forward"). Walking ``parent`` links back up gives something
        like "Reach the pick-up point › To the pick-up point › move forward".
        The root itself ("Root") is left out to save space.
        """
        if self.albero is None:
            return "-"   # before the first tick
        nodo, catena = self.albero.root.tip(), []
        while nodo is not None:
            catena.append(nodo.name)
            nodo = nodo.parent
        return " › ".join(reversed(catena[:-1])) or catena[-1]

    def pannello_stato(self):
        """Status panel: tick, battery bar, order, item, node, active branch, events, legend."""
        m = self.mondo
        tab = Table.grid(padding=(0, 1))
        tab.add_column(style="bold", no_wrap=True)   # labels
        tab.add_column()                             # values
        # 20-segment battery bar, green / yellow / red depending on the charge.
        pieni = round(m.batteria / 5)
        colore = "green" if m.batteria > 50 else "yellow" if m.batteria > 20 else "red"
        barra = Text("█" * pieni, colore) + Text("░" * (20 - pieni), "grey37")
        barra.append(f" {m.batteria:3.0f}%" + ("  ⚡ charging" if m.in_carica else ""))
        o = m.ordine
        tab.add_row("tick", str(m.tick))
        tab.add_row("battery", barra)
        tab.add_row("order", f"{o.oggetto}: {o.ritiro} → {o.consegna}" if o else
                    f"none ({len(m.completati)}/{self.ordini} completed)")
        tab.add_row("holding", m.oggetto_in_mano or "-")
        tab.add_row("node", m.posizione)
        tab.add_row("plan", m.testo_piano(m.piano) or "-")
        tab.add_row("tree", Text(self._ramo_attivo(), "cyan"))
        legenda = Text()
        for simbolo, nome, stile in LEGENDA:
            legenda.append(f" {simbolo} ", STILE[stile])
            legenda.append(f"{nome}  ")
        # Latest events without the "[tNNNN] " prefix; more of them fit when the
        # panel is beside the map (it is as tall as the map there).
        righe_eventi = 14 if self.affiancati else 4
        eventi = Text("\n".join(r.split("] ", 1)[1] for r in m.log[-righe_eventi:]), "grey70")
        larghezza = 52 if self.affiancati else LARGHEZZA_MINIMA
        return Panel(Group(tab, Text(), eventi, Text(), legenda), title="Status", width=larghezza)

    def disegna(self):
        """Whole frame for the current layout (compact, side by side or stacked)."""
        if self.compatta:
            return self.pannello_mappa()
        if self.affiancati:
            griglia = Table.grid(padding=(0, 1))
            griglia.add_row(self.pannello_mappa(), self.pannello_stato())
            return griglia
        return Group(self.pannello_mappa(), self.pannello_stato())

    # --- animation -------------------------------------------------------------
    def dopo_tick(self, live, ritardo):
        """Return the callback that main.simula calls after every tick.

        ``live`` is the rich Live display to redraw; ``ritardo`` is the delay in
        seconds between two cells of a move (1 / --velocita).
        """
        def aggiorna(albero):
            """Animate/redraw after one tick; ``albero`` is the BehaviourTree just ticked."""
            self.albero = albero
            m = self.mondo
            if m.ultimo_passo:
                # The robot moved along one edge in this tick: walk the marker
                # along the wall-respecting grid path of that edge.
                da, a = m.ultimo_passo
                m.ultimo_passo = None   # consume it, so it is not animated twice
                self.porta_in_transito = mappa.CELLE_PORTE.get(arco(da, a))
                for cella in mappa.celle_arco(da, a)[1:]:   # [0] is where the robot already is
                    self.robot = cella
                    live.update(self.disegna(), refresh=True)
                    time.sleep(ritardo)
                self.porta_in_transito = None
            # short pause even for actions without movement (doors, charging, pickup)
            live.update(self.disegna(), refresh=True)
            time.sleep(ritardo * 4)
        return aggiorna


def main():
    """Command-line entry point: parse options, pick a layout, run the animated simulation."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opzioni_scenario(ap)
    ap.add_argument("--velocita", type=float, default=12, help="cells per second (default 12)")
    args = ap.parse_args()

    mondo, intestazione = crea_scenario(args)
    console = Console()
    if console.width < LARGHEZZA_MINIMA:
        console.print(f"[bold yellow]The terminal is {console.width} columns wide, the map needs "
                      f"{LARGHEZZA_MINIMA}: widen the window or shrink the font, "
                      f"otherwise the east side is cut off.[/]")
        time.sleep(3)   # leave time to read the warning before the animation starts
    # Side by side needs the map plus a 52-column status panel and a 1-column gap;
    # otherwise use the stacked layout if there are enough rows, else compact.
    affiancati = console.width >= LARGHEZZA_MINIMA + 53
    compatta = not affiancati and console.height < mappa.ALTEZZA + 2 + 18
    vista = Vista(mondo, intestazione, args.ordini, affiancati, compatta)
    try:
        # auto_refresh=False: the screen is redrawn only when we call update(),
        # which keeps the animation in step with the simulation.
        with Live(vista.disegna(), console=console, auto_refresh=False) as live:
            time.sleep(1)   # show the starting position for a moment
            simula(mondo, args.max_tick, dopo_tick=vista.dopo_tick(live, 1 / args.velocita))
            live.update(vista.disegna(), refresh=True)
    except KeyboardInterrupt:
        # Ctrl-C: stop quietly and still print the summary.
        console.print("[yellow]simulation interrupted[/]")
    console.print(f"[bold]{riepilogo(mondo, args.ordini)}[/]")


if __name__ == "__main__":
    main()
