"""End-to-end tests of the behaviour tree running on the simulated world.

Each test builds a Mondo with a controlled scenario (start node, orders,
obstacles, battery), runs main.simula() and then checks the final state and/or
the event log (Mondo.log, Italian messages). Log assertions therefore depend
on the exact wording used in mondo.py: update both together.
"""
from robot_consegne import mappa
from robot_consegne.main import simula
from robot_consegne.mondo import Mondo, Ordine, arco, genera_ordini, genera_ostacoli


def test_consegna_semplice():
    """Basic delivery between two neighbouring rooms: order closed, item at destination, hands empty."""
    m = Mondo([Ordine(1, "pacco", "r105", "r107")])
    simula(m, max_tick=200)
    assert m.finito() and [o.id for o in m.completati] == [1]
    assert m.oggetti["pacco"] == "r107" and m.oggetto_in_mano is None


def test_spinge_entrando_e_usa_la_chiave_dove_dovrebbe_tirare():
    """Room doors swing inwards: the robot pushes to enter and must use the key to leave."""
    m = Mondo([Ordine(1, "documenti", "main_office", "r101")])
    simula(m, max_tick=400)
    assert m.finito()
    log = "\n".join(m.log)
    # the office door swings inwards: pushed when entering; when leaving it would need pulling, so key
    assert "pushes the door c_south_west|main_office" in log
    assert "uses the key on the door main_office|c_south_west" in log
    assert "pushes the door c_101|r101" in log


def test_porta_del_lab_d_si_apre_verso_il_corridoio():
    """Lab D's door swings towards the corridor: key from outside, push from inside (calls Mondo directly)."""
    m = Mondo(posizione="c_129")
    assert m.porta_chiusa("lab_d") and not m.porta_a_spinta("lab_d")
    assert not m.spingi("lab_d")           # from outside it would need pulling
    assert m.usa_chiave("lab_d") and m.avanza("lab_d")
    assert m.porta_chiusa("c_129") and m.porta_a_spinta("c_129") and m.spingi("c_129")


def test_batteria_bassa_va_in_carica_fino_al_100():
    """Starting at 15% the robot charges to 100% before even taking the order."""
    m = Mondo([Ordine(1, "pacco", "r103", "r105")], batteria=15)
    simula(m, max_tick=400)
    log = "\n".join(m.log)
    assert "charging complete (100%)" in log
    # charging happens before the order is even taken
    assert log.index("charging complete") < log.index("new order 1")
    assert m.finito()


def test_ostacolo_scoperto_e_aggirato():
    # from c_103 to main_office the direct route goes through c_101|c_stairs
    """A hidden obstacle on the planned route is discovered, remembered and never crossed."""
    m = Mondo([Ordine(1, "cavo", "c_103", "main_office")], ostacoli=[("c_101", "c_stairs")])
    simula(m, max_tick=600)
    assert m.finito()
    assert arco("c_101", "c_stairs") in m.bloccati_noti
    assert not any("c_101 -> c_stairs" in r for r in m.log)


def test_si_allontana_dalle_scale():
    """Starting next to the stairs, the 'allontanati' action moves the robot away."""
    m = Mondo([Ordine(1, "libro", "c_103", "r131")], posizione="c_stairs")
    simula(m, max_tick=600)
    assert m.finito()
    assert "moving away" in "\n".join(m.log)


def test_attende_ordini_che_arrivano_dopo():
    """Orders arriving later are waited for ('attendi ordine') and served in order."""
    m = Mondo([Ordine(1, "caffè", "r101", "r103", arrivo=0), Ordine(2, "cavo", "r109", "r111", arrivo=150)])
    simula(m, max_tick=1000)
    assert [o.id for o in m.completati] == [1, 2]
    assert m.tick > 150


def test_simulazione_completa_con_ostacoli_e_ricariche():
    """Long random run (12 orders, obstacles, 60% start): everything delivered, at least one recharge."""
    m = Mondo(genera_ordini(12, seed=3), genera_ostacoli(3, seed=3), batteria=60)
    simula(m, max_tick=8000)
    assert m.finito() and len(m.completati) == 12
    assert m.batteria > 0
    assert any("charging complete" in r for r in m.log)
    # no item lost: every one lies at its delivery node
    for o in m.completati:
        assert m.oggetti[o.oggetto] == o.consegna


def test_mai_sulle_scale_e_porte_richiuse():
    """After a random run, any door still open must be next to the robot (doors close behind it) and the robot ends on a valid node."""
    m = Mondo(genera_ordini(5, seed=9), batteria=100)
    simula(m, max_tick=4000)
    assert m.finito()
    assert not m.porte_aperte or all(m.posizione in e for e in m.porte_aperte)
    assert all(n in mappa.NODI for n in [m.posizione])


def test_ostacoli_generati_lasciano_tutto_raggiungibile():
    """genera_ostacoli always places the requested number of obstacles without disconnecting the map."""
    from robot_consegne.percorso import percorso
    for seed in range(30):
        ostacoli = genera_ostacoli(4, seed)
        assert len(ostacoli) == 4
        for n in mappa.NODI:
            assert percorso(mappa.NODI, mappa.ARCHI, mappa.PARTENZA, n, bloccati=ostacoli), (seed, n)


def test_non_resta_mai_senza_batteria():
    """With a 25% start and 0-5 obstacles the robot never runs flat (validates the battery reserve rule)."""
    for seed in range(40):
        m = Mondo(genera_ordini(10, seed), genera_ostacoli(seed % 6, seed), batteria=25)
        simula(m, max_tick=8000)
        assert m.finito() and m.batteria > 0, seed


def test_arriva_al_caricabatterie_a_zero_e_ricarica():
    """A robot standing on the charger with 0% can still recharge and finish (the loop must not stop)."""
    m = Mondo([Ordine(1, "cavo", "r101", "r103")], batteria=0, posizione="charger")
    simula(m, max_tick=500)
    assert m.finito()


def test_partenza_e_ordini_casuali_su_tutta_la_mappa():
    """Random start/battery/orders: spread over the whole map, battery in 1..100, pickup != delivery, reproducible by seed."""
    from robot_consegne.mondo import genera_partenza
    partenze = {genera_partenza(s)[0] for s in range(300)}
    batterie = [genera_partenza(s)[1] for s in range(300)]
    luoghi = {n for o in genera_ordini(300, seed=1) for n in (o.ritiro, o.consegna)}
    assert len(partenze) > 30 and partenze <= set(mappa.NODI)
    assert 1 <= min(batterie) and max(batterie) <= 100
    assert any(n.startswith("c_") for n in luoghi) and luoghi <= set(mappa.NODI)
    assert all(o.ritiro != o.consegna for o in genera_ordini(300, seed=1))
    assert genera_partenza(5) == genera_partenza(5)


def test_scenari_casuali_con_batteria_sufficiente_vanno_a_buon_fine():
    """Random start nodes with 60% battery always complete the delivery."""
    from robot_consegne.mondo import genera_partenza
    for seed in range(60):
        pos, _ = genera_partenza(seed)
        m = Mondo(genera_ordini(1, seed), genera_ostacoli(2, seed), batteria=60, posizione=pos)
        simula(m, max_tick=3000)
        assert m.finito(), seed
