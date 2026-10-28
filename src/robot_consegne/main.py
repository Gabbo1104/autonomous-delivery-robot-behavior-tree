"""Robot that picks up an item in one room and carries it to another (py_trees behavior tree).

Start, pick-up point, delivery point and battery are random;
the same --seed replays the same simulation.

Examples:
    uv run robot
    uv run robot --seed 42
    uv run robot --ordini 8 --ostacoli 3 --seed 7 --batteria 40
    uv run robot --mostra-albero
    uv run robot-tui              # same simulation, animated in the terminal
"""
# NOTE: the docstring above is passed to argparse (description=__doc__) and is
# what users see with --help.
#
# Entry point of the project: builds the behaviour tree and runs the simulation
# as plain text (one log line per event). tui.py reuses simula(),
# opzioni_scenario(), crea_scenario() and riepilogo() from here to run the very
# same simulation with an animated terminal view.
#
# Project layout
# --------------
#   src/robot_consegne/   the package
#     main.py         this file: tree assembly, simulation loop, command line
#     tui.py          animated terminal view (rich)
#     mondo.py        simulated world: robot state, battery, doors, obstacles, orders
#     mappa.py        floor map: graph (nodes/edges/doors) + character grid with walls
#     percorso.py     generic shortest-path functions (Dijkstra) on the graph
#     rami/           one module per branch of the behaviour tree (see rami/__init__.py)
#   tests/            pytest suite: `uv run pytest`
#   docs/             behavior tree diagram (draw.io + SVG)
#
# How one simulation step works
# -----------------------------
# 1. simula() calls albero.tick(): py_trees walks the tree from the root.
# 2. Condition leaves query the world (mondo.batteria_ok(), mondo.strada_libera(), ...);
#    action leaves change it (mondo.avanza(), mondo.spingi(), ...), each doing at most
#    one unit of work (one edge, one door, one charging step).
# 3. mondo.tick is incremented and the loop repeats until every order is closed, the
#    tick limit is reached, or the battery is flat away from the charger.
#
# Italian -> English glossary (identifiers are in Italian)
# --------------------------------------------------------
#   albero = tree, radice = root, ramo/rami = branch(es), nodo = node, arco = edge,
#   mondo = world, mappa = map, griglia = grid, cella/casella = cell,
#   percorso = path, ordine/ordini = order(s), ritiro = pickup, consegna = delivery,
#   presa = picking up, posa = putting down, chiusura = closing,
#   batteria = battery, caricabatterie = charger, porta = door, ostacolo = obstacle,
#   scale = stairs, partenza = start, seed = random seed, simula = simulate,
#   riepilogo = summary, vista = view, stato = state/status, esito = outcome.
import argparse
import random

import py_trees

from robot_consegne.mondo import Mondo, genera_ordini, genera_ostacoli, genera_partenza
from robot_consegne.rami.batteria import crea_batteria
from robot_consegne.rami.chiusura import crea_chiusura
from robot_consegne.rami.consegna import crea_consegna
from robot_consegne.rami.ordini import crea_ordini
from robot_consegne.rami.posa import crea_posa
from robot_consegne.rami.presa import crea_presa
from robot_consegne.rami.ritiro import crea_ritiro


def crea_albero(mondo):
    """Assemble the full behaviour tree for ``mondo`` and wrap it in a BehaviourTree.

    The root is a reactive Sequence ("->" in the drawing, memory=False): on every
    tick it re-evaluates its children from the first one, so the battery check
    always runs first and can interrupt a delivery at any moment. The children
    are the seven branches of the drawing, left to right. To change the robot's
    behaviour, edit or add branches in rami/ and adjust this list.
    """
    radice = py_trees.composites.Sequence("Root", memory=False, children=[
        crea_batteria(mondo),     # enough charge? otherwise go and recharge
        crea_ordini(mondo),       # is there an order? otherwise wait
        crea_ritiro(mondo),       # reach the pickup point
        crea_presa(mondo),        # pick up the item
        crea_consegna(mondo),     # reach the delivery point
        crea_posa(mondo),         # put the item down
        crea_chiusura(mondo),     # close the order
    ])
    return py_trees.trees.BehaviourTree(radice)


