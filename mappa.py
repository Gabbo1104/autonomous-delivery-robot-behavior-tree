"""Floor map of the building (taken from the laboratory floor plan): grid, walls,
graph nodes and doors.

There are TWO representations of the same floor, and they must stay consistent:

1. A **graph** (``NODI`` + ``ARCHI``) that the robot uses to *reason*: path
   planning (see ``percorso.py``), "is there a door in front of me?", battery
   cost estimates, etc. Every place the robot can stand on is a node; an edge
   means "the robot can move directly between these two places".

2. A **character grid** (``GRIGLIA``) that is used to *draw* the map in the
   terminal (``tui.py``) and to animate the robot cell by cell along an edge
   (``celle_arco``). Walls are solid here, so the animation physically cannot go
   through a wall: the only way from a room to the corridor is the door cell.

Grid geometry: 71 columns x 28 rows. One column = 1 metre, one row = 2 metres,
because a terminal character is roughly twice as tall as it is wide; this keeps
the drawing proportional to the real floor plan. Grid cells are addressed as
``(column, row)``, i.e. ``(x, y)``, with ``(0, 0)`` in the top-left corner.

How to modify the map (checklist):

* Add/move a node: edit ``CELLE`` (grid position). ``NODI`` (metric position) is
  derived automatically. The cell must be free floor (``LIBERO``).
* Add a connection: append ``(a, b, verso)`` to ``ARCHI``. If the connection goes
  through a door, ``verso`` is the node the door swings towards, and the door's
  wall cell must be listed in ``CELLE_PORTE``.
* Add/move walls: edit ``_costruisci_griglia``.
* Run ``uv run pytest``: ``tests/test_griglia.py`` checks that nodes sit on free
  cells, that every edge can be walked on the grid without crossing walls, that
  every door has a cell in a wall, and that rooms are sealed when their doors
  are closed. ``tests/test_percorso.py`` checks that every node is reachable.

Glossary of the Italian names used here: griglia = grid, cella/casella = cell,
nodo = node, arco = edge, porta = door, verso = swing direction, muro = wall,
scale/scalini = stairs, libero = free, larghezza/altezza = width/height,
etichetta = label, corridoio = corridor, stanza = room, caricabatterie = charger.
"""
from collections import deque

# Grid size in cells (columns, rows).
LARGHEZZA, ALTEZZA = 71, 28
# Characters stored in GRIGLIA. These are the *logical* cell types; tui.py maps
# them to the characters/colours actually shown on screen.
MURO, SCALINI, LIBERO = "#", "=", " "   # wall, stairs, free floor

# Node name -> (column, row) on the grid.
# Naming convention: corridor nodes start with "c_" (other modules rely on this:
# e.g. obstacles are only placed between two "c_" nodes); "rNNN" are the office
# rooms of the floor plan; "lab_x" are the four laboratories.
CELLE = {
    # South corridor (west to east). These sit in the corridor right in front of
    # the room doors below them.
    "c_sud_ovest": (5, 22), "c_scale": (15, 22), "c_101": (25, 22), "c_103": (34, 22),
    "c_105": (42, 22), "c_107": (50, 22), "c_109": (59, 22), "c_111": (66, 22),
    # East corridor (south to north).
    "c_113": (59, 17), "c_115": (59, 12), "c_117": (59, 8), "c_nord_est": (59, 6),
    # North corridor (east to west).
    "c_119": (53, 6), "c_121": (45, 6), "c_123": (37, 6), "c_125": (29, 6),
    "c_127": (21, 6), "c_129": (13, 6), "c_nord_ovest": (5, 6),
    # West corridor: the charging station is a node of its own.
    "caricabatterie": (5, 14),
    # Rooms: one node in the middle of each room.
    "r131": (5, 3), "r129": (13, 3), "r127": (21, 3), "r125": (29, 3),
    "r123": (37, 3), "r121": (45, 3), "r119": (53, 3),
    "r117": (66, 8), "r115": (66, 12), "r113": (66, 17),
    "main_office": (5, 25), "r101": (25, 25), "r103": (34, 25), "r105": (42, 25),
    "r107": (50, 25), "r109": (58, 25), "r111": (66, 25),
    # Labs: placed near their internal doors so the grid path stays short
    # (tests/test_griglia.py rejects edges that zig-zag too much).
    "lab_d": (22, 11), "lab_c": (45, 11), "lab_a": (26, 17), "lab_b": (45, 17),
}

# Metric coordinates used for distances and shortest paths: (column, row * 2).
# A row is 2 m tall, so multiplying the row by 2 converts grid units to metres.
# Battery consumption (mondo.py) is computed from these distances.
NODI = {n: (c, r * 2) for n, (c, r) in CELLE.items()}

