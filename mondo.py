"""Mondo simulato: stato del robot, porte, ostacoli e ordini sulla mappa del piano."""
from dataclasses import dataclass
import random

import mappa
from percorso import costruisci_grafo, distanza, lunghezza, percorso

CONSUMO_PER_METRO = 0.1     # % per metro: col 20% di riserva si fa un giro intero (~180 m)
CONSUMO_PORTA = 0.5         # % per aprire una porta
RICARICA_PER_TICK = 10.0    # % recuperata a ogni tick sul caricabatterie
OGGETTI = ["pacco", "libro", "chiavetta", "caffè", "documenti", "attrezzi", "campione", "cavo"]


@dataclass
class Ordine:
    id: int
    oggetto: str
    ritiro: str
    consegna: str
    arrivo: int = 0         # tick in cui l'ordine diventa disponibile


def genera_ordini(n, seed=None):
    """Ordini con punto di ritiro e di consegna casuali (diversi) su tutta la mappa."""
    rng = random.Random(seed)
    ordini, arrivo = [], 0
    for i in range(n):
        ritiro, consegna = rng.sample(list(mappa.NODI), 2)
        ordini.append(Ordine(i + 1, f"{OGGETTI[i % len(OGGETTI)]} #{i + 1}", ritiro, consegna, arrivo))
        arrivo += rng.randint(0, 30)
    return ordini


def genera_ostacoli(n, seed=None):
    """Ostacoli (carrelli, persone) su archi del corridoio: l'anello resta percorribile."""
    rng = random.Random(seed)
    corridoio = [(a, b) for a, b, porta in mappa.ARCHI
                 if porta is None and a.startswith("c_") and b.startswith("c_")]
    rng.shuffle(corridoio)
    scelti = []
    for e in corridoio:
        if len(scelti) == n:
            break
        prova = scelti + [e]
        if all(percorso(mappa.NODI, mappa.ARCHI, mappa.PARTENZA, nodo, bloccati=prova)
               for nodo in mappa.NODI):
            scelti = prova
    return scelti


def genera_partenza(seed=None):
    """Punto di partenza e carica iniziale (randint 1-100) casuali."""
    rng = random.Random(seed)
    return rng.choice(list(mappa.NODI)), rng.randint(1, 100)


def arco(a, b):
    return frozenset((a, b))


