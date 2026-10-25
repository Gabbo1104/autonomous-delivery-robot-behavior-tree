import mappa
from main import simula
from mondo import Mondo, Ordine, arco, genera_ordini, genera_ostacoli


def test_consegna_semplice():
    m = Mondo([Ordine(1, "pacco", "r105", "r107")])
    simula(m, max_tick=200)
    assert m.finito() and [o.id for o in m.completati] == [1]
    assert m.oggetti["pacco"] == "r107" and m.oggetto_in_mano is None


def test_apre_porte_a_spinta_e_a_chiave():
    m = Mondo([Ordine(1, "documenti", "main_office", "lab_c")])
    simula(m, max_tick=400)
    assert m.finito()
    log = "\n".join(m.log)
    assert "apre con la chiave la porta c_sud_ovest|main_office" in log
    assert "spinge la porta" in log


def test_batteria_bassa_va_in_carica_fino_al_100():
    m = Mondo([Ordine(1, "pacco", "r103", "r105")], batteria=15)
    simula(m, max_tick=400)
    log = "\n".join(m.log)
    assert "ricarica completata (100%)" in log
    # la ricarica avviene prima di prendere l'ordine
    assert log.index("ricarica completata") < log.index("nuovo ordine 1")
    assert m.finito()


def test_ostacolo_scoperto_e_aggirato():
    # da c_103 a main_office il percorso diretto passa per c_101|c_scale
    m = Mondo([Ordine(1, "cavo", "c_103", "main_office")], ostacoli=[("c_101", "c_scale")])
    simula(m, max_tick=600)
    assert m.finito()
    assert arco("c_101", "c_scale") in m.bloccati_noti
    assert not any("c_101 -> c_scale" in r for r in m.log)


def test_si_allontana_dalle_scale():
    m = Mondo([Ordine(1, "libro", "c_103", "r131")], posizione="c_scale")
    simula(m, max_tick=600)
    assert m.finito()
    assert "mi allontano" in "\n".join(m.log)


def test_attende_ordini_che_arrivano_dopo():
    m = Mondo([Ordine(1, "caffè", "r101", "r103", arrivo=0), Ordine(2, "cavo", "r109", "r111", arrivo=150)])
    simula(m, max_tick=1000)
    assert [o.id for o in m.completati] == [1, 2]
    assert m.tick > 150


def test_simulazione_completa_con_ostacoli_e_ricariche():
    m = Mondo(genera_ordini(12, seed=3), genera_ostacoli(3, seed=3), batteria=60)
    simula(m, max_tick=8000)
    assert m.finito() and len(m.completati) == 12
    assert m.batteria > 0
    assert any("ricarica completata" in r for r in m.log)
    # nessun oggetto perso: tutti nelle stanze di consegna
    for o in m.completati:
        assert m.oggetti[o.oggetto] == o.consegna


def test_mai_sulle_scale_e_porte_richiuse():
    m = Mondo(genera_ordini(5, seed=9), batteria=100)
    simula(m, max_tick=4000)
    assert m.finito()
    assert not m.porte_aperte or all(m.posizione in e for e in m.porte_aperte)
    assert all(n in mappa.NODI for n in [m.posizione])


def test_ostacoli_generati_lasciano_tutto_raggiungibile():
    from percorso import percorso
    for seed in range(30):
        ostacoli = genera_ostacoli(4, seed)
        assert len(ostacoli) == 4
        for n in mappa.NODI:
            assert percorso(mappa.NODI, mappa.ARCHI, mappa.PARTENZA, n, bloccati=ostacoli), (seed, n)


def test_non_resta_mai_senza_batteria():
    for seed in range(40):
        m = Mondo(genera_ordini(10, seed), genera_ostacoli(seed % 6, seed), batteria=25)
        simula(m, max_tick=8000)
        assert m.finito() and m.batteria > 0, seed
