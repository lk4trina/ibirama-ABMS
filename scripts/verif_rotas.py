"""
Verificacao do roteamento: JavaScript (Node, o MESMO resultados/mapa_rotas_router.js
usado no HTML) x Python. 20 pares origem-destino sorteados, com e sem fechamentos.
As distancias devem coincidir (tolerancia 1 m). Imprime a tabela.

Anexo: confere que o custo (tempo) do Dijkstra-Python bate com o scipy.dijkstra
(mesmo algoritmo do script 08), ancorando a comparacao ao "Dijkstra do script 08".

    python scripts/verif_rotas.py
"""
import heapq
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra as sp_dijkstra

RAIZ = Path(__file__).resolve().parent.parent
RESULT = RAIZ / "resultados"
DATA = json.loads((RESULT / "mapa_rotas_dados.json").read_text(encoding="utf-8"))
SEED = 123
N_PARES = 20
# cenario "com fechamentos": tres interdicoes inteiras (Blumenau, Guarani, Santa Cruz)
FECH_MARCADOS = [0, 1, 2]
MODAL = "carro"

edges = DATA["edges"]
N = len(DATA["nodes"])
vel_moto = DATA["vel_moto"]
vel_ped = DATA["vel_ped"]


def peso(e):
    _u, _v, length, vc, carro, pe = e[0], e[1], e[2], e[3], e[4], e[5]
    if MODAL == "pe":
        return (pe == 1), length / vel_ped
    if MODAL == "moto":
        return (carro == 1), length / (vc * vel_moto)
    return (carro == 1), length / vc


def conjunto_fechado(marcados, modo="inteira"):
    s = set()
    for m in marcados:
        for idx in DATA["interd"][m]["ids"]:
            if 0 <= idx < len(edges):
                if modo == "risco" and edges[idx][7] != 1:
                    continue
                s.add(idx)
    return s


def dijkstra_py(src, dst, fechados):
    """Mesma construcao de adjacencia e desempate (custo, no) do _rotas_router.js."""
    adj = [[] for _ in range(N)]
    for e_i, e in enumerate(edges):
        if e_i in fechados:
            continue
        ok, w = peso(e)
        if not ok or not (w > 0):
            continue
        adj[e[0]].append((e[1], w, e_i))
        adj[e[1]].append((e[0], w, e_i))
    dist = [math.inf] * N
    prevN = [-1] * N
    prevE = [-1] * N
    dist[src] = 0.0
    heap = [(0.0, src)]
    while heap:
        du, nu = heapq.heappop(heap)
        if du > dist[nu]:
            continue
        if nu == dst:
            break
        for nv, w, e_i in adj[nu]:
            nd = du + w
            if nd < dist[nv]:
                dist[nv] = nd
                prevN[nv] = nu
                prevE[nv] = e_i
                heapq.heappush(heap, (nd, nv))
    if not math.isfinite(dist[dst]):
        return dict(ok=False)
    x, eds = dst, []
    while x != -1:
        if prevE[x] != -1:
            eds.append(prevE[x])
        x = prevN[x]
    eds.reverse()
    dist_m = float(sum(edges[e][2] for e in eds))
    return dict(ok=True, dist_m=dist_m, tempo_s=dist[dst])


def scipy_custo(src, dst, fechados):
    """Custo (tempo) por scipy.dijkstra - mesmo algoritmo do script 08.
    OBS: ha 12 pares de nos com trechos PARALELOS; csr_matrix SOMA pesos de (u,v)
    repetidos, o que infla o custo. Dijkstra correto (JS/mirror) usa o MENOR. Aqui
    deduplicamos por minimo, como um Dijkstra deve enxergar o grafo."""
    menor = {}
    for e_i, e in enumerate(edges):
        if e_i in fechados:
            continue
        ok, w = peso(e)
        if not ok or not (w > 0):
            continue
        a, b = e[0], e[1]
        k = (a, b) if a <= b else (b, a)
        if k not in menor or w < menor[k]:
            menor[k] = w
    uu, vv, ww = [], [], []
    for (a, b), w in menor.items():
        uu += [a, b]; vv += [b, a]; ww += [w, w]
    g = csr_matrix((ww, (uu, vv)), shape=(N, N))
    d = sp_dijkstra(g, indices=src)
    return float(d[dst]) if math.isfinite(d[dst]) else None


# ---- sorteio dos pares (so entre nos com algum trecho de carro) ----
usados = set()
for e in edges:
    if e[4] == 1:
        usados.add(e[0]); usados.add(e[1])
