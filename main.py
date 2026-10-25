"""Robot che prende un oggetto in una stanza e lo porta in un'altra (behavior tree py_trees).

Esempi:
    uv run main.py
    uv run main.py --ordini 8 --ostacoli 3 --seed 7 --batteria 40
    uv run main.py --mostra-albero
"""
import argparse

import py_trees

from mondo import Mondo, genera_ordini, genera_ostacoli
from rami.batteria import crea_batteria
from rami.chiusura import crea_chiusura
from rami.consegna import crea_consegna
from rami.ordini import crea_ordini
from rami.posa import crea_posa
from rami.presa import crea_presa
from rami.ritiro import crea_ritiro


def crea_albero(mondo):
    radice = py_trees.composites.Sequence("Root", memory=False, children=[
        crea_batteria(mondo),
        crea_ordini(mondo),
        crea_ritiro(mondo),
        crea_presa(mondo),
        crea_consegna(mondo),
        crea_posa(mondo),
        crea_chiusura(mondo),
    ])
    return py_trees.trees.BehaviourTree(radice)


def simula(mondo, max_tick=5000, mostra_stato=False):
    albero = crea_albero(mondo)
    albero.setup()
    while not mondo.finito() and mondo.tick < max_tick and mondo.batteria > 0:
        albero.tick()
        if mostra_stato:
            print(py_trees.display.unicode_tree(albero.root, show_only_visited=True, show_status=True))
        mondo.tick += 1
    return albero


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ordini", type=int, default=5)
    ap.add_argument("--ostacoli", type=int, default=2, help="ostacoli nascosti nel corridoio")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--batteria", type=float, default=100.0, help="carica iniziale in %%")
    ap.add_argument("--max-tick", type=int, default=5000)
    ap.add_argument("--mostra-albero", action="store_true", help="stampa l'albero e esce")
    ap.add_argument("--stato", action="store_true", help="stampa lo stato dell'albero a ogni tick")
    args = ap.parse_args()

    mondo = Mondo(genera_ordini(args.ordini, args.seed), genera_ostacoli(args.ostacoli, args.seed),
                  batteria=args.batteria, verboso=True)
    if args.mostra_albero:
        print(py_trees.display.unicode_tree(crea_albero(mondo).root))
        return
    simula(mondo, args.max_tick, args.stato)
    esito = ("tutti gli ordini completati" if mondo.finito()
             else "robot fermo: batteria scarica" if mondo.batteria <= 0 else "limite di tick raggiunto")
    print(f"\n{esito}: {len(mondo.completati)}/{args.ordini} ordini, {mondo.tick} tick, "
          f"{mondo.metri:.0f} m percorsi, batteria {mondo.batteria:.0f}%")


if __name__ == "__main__":
    main()
