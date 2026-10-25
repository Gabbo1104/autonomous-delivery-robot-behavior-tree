"""Shortest paths and distances on the floor graph.

This module is generic: it knows nothing about the robot or the building. It
works on any graph given as

* ``nodi``: dict ``name -> (x, y)`` (positions in metres), and
* ``archi``: list of ``(a, b, extra)`` tuples; ``extra`` (the door information
  in mappa.ARCHI) is ignored here.

Edges are undirected and their weight is the straight-line (Euclidean) distance
between the two nodes, so "shortest" means "fewest metres travelled", not
"fewest hops".

Note: this module was written by the local model (LFM2.5) through the
``delega-locale`` skill, against the specification in tests/test_percorso.py.
It was later cross-checked against an independent Floyd-Warshall
implementation on thousands of random graphs.

Glossary: distanza = distance, grafo = graph, percorso = path/route,
partenza = start, arrivo = goal, bloccati = blocked edges, lunghezza = length,
cammino = walk (list of nodes).
"""

import math
import heapq


def distanza(a, b):
    """Euclidean distance between two points ``(x, y)``."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def costruisci_grafo(nodi, archi):
    """Build an undirected adjacency dict weighted by Euclidean distance.

    Returns ``{node: {neighbour: distance, ...}, ...}``. Every node of ``nodi``
    is a key, even isolated ones (they map to ``{}``). Edges that mention an
    unknown node are silently skipped, so a typo in mappa.ARCHI shows up as an
    unreachable node (caught by tests/test_percorso.py), not as an exception.
    """
    graph = {node: {} for node in nodi}
    for a, b, _ in archi:
        if a in graph and b in graph:
            w = distanza(nodi[a], nodi[b])
            # Undirected: store the edge in both directions.
            graph[a][b] = w
            graph[b][a] = w
    return graph


def percorso(nodi, archi, partenza, arrivo, bloccati=()):
    """Shortest path from ``partenza`` to ``arrivo`` using Dijkstra's algorithm.

    ``bloccati`` is an iterable of ``(a, b)`` pairs: those edges are removed in
    BOTH directions before searching (the robot uses this for obstacles it has
    already discovered).

    Returns the list of node names from ``partenza`` to ``arrivo`` inclusive,
    ``[partenza]`` if they are the same node, or ``None`` if ``arrivo`` cannot
    be reached. Raises ``ValueError`` if either node is not in ``nodi``.

    The graph is rebuilt on every call. That is wasteful in theory but cheap in
    practice (about 40 nodes; a whole simulation spends a few hundredths of a
    second here), and it keeps the function stateless and easy to test.
    """
    if partenza not in nodi or arrivo not in nodi:
        raise ValueError("Nodo di partenza o arrivo non presente.")
    if partenza == arrivo:
        return [partenza]

    graph = costruisci_grafo(nodi, archi)
    # Remove the blocked edges (pop with a default, so blocking an edge that
    # does not exist is harmless).
    for a, b in bloccati:
        if a in graph and b in graph:
            graph[a].pop(b, None)
            graph[b].pop(a, None)

    # Standard Dijkstra with a binary heap:
    # dist[n] = best known distance from the start, prev[n] = previous node on
    # that best path (used to rebuild the path at the end).
    dist = {node: float('inf') for node in nodi}
    prev = {node: None for node in nodi}
    dist[partenza] = 0.0
    heap = [(0.0, partenza)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == arrivo:
            # The first time the goal is popped its distance is final, so we can
            # stop early.
            break
        if d > dist[u]:
            # Stale heap entry: a shorter path to u was already processed.
            continue
        for v, w in graph[u].items():
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if dist[arrivo] == float('inf'):
        return None   # goal unreachable (e.g. all routes blocked)

    # Follow prev[] back from the goal to the start, then reverse.
    path = []
    node = arrivo
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path


def lunghezza(nodi, cammino):
    """Total length in metres of a path (sum of the Euclidean lengths of its steps).

    A path with a single node (or empty) has length 0.
    """
    if len(cammino) <= 1:
        return 0.0
    total = 0.0
    for i in range(len(cammino) - 1):
        total += distanza(nodi[cammino[i]], nodi[cammino[i + 1]])
    return total
