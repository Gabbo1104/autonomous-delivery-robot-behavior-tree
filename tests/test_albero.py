"""End-to-end tests of the behaviour tree running on the simulated world.

Each test builds a Mondo with a controlled scenario (start node, orders,
obstacles, battery), runs main.simula() and then checks the final state and/or
the event log (Mondo.log, English messages). Log assertions therefore depend
on the exact wording used in mondo.py: update both together.

The charger is never fixed: as when a user starts a simulation, it is drawn
with genera_partenza(seed), and every test runs over several seeds (SEMI), so
over several random chargers.
"""
import argparse

import pytest

from robot_consegne import mappa
from robot_consegne.main import crea_scenario, simula
from robot_consegne.mondo import Mondo, Ordine, arco, genera_ordini, genera_ostacoli, genera_partenza

SEMI = range(20)   # seeds used by the tests that run on a random charger


def caricatore_casuale(seed):
    """Charger node drawn exactly as in a simulation started by the user."""
    return genera_partenza(seed)[1]


@pytest.mark.parametrize("seed", SEMI)
def test_consegna_semplice(seed):
    """Basic delivery between two neighbouring rooms: order closed, item at destination, hands empty."""
    m = Mondo([Ordine(1, "pacco", "r105", "r107")], caricatore=caricatore_casuale(seed))
    simula(m, max_tick=200)
    assert m.finito() and [o.id for o in m.completati] == [1]
    assert m.oggetti["pacco"] == "r107" and m.oggetto_in_mano is None


@pytest.mark.parametrize("seed", SEMI)
def test_spinge_entrando_e_usa_la_chiave_dove_dovrebbe_tirare(seed):
    """Room doors swing inwards: the robot pushes to enter and must use the key to leave."""
    m = Mondo([Ordine(1, "documenti", "main_office", "r101")], caricatore=caricatore_casuale(seed))
    simula(m, max_tick=400)
    assert m.finito()
    log = "\n".join(m.log)
    # the office door swings inwards: pushed when entering; when leaving it would need pulling, so key
    assert "pushes the door c_south_west|main_office" in log
    assert "uses the key on the door main_office|c_south_west" in log
    assert "pushes the door c_101|r101" in log


@pytest.mark.parametrize("seed", SEMI)
def test_porta_del_lab_d_si_apre_verso_il_corridoio(seed):
    """Lab D's door swings towards the corridor: key from outside, push from inside (calls Mondo directly)."""
    m = Mondo(posizione="c_129", caricatore=caricatore_casuale(seed))
    assert m.porta_chiusa("lab_d") and not m.porta_a_spinta("lab_d")
    assert not m.spingi("lab_d")           # from outside it would need pulling
    assert m.usa_chiave("lab_d") and m.avanza("lab_d")
    assert m.porta_chiusa("c_129") and m.porta_a_spinta("c_129") and m.spingi("c_129")


@pytest.mark.parametrize("seed", SEMI)
def test_batteria_bassa_va_a_caricarsi_al_caricatore_fino_al_100(seed):
    """Starting at 15% the robot plans a recharge, charges on the charger node to 100%, then takes the order."""
    caricatore = caricatore_casuale(seed)
    m = Mondo([Ordine(1, "pacco", "r103", "r105")], batteria=15, caricatore=caricatore)
    posizioni = []   # node where the robot is when charging starts
    m.registra = lambda msg, registra=m.registra: (
        posizioni.append(m.posizione) if msg.startswith("charging started") else None, registra(msg))
    simula(m, max_tick=400)
    log = "\n".join(m.log)
    assert m.finito()
    assert posizioni and set(posizioni) == {caricatore}
    assert "charging complete (100%)" in log
    # charging happens before the order is even taken
    assert log.index("charging complete") < log.index("new order 1")


@pytest.mark.parametrize("seed", SEMI)
def test_ostacolo_scoperto_e_aggirato(seed):
    """A hidden obstacle on the planned route is discovered, remembered and never crossed."""
    # from c_103 to main_office the direct route goes through c_101|c_stairs
    m = Mondo([Ordine(1, "cavo", "c_103", "main_office")], ostacoli=[("c_101", "c_stairs")],
              caricatore=caricatore_casuale(seed))
    simula(m, max_tick=600)
    assert m.finito()
    assert arco("c_101", "c_stairs") in m.bloccati_noti
    assert not any("c_101 -> c_stairs" in r for r in m.log)