def simula(mondo, max_tick=5000, mostra_stato=False, dopo_tick=None):
    """Run the simulation on ``mondo`` until it ends; return the BehaviourTree.

    Stops when all orders are closed, after ``max_tick`` ticks, or when the
    battery is at 0% and the robot is not on the charger (it cannot move any
    more). A robot that reaches the charger with exactly 0% may still recharge.

    ``mostra_stato`` prints the visited part of the tree with each node's status
    after every tick (handy for debugging the tree logic).
    ``dopo_tick(albero)``, if given, is called after every tick; tui.py uses it
    to animate the move that just happened before the next tick starts.
    """
    albero = crea_albero(mondo)
    albero.setup()   # py_trees: lets behaviours initialise themselves (no-op for ours)
    while not mondo.finito() and mondo.tick < max_tick and (mondo.batteria > 0 or mondo.al_caricabatterie()):
        mondo.aggiorna_piano()   # energy plan for this tick (logged when it changes)
        albero.tick()
        if mostra_stato:
            print(py_trees.display.unicode_tree(albero.root, show_only_visited=True, show_status=True))
        if dopo_tick:
            dopo_tick(albero)
        mondo.tick += 1
    return albero


def opzioni_scenario(ap):
    """Add the command-line options shared by main.py and tui.py to parser ``ap``.

    --ordini     number of orders (default 1)
    --ostacoli   number of hidden obstacles placed in the corridors
    --seed       random seed; omit it for a random scenario (the seed is printed
                 so that an interesting run can be replayed exactly)
    --batteria   initial charge in % (default 100: the robot starts fully charged)
    --max-tick   safety limit on the number of ticks
    """
    ap.add_argument("--ordini", type=int, default=1)
    ap.add_argument("--ostacoli", type=int, default=2, help="hidden obstacles in the corridors")
    ap.add_argument("--seed", type=int, help="default: random (it is printed)")
    ap.add_argument("--batteria", type=float, default=100.0, help="initial charge in %% (default 100)")
    ap.add_argument("--max-tick", type=int, default=5000)


def crea_scenario(args, verboso=False):
    """Create the world from the parsed options: random start, charger, orders, obstacles.

    Everything random is derived from a single seed, so the same ``--seed``
    reproduces the same run. Returns ``(mondo, header)`` where ``header`` is a
    one-line description (seed, start node, charger, battery) to show to the user.
    ``verboso=True`` makes the world print every event as it happens (main.py);
    tui.py passes False and shows events in its own panel.
    """
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    ostacoli = genera_ostacoli(args.ostacoli, seed)
    partenza, caricatore = genera_partenza(seed)
    mondo = Mondo(genera_ordini(args.ordini, seed), ostacoli, batteria=args.batteria,
                  posizione=partenza, caricatore=caricatore, verboso=verboso)
    return mondo, f"seed {seed}: start {partenza}, charger {caricatore}, battery {args.batteria:.0f}%"


def riepilogo(mondo, ordini):
    """One-line summary of how the simulation ended (shown to the user)."""
    esito = ("all orders completed" if mondo.finito()
             else "robot stopped: battery flat" if mondo.batteria <= 0 else "tick limit reached")
    return (f"{esito}: {len(mondo.completati)}/{ordini} orders, {mondo.tick} ticks, "
            f"{mondo.metri:.0f} m travelled, battery {mondo.batteria:.0f}%")


def main():
    """Command-line entry point: parse options, build the scenario, run it as text."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opzioni_scenario(ap)
    ap.add_argument("--mostra-albero", action="store_true", help="print the tree and exit")
    ap.add_argument("--stato", action="store_true", help="print the status of the tree at every tick")
    args = ap.parse_args()

    mondo, intestazione = crea_scenario(args, verboso=True)
    if args.mostra_albero:
        # Just print the structure of the tree and exit, without simulating.
        print(py_trees.display.unicode_tree(crea_albero(mondo).root))
        return
    print(intestazione)
    simula(mondo, args.max_tick, args.stato)
    print("\n" + riepilogo(mondo, args.ordini))


if __name__ == "__main__":
    main()