# The stairs are open towards the corridor and the robot must never get close to
# them. SCALE is the metric position of the middle of the staircase; a node is
# "too close" when its distance from SCALE is below DISTANZA_SICUREZZA_SCALE.
# With these numbers only "c_scale" (6 m away) is too close; its neighbours
# (about 11.7 m away) are safe. See Mondo.lontano_dalle_scale.
SCALE = (15, 50)
DISTANZA_SICUREZZA_SCALE = 7.0

# Edges of the graph: (node, node, verso).
# * verso = None  -> plain passage, no door (corridor segments, the open gap
#   between lab A and lab B).
# * verso = a node name -> there is a door on this edge and it swings open
#   TOWARDS that node. Moving in that direction the robot can PUSH the door
#   open; moving the other way it would have to PULL, which it cannot do, so it
#   must use the key instead (see Mondo.spingi / Mondo.usa_chiave and the
#   "bisogna spingere?" condition in rami/navigazione.py).
# Edges are undirected: the robot can travel both ways on every edge.
# percorso.py only looks at the first two items of each tuple.
ARCHI = [
    # Corridor ring: south -> east -> north -> west -> back to south.
    ("c_sud_ovest", "c_scale", None), ("c_scale", "c_101", None),
    ("c_101", "c_103", None), ("c_103", "c_105", None), ("c_105", "c_107", None),
    ("c_107", "c_109", None), ("c_109", "c_111", None),
    ("c_109", "c_113", None), ("c_113", "c_115", None), ("c_115", "c_117", None),
    ("c_117", "c_nord_est", None),
    ("c_nord_est", "c_119", None), ("c_119", "c_121", None), ("c_121", "c_123", None),
    ("c_123", "c_125", None), ("c_125", "c_127", None), ("c_127", "c_129", None),
    ("c_129", "c_nord_ovest", None),
    ("c_nord_ovest", "caricabatterie", None), ("caricabatterie", "c_sud_ovest", None),
    # Rooms: every room door swings inwards (towards the room), so the robot
    # pushes to get in and needs the key to get out.
    ("c_sud_ovest", "main_office", "main_office"), ("c_101", "r101", "r101"),
    ("c_103", "r103", "r103"), ("c_105", "r105", "r105"), ("c_107", "r107", "r107"),
    ("c_109", "r109", "r109"), ("c_111", "r111", "r111"),
    ("c_113", "r113", "r113"), ("c_115", "r115", "r115"), ("c_117", "r117", "r117"),
    ("c_119", "r119", "r119"), ("c_121", "r121", "r121"), ("c_123", "r123", "r123"),
    ("c_125", "r125", "r125"), ("c_127", "r127", "r127"), ("c_129", "r129", "r129"),
    ("c_nord_ovest", "r131", "r131"),
    # Labs: swing directions copied from the door arcs drawn on the floor plan
    # (some lab doors open towards the corridor, some towards the lab).
    ("c_129", "lab_d", "c_129"), ("c_123", "lab_c", "lab_c"),
    ("c_101", "lab_a", "c_101"), ("c_103", "lab_b", "lab_b"), ("c_107", "lab_b", "c_107"),
    ("lab_a", "lab_d", "lab_a"), ("lab_b", "lab_c", "lab_b"),
    ("lab_a", "lab_b", None),          # open passage, no door
]

# Grid cell of the door on each door edge, keyed by the (unordered) edge.
# The cell must be part of a wall in GRIGLIA: _costruisci_griglia turns it into
# a wall, and celle_arco "opens" it only when walking that specific edge. Every
# edge with a non-None verso must have an entry here (checked by the tests).
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

# Default starting node (in front of labs A/B, where the robot is drawn in the
# floor plan). The random scenarios in main.py pick a random start instead; this
# is still used as the default of Mondo(...) and as the reference node when
# checking that randomly placed obstacles leave the whole map reachable.
PARTENZA = "c_103"

# Room names written inside the rooms in the terminal view: text -> (column, row)
# of its first character. Purely cosmetic: tui.py writes them over whatever is
# in those cells, so keep them on free floor inside the room interiors.
ETICHETTE = {
    "r131": (3, 1), "r129": (11, 1), "r127": (19, 1), "r125": (27, 1), "r123": (35, 1),
    "r121": (43, 1), "r119": (51, 1), "r117": (64, 7), "r115": (64, 11), "r113": (64, 16),
    "office": (2, 26), "scale": (13, 26), "r101": (23, 26), "r103": (32, 26),
    "r105": (40, 26), "r107": (48, 26), "r109": (56, 26), "r111": (64, 26),
    "lab D": (12, 9), "lab C": (35, 9), "lab A": (12, 19), "lab B": (35, 19),
}