@pytest.mark.parametrize("seed", SEMI)
def test_si_allontana_dalle_scale(seed):
    """Starting next to the stairs, the 'move away' action moves the robot away."""
    m = Mondo([Ordine(1, "libro", "c_103", "r131")], posizione="c_stairs", caricatore=caricatore_casuale(seed))
    simula(m, max_tick=600)
    assert m.finito()
    assert "moving away" in "\n".join(m.log)


@pytest.mark.parametrize("seed", SEMI)
def test_ostacolo_davanti_vicino_alle_scale(seed):
    """Regression: an obstacle right after the stairs is remembered instead of bouncing back and forth forever."""
    m = Mondo([Ordine(1, "libro", "c_south_west", "lab_b")], ostacoli=[("c_stairs", "c_101")],
              posizione="c_west", caricatore=caricatore_casuale(seed))
    simula(m, max_tick=300)
    assert m.finito() and m.tick < 50
    assert arco("c_stairs", "c_101") in m.bloccati_noti


@pytest.mark.parametrize("seed", SEMI)
def test_attende_ordini_che_arrivano_dopo(seed):
    """Orders arriving later are waited for ('wait for an order') and served in order."""
    m = Mondo([Ordine(1, "caffè", "r101", "r103", arrivo=0), Ordine(2, "cavo", "r109", "r111", arrivo=150)],
              caricatore=caricatore_casuale(seed))
    simula(m, max_tick=1000)
    assert [o.id for o in m.completati] == [1, 2]
    assert m.tick > 150


@pytest.mark.parametrize("seed", range(5))
def test_simulazione_completa_con_ostacoli_e_ricariche(seed):
    """Long random run (12 orders, obstacles, 60% start): everything delivered, at least one recharge."""
    m = Mondo(genera_ordini(12, seed), genera_ostacoli(3, seed), batteria=60, caricatore=caricatore_casuale(seed))
    simula(m, max_tick=8000)
    assert m.finito() and len(m.completati) == 12
    assert m.batteria > 0
    assert any("charging complete" in r for r in m.log)
    # no item lost: every one lies at its delivery node
    for o in m.completati:
        assert m.oggetti[o.oggetto] == o.consegna


@pytest.mark.parametrize("seed", SEMI)
def test_mai_sulle_scale_e_porte_richiuse(seed):
    """After a random run, any door still open must be next to the robot (doors close behind it) and the robot ends on a valid node."""
    m = Mondo(genera_ordini(5, seed), caricatore=caricatore_casuale(seed))
    simula(m, max_tick=4000)
    assert m.finito()
    assert not m.porte_aperte or all(m.posizione in e for e in m.porte_aperte)
    assert m.posizione in mappa.NODI_SICURI


def test_ostacoli_generati_lasciano_tutto_raggiungibile():
    """genera_ostacoli always places the requested number of obstacles without disconnecting the map."""
    from robot_consegne.percorso import percorso
    for seed in range(30):
        ostacoli = genera_ostacoli(4, seed)
        assert len(ostacoli) == 4
        for n in mappa.NODI:
            assert percorso(mappa.NODI, mappa.ARCHI, mappa.PARTENZA, n, bloccati=ostacoli), (seed, n)


def test_non_resta_mai_senza_batteria():
    """With a 25% start, random chargers and 0-5 obstacles the robot never runs flat (validates the energy plan)."""
    for seed in range(40):
        m = Mondo(genera_ordini(10, seed), genera_ostacoli(seed % 6, seed), batteria=25,
                  caricatore=caricatore_casuale(seed))
        simula(m, max_tick=8000)
        assert m.finito() and m.batteria > 0, seed


@pytest.mark.parametrize("seed", SEMI)
def test_arriva_al_caricatore_a_zero_e_ricarica(seed):
    """A robot standing on the charger with 0% can still recharge and finish (the loop must not stop)."""
    caricatore = caricatore_casuale(seed)
    m = Mondo([Ordine(1, "cavo", "r101", "r103")], batteria=0, posizione=caricatore, caricatore=caricatore)
    simula(m, max_tick=500)
    assert m.finito()


