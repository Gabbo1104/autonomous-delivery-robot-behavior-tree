"""Mappa del piano (dalla piantina del laboratorio): griglia con muri, nodi e porte.

La griglia è 71 colonne x 28 righe: una colonna = 1 m, una riga = 2 m (i
caratteri del terminale sono alti il doppio che larghi). I muri non si
attraversano; si passa da una stanza all'altra solo dalle porte.

Il robot ragiona sul grafo dei nodi (NODI, ARCHI); la griglia serve a disegnare
la mappa e a far muovere il robot casella per casella lungo ogni arco.
"""
from collections import deque

LARGHEZZA, ALTEZZA = 71, 28
MURO, SCALINI, LIBERO = "#", "=", " "

# Nodo -> (colonna, riga) sulla griglia
CELLE = {
    # Corridoio sud (da ovest a est)
    "c_sud_ovest": (5, 22), "c_scale": (15, 22), "c_101": (25, 22), "c_103": (34, 22),
    "c_105": (42, 22), "c_107": (50, 22), "c_109": (59, 22), "c_111": (66, 22),
    # Corridoio est (da sud a nord)
    "c_113": (59, 17), "c_115": (59, 12), "c_117": (59, 8), "c_nord_est": (59, 6),
    # Corridoio nord (da est a ovest)
    "c_119": (53, 6), "c_121": (45, 6), "c_123": (37, 6), "c_125": (29, 6),
    "c_127": (21, 6), "c_129": (13, 6), "c_nord_ovest": (5, 6),
    # Corridoio ovest
    "caricabatterie": (5, 14),
    # Stanze
    "r131": (5, 3), "r129": (13, 3), "r127": (21, 3), "r125": (29, 3),
    "r123": (37, 3), "r121": (45, 3), "r119": (53, 3),
    "r117": (66, 8), "r115": (66, 12), "r113": (66, 17),
    "main_office": (5, 25), "r101": (25, 25), "r103": (34, 25), "r105": (42, 25),
    "r107": (50, 25), "r109": (58, 25), "r111": (66, 25),
    "lab_d": (22, 11), "lab_c": (45, 11), "lab_a": (26, 17), "lab_b": (45, 17),
}

# Coordinate in metri per distanze e percorsi: (colonna, riga * 2)
NODI = {n: (c, r * 2) for n, (c, r) in CELLE.items()}

# Le scale (aperte sul corridoio) non sono attraversabili: il robot deve starne lontano.
SCALE = (15, 50)
DISTANZA_SICUREZZA_SCALE = 7.0

# (nodo, nodo, verso): verso è None per un passaggio senza porta, altrimenti il
# nodo verso cui la porta si apre. Andando in quella direzione il robot spinge;
# dal lato opposto dovrebbe tirare, e non potendo usa la chiave.
ARCHI = [
    # Anello del corridoio
    ("c_sud_ovest", "c_scale", None), ("c_scale", "c_101", None),
    ("c_101", "c_103", None), ("c_103", "c_105", None), ("c_105", "c_107", None),
    ("c_107", "c_109", None), ("c_109", "c_111", None),
    ("c_109", "c_113", None), ("c_113", "c_115", None), ("c_115", "c_117", None),
    ("c_117", "c_nord_est", None),
    ("c_nord_est", "c_119", None), ("c_119", "c_121", None), ("c_121", "c_123", None),
    ("c_123", "c_125", None), ("c_125", "c_127", None), ("c_127", "c_129", None),
    ("c_129", "c_nord_ovest", None),
    ("c_nord_ovest", "caricabatterie", None), ("caricabatterie", "c_sud_ovest", None),
    # Stanze: tutte le porte si aprono verso l'interno
    ("c_sud_ovest", "main_office", "main_office"), ("c_101", "r101", "r101"),
    ("c_103", "r103", "r103"), ("c_105", "r105", "r105"), ("c_107", "r107", "r107"),
    ("c_109", "r109", "r109"), ("c_111", "r111", "r111"),
    ("c_113", "r113", "r113"), ("c_115", "r115", "r115"), ("c_117", "r117", "r117"),
    ("c_119", "r119", "r119"), ("c_121", "r121", "r121"), ("c_123", "r123", "r123"),
    ("c_125", "r125", "r125"), ("c_127", "r127", "r127"), ("c_129", "r129", "r129"),
    ("c_nord_ovest", "r131", "r131"),
    # Laboratori (verso come nella piantina)
    ("c_129", "lab_d", "c_129"), ("c_123", "lab_c", "lab_c"),
    ("c_101", "lab_a", "c_101"), ("c_103", "lab_b", "lab_b"), ("c_107", "lab_b", "c_107"),
    ("lab_a", "lab_d", "lab_a"), ("lab_b", "lab_c", "lab_b"),
    ("lab_a", "lab_b", None),          # passaggio aperto
]

