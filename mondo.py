"""Simulated world: the robot's state, doors, obstacles and delivery orders.

``Mondo`` ("world") is the single source of truth of the simulation. The
behaviour tree (rami/*.py) never changes state directly: its condition leaves
call the *perception* methods (``batteria_ok``, ``strada_libera``,
``porta_chiusa``, ...) and its action leaves call the *action* methods
(``avanza``, ``spingi``, ``ricarica``, ...). Keeping all rules here means you
can change how the world behaves without touching the tree, and vice versa.

Time is discrete. The main loop (main.simula) ticks the tree once per step and
then increments ``Mondo.tick``. Every action does at most one "unit" of work per
call (move along ONE edge, open ONE door, charge ONE step), which is why most
actions in the tree return RUNNING: the tree re-evaluates everything on the next
tick, so it reacts immediately to a low battery, a new obstacle, etc.

What the robot knows vs. what is true:
* ``ostacoli``: the real obstacles (carts, people) on corridor edges. The robot
  does NOT know them in advance; it only "sees" the edge right in front of it.
* ``bloccati_noti``: obstacles it has already discovered. Path planning avoids
  only these, so the robot sometimes has to turn back (see ``torna_indietro``).

Battery model: moving costs CONSUMO_PER_METRO % per metre, opening a door costs
CONSUMO_PORTA %, charging gives RICARICA_PER_TICK % per tick. Change these
constants to make the robot more or less autonomous.

Glossary of Italian names: mondo = world, ordine = order, ritiro = pickup,
consegna = delivery, arrivo = arrival time, oggetto = item, batteria = battery,
in carica = charging, posizione = position, porta = door, aperta = open,
ostacolo = obstacle, bloccato = blocked, noto = known, spingi = push,
chiave = key, avanza = move forward, torna indietro = turn back,
scale = stairs, registra = log, prossimo passo = next step, destinazione = target.
"""
from dataclasses import dataclass
import random

import mappa
from percorso import costruisci_grafo, distanza, lunghezza, percorso

# Battery model (all values are percentages of a full battery).
CONSUMO_PER_METRO = 0.1     # % per metre: with a 20% reserve the robot can drive a full lap (~180 m)
CONSUMO_PORTA = 0.5         # % to open a door
RICARICA_PER_TICK = 10.0    # % recovered per tick while on the charger
# Item names used for generated orders (cycled; a "#n" suffix keeps them unique).
OGGETTI = ["pacco", "libro", "chiavetta", "caffè", "documenti", "attrezzi", "campione", "cavo"]


@dataclass
class Ordine:
    """A delivery order: carry ``oggetto`` from node ``ritiro`` to node ``consegna``."""
    id: int
    oggetto: str            # item name; must be unique across orders (it is a dict key in Mondo.oggetti)
    ritiro: str             # pickup node (where the item initially is)
    consegna: str           # delivery node
    arrivo: int = 0         # tick at which the order becomes available to the robot


def genera_ordini(n, seed=None):
    """Create ``n`` orders with random pickup and delivery nodes (always different).

    Any node of the map can be a pickup/delivery point, corridors included.
    Orders arrive at increasing ticks (0 to 30 ticks apart), so with several
    orders the robot sometimes has to wait ("attendi ordine").
    The same ``seed`` always produces the same orders (reproducible runs).
    """
    rng = random.Random(seed)
    ordini, arrivo = [], 0
    for i in range(n):
        ritiro, consegna = rng.sample(list(mappa.NODI), 2)   # sample() never returns the same node twice
        ordini.append(Ordine(i + 1, f"{OGGETTI[i % len(OGGETTI)]} #{i + 1}", ritiro, consegna, arrivo))
        arrivo += rng.randint(0, 30)
    return ordini


def genera_ostacoli(n, seed=None):
    """Pick up to ``n`` random obstacles (carts, people) on corridor edges.

    Only edges between two corridor nodes ("c_" prefix) without a door are
    candidates. An obstacle is accepted only if, together with the ones already
    chosen, every node is still reachable from mappa.PARTENZA; otherwise it is
    skipped. This guarantees the scenario is always solvable (an early version
    could cut off the whole east corridor). Since the graph is undirected,
    "reachable from PARTENZA" means "everything is connected", whatever the
    robot's actual starting node is.
    """
    rng = random.Random(seed)
    corridoio = [(a, b) for a, b, porta in mappa.ARCHI
                 if porta is None and a.startswith("c_") and b.startswith("c_")]
    rng.shuffle(corridoio)
    scelti = []
    for e in corridoio:
        if len(scelti) == n:
            break
        prova = scelti + [e]   # tentatively add this obstacle
        if all(percorso(mappa.NODI, mappa.ARCHI, mappa.PARTENZA, nodo, bloccati=prova)
               for nodo in mappa.NODI):
            scelti = prova
    return scelti