def test_partenza_e_ordini_casuali_su_tutta_la_mappa():
    """Random start/charger/orders: spread over the safe nodes, pickup != delivery, reproducible by seed."""
    scenari = [genera_partenza(s) for s in range(300)]
    partenze = {p for p, _ in scenari}
    caricatori = {c for _, c in scenari}
    luoghi = {n for o in genera_ordini(300, seed=1) for n in (o.ritiro, o.consegna)}
    assert len(partenze) > 30 and partenze <= set(mappa.NODI_SICURI)
    assert len(caricatori) > 30 and caricatori <= set(mappa.NODI_SICURI)
    assert any(n.startswith("c_") for n in luoghi) and luoghi <= set(mappa.NODI_SICURI)
    assert "c_stairs" not in partenze | caricatori | luoghi
    assert all(o.ritiro != o.consegna for o in genera_ordini(300, seed=1))
    assert genera_partenza(5) == genera_partenza(5)


def test_scenari_casuali_con_batteria_sufficiente_vanno_a_buon_fine():
    """Random start and charger with 60% battery always complete the delivery."""
    for seed in range(60):
        pos, caricatore = genera_partenza(seed)
        m = Mondo(genera_ordini(1, seed), genera_ostacoli(2, seed), batteria=60, posizione=pos,
                  caricatore=caricatore)
        simula(m, max_tick=3000)
        assert m.finito(), seed


def test_piano_con_ricarica_tra_ritiro_e_consegna():
    """When the plan puts the charger between pickup and delivery, the robot picks up, charges, then delivers.

    Full random runs built as the command line does (8 orders, 100% start):
    after a few deliveries the charge is lower and some orders need a recharge
    while the item is already in hand (plan "charger -> delivery"). The plan is
    recomputed every tick, so only the plan made after the pickup is checked.
    There must be enough such orders for the check to mean something.
    """
    casi = 0
    for seed in range(60):
        args = argparse.Namespace(seed=seed, ordini=8, ostacoli=seed % 5, batteria=100.0)
        m, intestazione = crea_scenario(args)
        con_ricarica = set()   # items carried while the plan said "charge, then deliver"

        def dopo_tick(_albero, m=m, con_ricarica=con_ricarica):
            o = m.ordine
            if o and m.oggetto_in_mano == o.oggetto and m.calcola_piano() == [m.caricatore, o.consegna] \
                    and m.caricatore != o.consegna:
                con_ricarica.add(o.oggetto)

        simula(m, max_tick=8000, dopo_tick=dopo_tick)
        assert m.finito(), intestazione
        for oggetto in con_ricarica:
            presa = next(i for i, r in enumerate(m.log) if f"picks up {oggetto} " in r)
            posa = next(i for i, r in enumerate(m.log) if f"puts down {oggetto} " in r)
            assert any("charging started" in r for r in m.log[presa:posa]), (intestazione, oggetto)
        casi += len(con_ricarica)
    assert casi >= 5


@pytest.mark.parametrize("seed", SEMI)
def test_piano_senza_ricarica_se_la_carica_basta(seed):
    """With a full battery one order never needs a recharge, wherever the charger is (calls Mondo directly)."""
    partenza, caricatore = genera_partenza(seed)
    ordine = genera_ordini(1, seed)[0]
    m = Mondo([ordine], posizione=partenza, caricatore=caricatore)
    m.attendi_ordine()
    assert m.calcola_piano() == [ordine.ritiro, ordine.consegna]
    assert m.batteria_ok()


def test_scenari_completamente_casuali_vanno_a_buon_fine():
    """Scenarios built exactly as the command line does (random start, charger, orders, obstacles; 100%): all delivered."""
    for seed in range(150):
        args = argparse.Namespace(seed=seed, ordini=1 + seed % 3, ostacoli=seed % 5, batteria=100.0)
        m, intestazione = crea_scenario(args)
        simula(m, max_tick=5000)
        assert m.finito() and len(m.completati) == args.ordini, intestazione


def test_partenza_caricatore_e_ordini_sono_indipendenti():
    """Regression: with the same seed, the pickup was always the start node and the delivery the charger."""
    uguali_a, uguali_b = 0, 0
    for seed in range(300):
        partenza, caricatore = genera_partenza(seed)
        ordine = genera_ordini(1, seed)[0]
        uguali_a += ordine.ritiro == partenza
        uguali_b += ordine.consegna == caricatore
    # with ~50 safe nodes a coincidence is rare (about 2% each)
    assert uguali_a < 20 and uguali_b < 20