usados = sorted(usados)
rng = np.random.default_rng(SEED)
pares = []
while len(pares) < N_PARES:
    a, b = int(rng.choice(usados)), int(rng.choice(usados))
    if a != b:
        pares.append((a, b))

fset = conjunto_fechado(FECH_MARCADOS, "inteira")

# ---- Python ----
linhas = []   # (idx, cenario, o, d, dist_py, ok_py)
for (o, d) in pares:
    for cen, F in (("sem fechamento", set()), ("com fechamento", fset)):
        r = dijkstra_py(o, d, F)
        linhas.append(dict(o=o, d=d, cen=cen, py_ok=r["ok"],
                           py_dist=(r["dist_m"] if r["ok"] else None),
                           py_tempo=(r["tempo_s"] if r["ok"] else None)))

# ---- Node (mesmo router do HTML) ----
harness = r"""
const fs = require("fs");
const ROTAS = require(process.argv[2]);
const DATA = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const casos = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const fech = new Set(casos.fechados);
const out = casos.pares.map(c => {
  const F = c.cen === "com fechamento" ? fech : new Set();
  const r = ROTAS.rota(DATA, c.o, c.d, casos.modal, F);
  return r.ok ? { ok: true, dist: r.dist_m, tempo: r.tempo_s } : { ok: false };
});
process.stdout.write(JSON.stringify(out));
"""
scratch = Path(r"D:\Temp\claude\C--Users-Brenda-Downloads-teste-final\916c2073-78ca-45b0-a2fe-06fdf9667a46\scratchpad")
scratch.mkdir(parents=True, exist_ok=True)
(scratch / "harness.js").write_text(harness, encoding="utf-8")
casos = {"modal": MODAL, "fechados": sorted(fset),
         "pares": [{"o": l["o"], "d": l["d"], "cen": l["cen"]} for l in linhas]}
(scratch / "casos.json").write_text(json.dumps(casos), encoding="utf-8")
res = subprocess.run(["node", str(scratch / "harness.js"),
                      str(RESULT / "mapa_rotas_router.js"),
                      str(RESULT / "mapa_rotas_dados.json"),
                      str(scratch / "casos.json")],
                     capture_output=True, text=True)
if res.returncode != 0:
    print("ERRO no Node:", res.stderr); sys.exit(1)
js = json.loads(res.stdout)

# ---- comparar ----
print(f"\nModal: {MODAL} | fechamentos (inteira): {[DATA['interd'][i]['nome'] for i in FECH_MARCADOS]}")
print(f"{len(fset)} trechos fechados no cenario 'com fechamento'\n")
hdr = f"{'#':>2} {'cenario':<16} {'orig':>5} {'dest':>5} {'dist_JS(m)':>11} {'dist_PY(m)':>11} {'dif(m)':>8} {'status':>12}"
print(hdr); print("-" * len(hdr))
pior = 0.0
ok_count = 0
for i, (l, j) in enumerate(zip(linhas, js)):
    if l["py_ok"] != j["ok"]:
        print(f"{i:>2} {l['cen']:<16} {l['o']:>5} {l['d']:>5} {'':>11} {'':>11} {'':>8}   OK/!=OK DIVERGE")
        continue
    if not l["py_ok"]:
        print(f"{i:>2} {l['cen']:<16} {l['o']:>5} {l['d']:>5} {'sem rota':>11} {'sem rota':>11} {'-':>8} {'ambos sem':>12}")
        ok_count += 1
        continue
    dif = abs(j["dist"] - l["py_dist"])
    pior = max(pior, dif)
    st = "OK" if dif <= 1.0 else "DIVERGE"
    if st == "OK":
        ok_count += 1
    print(f"{i:>2} {l['cen']:<16} {l['o']:>5} {l['d']:>5} {j['dist']:>11.1f} {l['py_dist']:>11.1f} {dif:>8.3f} {st:>12}")
print("-" * len(hdr))
print(f"maior diferenca de distancia JS x PY: {pior:.4f} m | casos OK: {ok_count}/{len(linhas)}")

# ---- ancoragem: Python-mirror x scipy (script 08) em alguns casos ----
print("\nAncoragem (tempo) Dijkstra-Python x scipy.dijkstra (algoritmo do script 08):")
pior_t = 0.0
for l in linhas[:8]:
    if not l["py_ok"]:
        continue
    F = set() if l["cen"] == "sem fechamento" else fset
    c = scipy_custo(l["o"], l["d"], F)
    if c is None:
        continue
    dt = abs(c - l["py_tempo"])
    pior_t = max(pior_t, dt)
print(f"  maior diferenca de tempo (8 casos): {pior_t:.6e} s  (==0 => mesmo otimo do script 08)")
