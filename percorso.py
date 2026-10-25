"""Modulo per il calcolo di percorsi e distanze su una piantina."""

import math
import heapq


def distanza(a, b):
    """Distanza euclidea tra due punti (x, y)."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def costruisci_grafo(nodi, archi):
    """Costruisce un grafo non orientato con pesi pari alla distanza euclidea."""
    graph = {node: {} for node in nodi}
    for a, b, _ in archi:
        if a in graph and b in graph:
            w = distanza(nodi[a], nodi[b])
            graph[a][b] = w
            graph[b][a] = w
    return graph


def percorso(nodi, archi, partenza, arrivo, bloccati=()):
    """Trova il percorso più breve tra partenza e arrivo (Dijkstra)."""
    if partenza not in nodi or arrivo not in nodi:
        raise ValueError("Nodo di partenza o arrivo non presente.")
    if partenza == arrivo:
        return [partenza]

    graph = costruisci_grafo(nodi, archi)
    for a, b in bloccati:
        if a in graph and b in graph:
            graph[a].pop(b, None)
            graph[b].pop(a, None)

    dist = {node: float('inf') for node in nodi}
    prev = {node: None for node in nodi}
    dist[partenza] = 0.0
    heap = [(0.0, partenza)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == arrivo:
            break
        if d > dist[u]:
            continue
        for v, w in graph[u].items():
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if dist[arrivo] == float('inf'):
        return None

    path = []
    node = arrivo
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path


def lunghezza(nodi, cammino):
    """Lunghezza totale di un percorso (somma delle distanze euclidee)."""
    if len(cammino) <= 1:
        return 0.0
    total = 0.0
    for i in range(len(cammino) - 1):
        total += distanza(nodi[cammino[i]], nodi[cammino[i + 1]])
    return total