# Casella della porta di ogni arco con porta
CELLE_PORTE = {
    frozenset(("c_sud_ovest", "main_office")): (5, 23),
    frozenset(("c_101", "r101")): (25, 23), frozenset(("c_103", "r103")): (34, 23),
    frozenset(("c_105", "r105")): (42, 23), frozenset(("c_107", "r107")): (50, 23),
    frozenset(("c_109", "r109")): (58, 23), frozenset(("c_111", "r111")): (66, 23),
    frozenset(("c_113", "r113")): (62, 17), frozenset(("c_115", "r115")): (62, 12),
    frozenset(("c_117", "r117")): (62, 8),
    frozenset(("c_119", "r119")): (53, 5), frozenset(("c_121", "r121")): (45, 5),
    frozenset(("c_123", "r123")): (37, 5), frozenset(("c_125", "r125")): (29, 5),
    frozenset(("c_127", "r127")): (21, 5), frozenset(("c_129", "r129")): (13, 5),
    frozenset(("c_nord_ovest", "r131")): (5, 5),
    frozenset(("c_129", "lab_d")): (16, 8), frozenset(("c_123", "lab_c")): (38, 8),
    frozenset(("c_101", "lab_a")): (29, 20), frozenset(("c_103", "lab_b")): (36, 20),
    frozenset(("c_107", "lab_b")): (50, 20),
    frozenset(("lab_a", "lab_d")): (27, 14), frozenset(("lab_b", "lab_c")): (50, 14),
}

PARTENZA = "c_103"

# Nomi scritti dentro le stanze nella vista a terminale: nome -> (colonna, riga)
ETICHETTE = {
    "r131": (3, 1), "r129": (11, 1), "r127": (19, 1), "r125": (27, 1), "r123": (35, 1),
    "r121": (43, 1), "r119": (51, 1), "r117": (64, 7), "r115": (64, 11), "r113": (64, 16),
    "office": (2, 26), "scale": (13, 26), "r101": (23, 26), "r103": (32, 26),
    "r105": (40, 26), "r107": (48, 26), "r109": (56, 26), "r111": (64, 26),
    "lab D": (12, 9), "lab C": (35, 9), "lab A": (12, 19), "lab B": (35, 19),
}


def _costruisci_griglia():
    g = [[LIBERO] * LARGHEZZA for _ in range(ALTEZZA)]

    def orizzontale(r, c1, c2):
        for c in range(c1, c2 + 1):
            g[r][c] = MURO

    def verticale(c, r1, r2):
        for r in range(r1, r2 + 1):
            g[r][c] = MURO

    # Perimetro
    orizzontale(0, 0, 70), orizzontale(27, 0, 70), verticale(0, 0, 27), verticale(70, 0, 27)
    # Stanze nord
    orizzontale(5, 0, 57)
    for c in (9, 17, 25, 33, 41, 49, 57):
        verticale(c, 0, 5)
    # Blocco dei laboratori: D | C sopra, A | B sotto (varco aperto tra A e B)
    orizzontale(8, 10, 56), orizzontale(14, 10, 56), orizzontale(20, 10, 56)
    verticale(10, 8, 20), verticale(56, 8, 20), verticale(33, 8, 14), verticale(33, 17, 20)
    # Stanze est
    verticale(62, 6, 20)
    for r in (6, 10, 15, 20):
        orizzontale(r, 62, 70)
    # Stanze sud; le scale sono aperte sul corridoio
    orizzontale(23, 0, 10), orizzontale(23, 20, 70)
    for c in (10, 20, 30, 38, 46, 54, 62):
        verticale(c, 23, 27)
    for r in range(23, 27):
        for c in range(11, 20):
            g[r][c] = SCALINI
    for c, r in CELLE_PORTE.values():
        g[r][c] = MURO   # una porta chiusa è un muro finché non si apre
    return g


GRIGLIA = _costruisci_griglia()
VICINI_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def percorso_griglia(da, a, aperte=()):
    """Caselle da `da` ad `a` (colonna, riga) muovendosi in 8 direzioni senza tagliare
    gli angoli dei muri; `aperte` sono le caselle porta attraversabili. None se bloccato."""
    aperte = set(aperte)

    def libera(c, r):
        return 0 <= c < LARGHEZZA and 0 <= r < ALTEZZA and (GRIGLIA[r][c] == LIBERO or (c, r) in aperte)

    precedente = {da: None}
    coda = deque([da])
    while coda:
        c, r = coda.popleft()
        if (c, r) == a:
            celle = []
            while (c, r) != da:
                celle.append((c, r))
                c, r = precedente[(c, r)]
            return [da] + celle[::-1]
        for dc, dr in VICINI_8:
            n = (c + dc, r + dr)
            if n in precedente or not libera(*n):
                continue
            if dc and dr and not (libera(c + dc, r) and libera(c, r + dr)):
                continue  # niente diagonali attraverso lo spigolo di un muro
            precedente[n] = (c, r)
            coda.append(n)
    return None


def celle_arco(a, b):
    """Caselle percorse sulla griglia per andare dal nodo a al nodo b."""
    porta = CELLE_PORTE.get(frozenset((a, b)))
    return percorso_griglia(CELLE[a], CELLE[b], [porta] if porta else ())