def _costruisci_griglia():
    """Build the grid (list of rows, each a list of single-character cells).

    Walls are drawn as horizontal/vertical segments; coordinates are inclusive.
    The layout mirrors the floor plan: a row of rooms along the north wall, the
    block of four labs in the middle (D | C on top, A | B below), three rooms on
    the east side, and a row of rooms plus the staircase along the south wall,
    with a corridor ring all around the lab block.
    """
    g = [[LIBERO] * LARGHEZZA for _ in range(ALTEZZA)]   # start with an empty floor

    def orizzontale(r, c1, c2):
        """Horizontal wall on row r, from column c1 to c2 (inclusive)."""
        for c in range(c1, c2 + 1):
            g[r][c] = MURO

    def verticale(c, r1, r2):
        """Vertical wall on column c, from row r1 to r2 (inclusive)."""
        for r in range(r1, r2 + 1):
            g[r][c] = MURO

    # Outer perimeter of the building.
    orizzontale(0, 0, 70), orizzontale(27, 0, 70), verticale(0, 0, 27), verticale(70, 0, 27)
    # North rooms (r131 ... r119): bottom wall on row 5, dividing walls between
    # rooms. The area east of r119 (columns 58-69) is left open floor.
    orizzontale(5, 0, 57)
    for c in (9, 17, 25, 33, 41, 49, 57):
        verticale(c, 0, 5)
    # Lab block: outer box, horizontal wall between the top and bottom labs,
    # vertical wall between left and right labs. The vertical wall stops at row
    # 14 and restarts at row 17, leaving rows 15-16 open: that is the open
    # passage between lab A and lab B (the ("lab_a", "lab_b", None) edge).
    orizzontale(8, 10, 56), orizzontale(14, 10, 56), orizzontale(20, 10, 56)
    verticale(10, 8, 20), verticale(56, 8, 20), verticale(33, 8, 14), verticale(33, 17, 20)
    # East rooms (r117, r115, r113): west wall on column 62, separators between rooms.
    verticale(62, 6, 20)
    for r in (6, 10, 15, 20):
        orizzontale(r, 62, 70)
    # South rooms: top wall on row 23, except columns 11-19 where the staircase
    # is open towards the corridor (no wall: that is why it is dangerous).
    orizzontale(23, 0, 10), orizzontale(23, 20, 70)
    for c in (10, 20, 30, 38, 46, 54, 62):
        verticale(c, 23, 27)
    # Staircase: SCALINI cells are never walkable (see percorso_griglia.libera).
    for r in range(23, 27):
        for c in range(11, 20):
            g[r][c] = SCALINI
    # Doors: a closed door behaves exactly like a wall. percorso_griglia lets the
    # robot through a door cell only when that cell is passed in `aperte`.
    for c, r in CELLE_PORTE.values():
        g[r][c] = MURO
    return g


# Built once at import time; treat it as read-only. GRIGLIA[row][column].
GRIGLIA = _costruisci_griglia()
# The 8 neighbouring cells (dc, dr): orthogonal and diagonal moves.
VICINI_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def percorso_griglia(da, a, aperte=()):
    """Shortest list of cells from ``da`` to ``a`` (both ``(column, row)``).

    Breadth-first search on the grid, moving in 8 directions. Only LIBERO cells
    are walkable, plus the door cells listed in ``aperte`` (doors that are open
    for this move). Diagonal moves are not allowed to "cut the corner" of a wall:
    a diagonal step is only taken if both orthogonal cells next to it are free,
    so the robot never squeezes between two walls that touch at a corner.

    Returns the list of cells including both ends, or None if ``a`` cannot be
    reached. BFS minimises the number of steps (a diagonal step counts as 1).
    """
    aperte = set(aperte)

    def libera(c, r):
        """True if (c, r) is inside the grid and walkable right now."""
        return 0 <= c < LARGHEZZA and 0 <= r < ALTEZZA and (GRIGLIA[r][c] == LIBERO or (c, r) in aperte)

    # precedente[cell] = the cell we came from; doubles as the "visited" set.
    precedente = {da: None}
    coda = deque([da])
    while coda:
        c, r = coda.popleft()
        if (c, r) == a:
            # Walk the predecessor links back to the start, then reverse.
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
                continue  # no diagonal moves across the corner of a wall
            precedente[n] = (c, r)
            coda.append(n)
    return None


def celle_arco(a, b):
    """Cells the robot walks through on the grid to go from node ``a`` to node ``b``.

    Only the door of this particular edge (if any) is treated as open, so the
    path cannot sneak through another room's door. Used by tui.py to animate a
    move and by the tests to prove that every edge respects the walls.
    """
    porta = CELLE_PORTE.get(frozenset((a, b)))
    return percorso_griglia(CELLE[a], CELLE[b], [porta] if porta else ())