class Mondo:
    def __init__(self, ordini=(), ostacoli=(), batteria=100.0, posizione=mappa.PARTENZA, verboso=False):
        self.posizione = posizione
        self.batteria = float(batteria)
        self.in_carica = False
        self.tick = 0
        self.coda = sorted(ordini, key=lambda o: o.arrivo)
        self.ordine = None
        self.completati = []
        self.oggetto_in_mano = None
        self.oggetti = {o.oggetto: o.ritiro for o in ordini}
        self.porte = {arco(a, b): porta for a, b, porta in mappa.ARCHI if porta}
        self.porte_aperte = set()
        self.ostacoli = {arco(a, b) for a, b in ostacoli}   # il robot non li conosce
        self.bloccati_noti = set()                          # ostacoli già scoperti
        self.grafo = costruisci_grafo(mappa.NODI, mappa.ARCHI)
        self.metri = 0.0
        self.verboso = verboso
        self.log = []

    # --- utilità -------------------------------------------------------------
    def registra(self, messaggio):
        riga = f"[t{self.tick:04d}] {messaggio}"
        self.log.append(riga)
        if self.verboso:
            print(riga)

    def _consuma(self, quanto):
        self.batteria = max(0.0, self.batteria - quanto)

    def prossimo_passo(self, destinazione):
        """Prossimo nodo sul percorso più breve che evita gli ostacoli noti."""
        if self.posizione == destinazione:
            return None
        p = percorso(mappa.NODI, mappa.ARCHI, self.posizione, destinazione,
                     bloccati=[tuple(e) for e in self.bloccati_noti])
        return p[1] if p else None

    def _arco_davanti(self, destinazione):
        nxt = self.prossimo_passo(destinazione)
        return (nxt, arco(self.posizione, nxt)) if nxt else (None, None)

    def _sposta(self, nodo):
        if self.batteria <= 0:
            self.registra("batteria scarica: impossibile muoversi")
            return False
        e = arco(self.posizione, nodo)
        metri = distanza(mappa.NODI[self.posizione], mappa.NODI[nodo])
        self._consuma(metri * CONSUMO_PER_METRO)
        self.metri += metri
        self.registra(f"{self.posizione} -> {nodo} ({self.batteria:.0f}%)")
        self.posizione = nodo
        self.in_carica = False
        self.porte_aperte.discard(e)   # le porte si richiudono dopo il passaggio
        return True

    # --- percezione --------------------------------------------------------
    def costo_ritorno(self):
        """% stimata per raggiungere il caricabatterie con gli ostacoli noti."""
        p = percorso(mappa.NODI, mappa.ARCHI, self.posizione, "caricabatterie",
                     bloccati=[tuple(e) for e in self.bloccati_noti])
        porte = sum(arco(a, b) in self.porte for a, b in zip(p, p[1:])) if p else 0
        return (lunghezza(mappa.NODI, p) * CONSUMO_PER_METRO + porte * CONSUMO_PORTA) if p else 100.0

    def batteria_ok(self):
        """Più del 20% di riserva oltre a quanto serve per tornare a ricaricare."""
        return self.batteria - self.costo_ritorno() > 20 and not self.in_carica

    def al_caricabatterie(self):
        return self.posizione == "caricabatterie"

    def lontano_dalle_scale(self):
        return distanza(mappa.NODI[self.posizione], mappa.SCALE) >= mappa.DISTANZA_SICUREZZA_SCALE

    def strada_libera(self, destinazione):
        nxt, e = self._arco_davanti(destinazione)
        if nxt is None:
            return self.posizione == destinazione
        return e not in self.ostacoli and (e not in self.porte or e in self.porte_aperte)

    def porta_chiusa(self, destinazione):
        _, e = self._arco_davanti(destinazione)
        return e is not None and e in self.porte and e not in self.porte_aperte

    def porta_a_spinta(self, destinazione):
        _, e = self._arco_davanti(destinazione)
        return self.porte.get(e) == mappa.SPINTA

    # --- azioni ------------------------------------------------------------
    def apri_porta(self, destinazione, modo):
        """modo = SPINTA o CHIAVE; riesce solo se corrisponde al tipo di porta."""
        nxt, e = self._arco_davanti(destinazione)
        if e not in self.porte or self.porte[e] != modo:
            return False
        self.porte_aperte.add(e)
        self._consuma(CONSUMO_PORTA)
        azione = "spinge" if modo == mappa.SPINTA else "apre con la chiave"
        self.registra(f"{azione} la porta {self.posizione}|{nxt}")
        return True

    def avanza(self, destinazione):
        nxt = self.prossimo_passo(destinazione)
        if nxt is None or not self.strada_libera(destinazione):
            return False
        return self._sposta(nxt)

    def torna_indietro(self, destinazione):
        """L'arco davanti è bloccato: lo memorizza e ripianifica. False se non c'è alternativa."""
        nxt, e = self._arco_davanti(destinazione)
        if e is None:
            return False
        self.bloccati_noti.add(e)
        self.registra(f"ostacolo su {self.posizione}|{nxt}: ripianifico")
        return self.prossimo_passo(destinazione) is not None

    def allontanati_dalle_scale(self, destinazione):
        """Si sposta verso un nodo vicino più lontano dalle scale, preferendo quello verso la meta."""
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
        """Passo automatico (per andare in carica): apre porte e aggira ostacoli da solo."""
        if self.posizione == destinazione:
            return True
        if self.porta_chiusa(destinazione):
            return self.apri_porta(destinazione, self.porte[self._arco_davanti(destinazione)[1]])
        if not self.strada_libera(destinazione):
            return self.torna_indietro(destinazione)
        return self.avanza(destinazione)

    def ricarica(self):
        """True quando la batteria è al 100%."""
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
        if self.coda and self.coda[0].arrivo <= self.tick:
            self.ordine = self.coda.pop(0)
            o = self.ordine
            self.registra(f"nuovo ordine {o.id}: {o.oggetto} da {o.ritiro} a {o.consegna}")
            return True
        return False

    def prendi(self):
        o = self.ordine
        if o is None or self.posizione != o.ritiro or self.oggetti.get(o.oggetto) != self.posizione:
            return False
        del self.oggetti[o.oggetto]
        self.oggetto_in_mano = o.oggetto
        self.registra(f"prende {o.oggetto} in {self.posizione}")
        return True

    def posa(self):
        o = self.ordine
        if o is None or self.oggetto_in_mano != o.oggetto or self.posizione != o.consegna:
            return False
        self.oggetti[o.oggetto] = self.posizione
        self.oggetto_in_mano = None
        self.registra(f"posa {o.oggetto} in {self.posizione}")
        return True

    def chiudi_ordine(self):
        if self.ordine is None or self.oggetti.get(self.ordine.oggetto) != self.ordine.consegna:
            return False
        self.completati.append(self.ordine)
        self.registra(f"ordine {self.ordine.id} chiuso")
        self.ordine = None
        return True

    def finito(self):
        return not self.coda and self.ordine is None