def genera_partenza(seed=None):
    """Random starting node (anywhere on the map) and initial battery ``randint(1, 100)``."""
    rng = random.Random(seed)
    return rng.choice(list(mappa.NODI)), rng.randint(1, 100)


def arco(a, b):
    """Edge identifier independent of direction: arco(a, b) == arco(b, a).

    Used as the key for doors, open doors and obstacles.
    """
    return frozenset((a, b))


class Mondo:
    """The whole simulation state plus the rules for perceiving and changing it.

    Most methods take ``destinazione`` (the node the robot is currently heading
    to). They look at the *next edge* on the planned route towards it: "is the
    road in front of me free?", "is there a door?", "push it", "move along it".
    The route is recomputed on every call from the current position and the
    known obstacles, so there is no stored path that could go stale.

    Methods return booleans; the tree leaves in rami/ turn them into py_trees
    Status values (SUCCESS / FAILURE / RUNNING).
    """

    def __init__(self, ordini=(), ostacoli=(), batteria=100.0, posizione=mappa.PARTENZA, verboso=False):
        # --- robot -----------------------------------------------------------
        self.posizione = posizione      # current node
        self.batteria = float(batteria)  # charge in %, 0..100
        self.in_carica = False          # True from the first charging tick until 100% (see ricarica)
        self.tick = 0                   # advanced by main.simula after each tree tick
        # --- orders ----------------------------------------------------------
        self.coda = sorted(ordini, key=lambda o: o.arrivo)  # pending orders, earliest first
        self.ordine = None              # order currently being served (None = idle)
        self.completati = []            # closed orders, in completion order
        self.oggetto_in_mano = None     # name of the item being carried, if any
        self.oggetti = {o.oggetto: o.ritiro for o in ordini}   # item -> node where it lies (absent while carried)
        # --- doors -----------------------------------------------------------
        # edge -> node the door swings towards (only edges that have a door)
        self.porte = {arco(a, b): verso for a, b, verso in mappa.ARCHI if verso}  # swing direction
        self.porte_aperte = set()       # edges whose door is currently open
        # --- obstacles -------------------------------------------------------
        self.ostacoli = {arco(a, b) for a, b in ostacoli}   # the robot does not know these
        self.bloccati_noti = set()                          # obstacles already discovered
        # Neighbours of each node (used by allontanati_dalle_scale).
        self.grafo = costruisci_grafo(mappa.NODI, mappa.ARCHI)
        # --- statistics / output --------------------------------------------
        self.metri = 0.0                # total distance travelled
        self.ultimo_passo = None   # (from, to) of the latest move, read and reset by the terminal view
        self.verboso = verboso          # True = also print every log line (main.py)
        self.log = []                   # human-readable event log (Italian, shown to the user)

    # --- helpers --------------------------------------------------------------
    def registra(self, messaggio):
        """Append an event to the log, prefixed with the current tick."""
        riga = f"[t{self.tick:04d}] {messaggio}"
        self.log.append(riga)
        if self.verboso:
            print(riga)

    def _consuma(self, quanto):
        """Drain ``quanto`` % of battery, never going below 0."""
        self.batteria = max(0.0, self.batteria - quanto)

    def prossimo_passo(self, destinazione):
        """Next node on the shortest route to ``destinazione`` avoiding KNOWN obstacles.

        None if the robot is already there or no route exists.
        """
        if self.posizione == destinazione:
            return None
        p = percorso(mappa.NODI, mappa.ARCHI, self.posizione, destinazione,
                     bloccati=[tuple(e) for e in self.bloccati_noti])
        return p[1] if p else None   # p[0] is the current position

    def _arco_davanti(self, destinazione):
        """(next node, edge to it) on the way to ``destinazione``, or (None, None)."""
        nxt = self.prossimo_passo(destinazione)
        return (nxt, arco(self.posizione, nxt)) if nxt else (None, None)

    def _sposta(self, nodo):
        """Physically move to the neighbouring ``nodo`` (callers check the way is clear).

        Pays the battery cost of the distance, stops any charging, logs the move
        and closes the door behind the robot. Fails only with a flat battery.
        """
        if self.batteria <= 0:
            self.registra("batteria scarica: impossibile muoversi")
            return False
        e = arco(self.posizione, nodo)
        metri = distanza(mappa.NODI[self.posizione], mappa.NODI[nodo])
        self._consuma(metri * CONSUMO_PER_METRO)
        self.metri += metri
        self.registra(f"{self.posizione} -> {nodo} ({self.batteria:.0f}%)")
        self.ultimo_passo = (self.posizione, nodo)
        self.posizione = nodo
        self.in_carica = False
        self.porte_aperte.discard(e)   # doors close again once the robot has gone through
        return True

    # --- perception (used by the Condition leaves) ---------------------------
    def costo_ritorno(self):
        """Estimated % of battery needed to reach the charger from here.

        Uses the shortest route that avoids the known obstacles, counting both
        the distance and every door on the way. Returns 100 (i.e. "impossible")
        if the charger is currently unreachable.
        """
        p = percorso(mappa.NODI, mappa.ARCHI, self.posizione, "caricabatterie",
                     bloccati=[tuple(e) for e in self.bloccati_noti])
        porte = sum(arco(a, b) in self.porte for a, b in zip(p, p[1:])) if p else 0
        return (lunghezza(mappa.NODI, p) * CONSUMO_PER_METRO + porte * CONSUMO_PORTA) if p else 100.0

    def batteria_ok(self):
        """Battery condition of the tree: more than 20% LEFT OVER after getting back to the charger.

        The original drawing says "> 20%". A fixed 20% left the robot stranded
        in 2-14% of runs when hidden obstacles forced long detours, so the
        reserve is now counted on top of the cost of the way back: the further
        the robot is from the charger, the earlier it goes to recharge.
        While charging (``in_carica``) this stays False, so the robot keeps
        charging until 100% instead of leaving at 21%.
        """
        return self.batteria - self.costo_ritorno() > 20 and not self.in_carica

    def al_caricabatterie(self):
        """True if the robot is on the charging station node."""
        return self.posizione == "caricabatterie"

    def lontano_dalle_scale(self):
        """True if the robot is at a safe distance from the open staircase."""
        return distanza(mappa.NODI[self.posizione], mappa.SCALE) >= mappa.DISTANZA_SICUREZZA_SCALE

    def strada_libera(self, destinazione):
        """True if the next edge towards ``destinazione`` can be travelled right now.

        That means: no obstacle on it, and either no door or an open door. When
        there is no next edge, the road is "free" only if the robot has already
        arrived (no route at all counts as not free).
        """
        nxt, e = self._arco_davanti(destinazione)
        if nxt is None:
            return self.posizione == destinazione
        return e not in self.ostacoli and (e not in self.porte or e in self.porte_aperte)

    def porta_chiusa(self, destinazione):
        """True if there is a closed door on the next edge ("c'è una porta?" in the tree)."""
        _, e = self._arco_davanti(destinazione)
        return e is not None and e in self.porte and e not in self.porte_aperte

    def porta_a_spinta(self, destinazione):
        """True if the door in front swings in the direction the robot is going.

        That is the "bisogna spingere?" ("do I need to push?") condition: if the
        door opens away from the robot it can push it; otherwise opening it would
        require pulling, which the robot cannot do.
        """
        nxt, e = self._arco_davanti(destinazione)
        return e in self.porte and self.porte[e] == nxt

    # --- actions (used by the Action leaves) ----------------------------------
    def spingi(self, destinazione):
        """Push open the door in front. Only works from the side it swings away from."""
        if not self.porta_chiusa(destinazione) or not self.porta_a_spinta(destinazione):
            return False
        return self._apri(destinazione, "spinge la porta")

    def usa_chiave(self, destinazione):
        """Open the door in front with the key.

        Used when the door would swing towards the robot (it would have to pull):
        the key unlocks the automatic opener. It works on any closed door; the
        tree only reaches it after "bisogna spingere?" failed.
        """
        if not self.porta_chiusa(destinazione):
            return False
        return self._apri(destinazione, "non può tirare: usa la chiave sulla porta")

    def _apri(self, destinazione, descrizione):
        """Mark the door on the next edge as open, pay the energy cost and log it."""
        nxt, e = self._arco_davanti(destinazione)
        self.porte_aperte.add(e)
        self._consuma(CONSUMO_PORTA)
        self.registra(f"{descrizione} {self.posizione}|{nxt}")
        return True

    def avanza(self, destinazione):
        """Move ONE edge towards ``destinazione`` if the road in front is free."""
        nxt = self.prossimo_passo(destinazione)
        if nxt is None or not self.strada_libera(destinazione):
            return False
        return self._sposta(nxt)

    def torna_indietro(self, destinazione):
        """The edge in front is blocked by an obstacle: remember it and re-plan.

        The robot does not move here; the next tick plans a route that avoids the
        newly known obstacle (which usually means going back the way it came).
        Returns False if no alternative route exists.
        """
        nxt, e = self._arco_davanti(destinazione)
        if e is None:
            return False
        self.bloccati_noti.add(e)
        self.registra(f"ostacolo su {self.posizione}|{nxt}: ripianifico")
        return self.prossimo_passo(destinazione) is not None

    def allontanati_dalle_scale(self, destinazione):
        """Step to a neighbouring node that is further from the stairs.

        Candidates are neighbours reachable without a door and without a known
        or real obstacle, and strictly further from the stairs than the current
        node. If the next node towards the target is among them it is preferred
        (so the robot keeps making progress); otherwise it takes the candidate
        furthest from the stairs. Returns False if there is nowhere to go.
        """
        qui = distanza(mappa.NODI[self.posizione], mappa.SCALE)
        candidati = [n for n in self.grafo[self.posizione]
                     if arco(self.posizione, n) not in self.porte
                     and arco(self.posizione, n) not in self.bloccati_noti | self.ostacoli
                     and distanza(mappa.NODI[n], mappa.SCALE) > qui]
        if not candidati:
            return False
        nxt = self.prossimo_passo(destinazione)
        scelto = nxt if nxt in candidati else max(candidati, key=lambda n: distanza(mappa.NODI[n], mappa.SCALE))
        self.registra("troppo vicino alle scale: mi allontano")
        return self._sposta(scelto)

    def vai_verso(self, destinazione):
        """One automatic step towards ``destinazione`` ("go to charge" in the tree).

        The battery branch of the drawing has a single "go to charge" action, so
        this method bundles the navigation logic: open a closed door (push if
        possible, otherwise key), re-plan around an obstacle, or move forward.
        Returns True when already there or when it made progress.
        """
        if self.posizione == destinazione:
            return True
        if self.porta_chiusa(destinazione):
            return self.spingi(destinazione) or self.usa_chiave(destinazione)
        if not self.strada_libera(destinazione):
            return self.torna_indietro(destinazione)
        return self.avanza(destinazione)

    def ricarica(self):
        """Charge for one tick. Returns True only when the battery reaches 100%.

        Sets ``in_carica`` so that batteria_ok() stays False until the battery is
        full: this implements "complete the action only when it reaches 100%".
        """
        if not self.in_carica:
            self.registra(f"inizio ricarica ({self.batteria:.0f}%)")
        self.in_carica = True
        self.batteria = min(100.0, self.batteria + RICARICA_PER_TICK)
        if self.batteria >= 100:
            self.in_carica = False
            self.registra("ricarica completata (100%)")
            return True
        return False

    def attendi_ordine(self):
        """Take the next order if it has arrived (its ``arrivo`` tick has passed)."""
        if self.coda and self.coda[0].arrivo <= self.tick:
            self.ordine = self.coda.pop(0)
            o = self.ordine
            self.registra(f"nuovo ordine {o.id}: {o.oggetto} da {o.ritiro} a {o.consegna}")
            return True
        return False

    def prendi(self):
        """Pick up the current order's item. Requires being at the pickup node with the item there."""
        o = self.ordine
        if o is None or self.posizione != o.ritiro or self.oggetti.get(o.oggetto) != self.posizione:
            return False
        del self.oggetti[o.oggetto]   # the item is no longer lying anywhere: it is in the robot's hands
        self.oggetto_in_mano = o.oggetto
        self.registra(f"prende {o.oggetto} in {self.posizione}")
        return True

    def posa(self):
        """Put down the carried item. Requires carrying the right item at the delivery node."""
        o = self.ordine
        if o is None or self.oggetto_in_mano != o.oggetto or self.posizione != o.consegna:
            return False
        self.oggetti[o.oggetto] = self.posizione
        self.oggetto_in_mano = None
        self.registra(f"posa {o.oggetto} in {self.posizione}")
        return True

    def chiudi_ordine(self):
        """Close the current order, but only if its item really lies at the delivery node."""
        if self.ordine is None or self.oggetti.get(self.ordine.oggetto) != self.ordine.consegna:
            return False
        self.completati.append(self.ordine)
        self.registra(f"ordine {self.ordine.id} chiuso")
        self.ordine = None
        return True

    def finito(self):
        """True when there are no pending orders and none in progress (simulation over)."""
        return not self.coda and self.ordine is None
