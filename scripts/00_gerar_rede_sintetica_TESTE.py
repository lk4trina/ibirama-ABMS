"""
REDE SINTÉTICA - SOMENTE PARA TESTAR O MODELO. NÃO USAR NOS RESULTADOS DO ARTIGO.

Por que existe: a rede real de ruas vem do OpenStreetMap (script 02), que precisa de internet.
Este script inventa uma malha de ruas (grade irregular + um "rio" com poucas pontes + uma rua
passando por cada polígono de risco) na mesma região do mapa de risco real, com o mesmo formato
de arquivo da rede real. Assim dá para testar o modelo antes de ter as ruas de verdade.

Gera:
    dados/vias_teste_SINTETICO.shp          (ruas, UTM 22S)
    dados/pontos_criticos_TESTE.csv/.shp    (hospital/bombeiros/abrigos de MENTIRA)
Uso:
    python scripts/00_gerar_rede_sintetica_TESTE.py
"""
import math
import random
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

RAIZ = Path(__file__).resolve().parent.parent
random.seed(7)
np.random.seed(7)

riscos = gpd.read_file(RAIZ / "dados" / "riscos.shp")
x0, y0, x1, y1 = riscos.total_bounds
x0, y0, x1, y1 = x0 - 300, y0 - 300, x1 + 300, y1 + 300
PASSO = 220.0

# --- nós da grade com um pouco de desordem -------------------------------------------------
xs = np.arange(x0, x1, PASSO)
ys = np.arange(y0, y1, PASSO)
nos = {}
for i, x in enumerate(xs):
    for j, y in enumerate(ys):
        nos[(i, j)] = (x + random.uniform(-25, 25), y + random.uniform(-25, 25))

# --- "rio": uma curva leste-oeste atravessando o centro; só 3 pontes -----------------------
ymid = (y0 + y1) / 2
largura = x1 - x0
rio_pts = [(x, ymid + 500 * math.sin((x - x0) / largura * 2 * math.pi)) for x in np.linspace(x0 - 1500, x1 + 1500, 300)]
rio = LineString(rio_pts)
pontes_x = [x0 + largura * f for f in (0.28, 0.55, 0.82)]

arestas = []  # (a, b, geom, highway)
for (i, j), p in nos.items():
    for (di, dj) in ((1, 0), (0, 1)):
        q = nos.get((i + di, j + dj))
        if q is None:
            continue
        if random.random() < 0.10:  # 10% das ruas inexistentes -> malha irregular
            continue
        g = LineString([p, q])
        hw = "primary" if (j % 6 == 0 and dj == 0) or (i % 8 == 0 and di == 0) else "residential"
        if g.intersects(rio):
            xc = g.centroid.x
            if min(abs(xc - px) for px in pontes_x) > 140:
                continue  # sem ponte aqui
            hw = "secondary"
        arestas.append((p, q, g, hw))

# --- uma rua passando por cada polígono de risco ainda sem rua ------------------------------
G = nx.Graph()
for p, q, g, hw in arestas:
    G.add_edge((round(p[0], 1), round(p[1], 1)), (round(q[0], 1), round(q[1], 1)), geom=g, hw=hw)
no_xy = np.array(list(G.nodes))
gdf_tmp = gpd.GeoSeries([a[2] for a in arestas])
extras = 0
for _, r in riscos.iterrows():
    c = r.geometry.centroid
    if gdf_tmp.distance(r.geometry).min() <= 40:
        continue
    d = np.hypot(no_xy[:, 0] - c.x, no_xy[:, 1] - c.y)
    viz = np.argsort(d)[:2]
    if d[viz[1]] > 600:
        continue
    cn = (round(c.x, 1), round(c.y, 1))
    ok = True
    novas = []
    for k in viz:
        n = tuple(no_xy[k])
        g = LineString([cn, n])
        if g.intersects(rio):
            ok = False
        novas.append((cn, n, g))
    if ok:
        for cn_, n, g in novas:
            G.add_edge(cn_, n, geom=g, hw="residential")
        extras += 1

maior = max(nx.connected_components(G), key=len)
G = G.subgraph(maior).copy()

linhas = [dict(highway=d["hw"], carro=1, pedest=1, comp=round(d["geom"].length, 1), geometry=d["geom"]) for _, _, d in G.edges(data=True)]
vias = gpd.GeoDataFrame(linhas, crs="EPSG:31982")
vias.to_file(RAIZ / "dados" / "vias_teste_SINTETICO.shp")

# --- pontos críticos de MENTIRA (substituir pelos reais quando a Defesa Civil responder) ----
nos_l = np.array(list(G.nodes))
alag = riscos[riscos.alaga == 1]
cx, cy = alag.geometry.centroid.x.mean(), alag.geometry.centroid.y.mean()


def mais_perto(x, y, dx=0, dy=0):
    d = np.hypot(nos_l[:, 0] - (x + dx), nos_l[:, 1] - (y + dy))
    return nos_l[np.argmin(d)]


pts = [
    ("hospital", "Hospital (POSICAO FICTICIA)", *mais_perto(cx, cy, 0, 250)),
    ("bombeiros", "Bombeiros (POSICAO FICTICIA)", *mais_perto(cx, cy, 400, -300)),
    ("abrigo", "Abrigo A (POSICAO FICTICIA)", *mais_perto(cx, cy, -1500, 600)),
    ("abrigo", "Abrigo B (POSICAO FICTICIA)", *mais_perto(cx, cy, 1800, -700)),
]
from pyproj import Transformer

df_pts = pd.DataFrame(pts, columns=["tipo", "nome", "x", "y"])
lon, lat = Transformer.from_crs("EPSG:31982", "EPSG:4326", always_xy=True).transform(df_pts.x.values, df_pts.y.values)
df_pts["lat"], df_pts["lon"] = lat.round(6), lon.round(6)
df_pts[["tipo", "nome", "lat", "lon"]].to_csv(RAIZ / "dados" / "pontos_criticos_TESTE.csv", index=False)
gpd.GeoDataFrame(df_pts[["tipo", "nome"]], geometry=gpd.points_from_xy(df_pts.x, df_pts.y), crs="EPSG:31982").to_file(
    RAIZ / "dados" / "pontos_criticos_TESTE.shp")

print(f"Rede sintética: {G.number_of_nodes()} nós, {G.number_of_edges()} trechos "
      f"({extras} ruas extras para cobrir polígonos de risco)")
print("Pontes (secondary):", int((vias.highway == 'secondary').sum()), "trechos")
