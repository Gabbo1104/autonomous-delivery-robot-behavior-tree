"""Mappa del piano (dalla piantina del laboratorio): nodi, collegamenti e porte.

Le coordinate sono in metri circa (pixel della piantina / 10), origine in alto a
sinistra. Il robot si muove da nodo a nodo lungo gli archi.
"""

# Nodo -> (x, y)
NODI = {
    # Corridoio sud (da ovest a est)
    "c_sud_ovest": (13, 43.5),   # davanti al main office
    "c_scale": (23, 43.5),
    "c_101": (33, 43.5),
    "c_103": (42, 43.5),         # posizione di partenza del robot
    "c_105": (50, 43.5),
    "c_107": (58, 43.5),
    "c_109": (67, 43.5),         # angolo sud-est
    "c_111": (74, 43.5),
    # Corridoio est (da sud a nord)
    "c_113": (67, 35),
    "c_115": (67, 26),
    "c_117": (67, 17),
    "c_nord_est": (67, 12.5),
    # Corridoio nord (da est a ovest)
    "c_119": (61, 12.5),
    "c_121": (53, 12.5),
    "c_123": (45, 12.5),
    "c_125": (37, 12.5),
    "c_127": (29, 12.5),
    "c_129": (21, 12.5),
    "c_nord_ovest": (13, 12.5),
    # Corridoio ovest
    "caricabatterie": (13, 28),
    # Stanze
    "main_office": (13, 50), "r101": (33, 50), "r103": (42, 50), "r105": (50, 50),
    "r107": (58, 50), "r109": (66, 50), "r111": (74, 50),
    "r113": (74, 35), "r115": (74, 26), "r117": (74, 17),
    "r119": (61, 5), "r121": (53, 5), "r123": (45, 5), "r125": (37, 5),
    "r127": (29, 5), "r129": (21, 5), "r131": (13, 5),
    "lab_a": (30, 33), "lab_b": (52, 33), "lab_c": (52, 21), "lab_d": (30, 21),
}

# Le scale non sono attraversabili: il robot deve starne lontano.
SCALE = (23, 47)
DISTANZA_SICUREZZA_SCALE = 4.0

SPINTA = "spinta"   # porta che si apre spingendo
CHIAVE = "chiave"   # porta chiusa a chiave

# (nodo, nodo, porta): porta è None, SPINTA o CHIAVE
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
    # Stanze sud
    ("c_sud_ovest", "main_office", CHIAVE), ("c_101", "r101", SPINTA),
    ("c_103", "r103", SPINTA), ("c_105", "r105", SPINTA), ("c_107", "r107", SPINTA),
    ("c_109", "r109", SPINTA), ("c_111", "r111", SPINTA),
    # Stanze est
    ("c_113", "r113", SPINTA), ("c_115", "r115", SPINTA), ("c_117", "r117", CHIAVE),
    # Stanze nord
    ("c_119", "r119", SPINTA), ("c_121", "r121", SPINTA), ("c_123", "r123", SPINTA),
    ("c_125", "r125", SPINTA), ("c_127", "r127", SPINTA), ("c_129", "r129", SPINTA),
    ("c_nord_ovest", "r131", CHIAVE),
    # Laboratori: porte sul corridoio e porte interne
    ("c_101", "lab_a", SPINTA), ("c_105", "lab_b", SPINTA),
    ("c_129", "lab_d", SPINTA), ("c_123", "lab_c", CHIAVE),
    ("lab_a", "lab_b", None),          # passaggio aperto
    ("lab_a", "lab_d", SPINTA), ("lab_b", "lab_c", SPINTA),
]

PARTENZA = "c_103"
STANZE = [n for n in NODI if not n.startswith("c_") and n != "caricabatterie"]
