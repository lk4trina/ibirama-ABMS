"""
PASSO 9 - Mapa interativo "de onde para onde" (rotas e desvios), a pedido da Defesa Civil de Ibirama
(ideia do Alerta Blu de Blumenau: o usuario diz onde esta e para onde quer ir; o mapa mostra o caminho
e, se houver fechamento, o desvio).

    python scripts/09_mapa_rotas.py

Gera um UNICO arquivo autocontido:
    resultados/mapa_rotas.html   grafo embutido em JSON + roteamento (Dijkstra) em JavaScript no navegador.
                                 Abre com duplo clique; o ROTEAMENTO funciona offline. Leaflet vem por CDN
                                 (versao fixa) e o fundo de satelite/OSM depende de internet (so o fundo).

NAO altera o modelo GAMA nem a simulacao. Ferramenta de apoio/demonstracao, separada.

Fontes (nada inventado):
  - Rede: includes/dados/vias.shp (OSM, EPSG:31982); nomes em vias_nomes.csv.
  - Fechamentos informados pela Defesa Civil: interdicoes_defesa_civil.csv e vias_principais_defesa_civil.csv.
  - Poligonos de risco: riscos.shp (buffer de 40 m, como o modelo).
  - Pontos criticos (29, inclui o abrigo Ginasio Joao Moretti): pontos_criticos.geojson.
Velocidades iguais ao GAML: VEL_CLASSE_KMH (linha 92), VEL_MODO (91; moto 1,1x), VEL_PED 1,3 m/s (96).

RESSALVA: NAO e alerta em tempo real. Rede OSM, SEM sentido unico, SEM semaforo, tempo em FLUXO LIVRE.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import STRtree

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "includes" / "dados"
RESULT = RAIZ / "resultados"
RESULT.mkdir(exist_ok=True)
BUFFER_M = 40.0

VEL_KMH = {"motorway": 80, "trunk": 60, "primary": 50, "secondary": 50, "tertiary": 40, "unclassified": 30,
           "residential": 30, "living_street": 20, "service": 20, "track": 20}   # VEL_CLASSE_KMH (GAML 92)
VEL_PADRAO = 30
VEL_MODO_MOTO = 1.1     # VEL_MODO["moto"] (GAML 91)
VEL_PED = 1.3           # m/s (GAML 96)

print("Lendo a rede...")
vias = gpd.read_file(DADOS / "vias.shp")
assert vias.crs is not None and vias.crs.to_epsg() == 31982, "vias.shp deve estar em EPSG:31982"
E = len(vias)
hw = vias["highway"].astype(str).values
carro_ok = vias["carro"].astype(int).values.astype(bool) if "carro" in vias.columns else np.ones(E, bool)
pedest_ok = vias["pedest"].astype(int).values.astype(bool) if "pedest" in vias.columns else np.ones(E, bool)
comp = (vias["comp"].astype(float).values if "comp" in vias.columns else vias.geometry.length.values)
geoms = list(vias.geometry.values)

# --- nos (extremos arredondados a 0,1 m, como em simulador.py / 08_desvios.py) ---
node_map, u, v = {}, np.empty(E, int), np.empty(E, int)
for i, g in enumerate(geoms):
    cs = list(g.coords)
    a = (round(cs[0][0], 1), round(cs[0][1], 1))
    b = (round(cs[-1][0], 1), round(cs[-1][1], 1))
    u[i] = node_map.setdefault(a, len(node_map))
    v[i] = node_map.setdefault(b, len(node_map))
N = len(node_map)
xy = np.zeros((N, 2))
for p, i in node_map.items():
    xy[i] = p

vcarro = np.array([VEL_KMH.get(h, VEL_PADRAO) for h in hw]) / 3.6   # m/s (carro)
loop = u == v

# --- nos em lat/lon (4326) p/ o mapa ---
nos_ll = gpd.GeoSeries(gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=vias.crs).to_crs(4326)
nodes_latlon = [[round(float(p.y), 6), round(float(p.x), 6)] for p in nos_ll]

# --- geometria de cada trecho em lat/lon (p/ desenhar rota/fechamento com a forma real da rua) ---
geoms_ll = gpd.GeoSeries(geoms, crs=vias.crs).to_crs(4326)
egeom = []
for g in geoms_ll.values:
    egeom.append([[round(float(y), 6), round(float(x), 6)] for x, y in g.coords])

# --- nomes das ruas por trecho (vias_nomes.csv) ---
nomes_tab = pd.read_csv(DADOS / "vias_nomes.csv")
nome_de = {int(r.id_trecho): (str(r["name"]) if pd.notna(r["name"]) else "") for _, r in nomes_tab.iterrows()}
nomes_unicos = sorted({n for n in nome_de.values() if n})
nome_idx = {n: i + 1 for i, n in enumerate(nomes_unicos)}   # 0 = sem nome
names_tab = [""] + nomes_unicos
edge_nameidx = [nome_idx.get(nome_de.get(e, ""), 0) for e in range(E)]

# --- trechos a <=40 m de algum poligono de risco (como edges_poli no modelo) ---
riscos = gpd.read_file(DADOS / "riscos.shp").to_crs(vias.crs)
arvore = STRtree(geoms)
risco_edge = np.zeros(E, bool)
for _, r in riscos.iterrows():
    idx = np.atleast_1d(arvore.query(r.geometry.buffer(BUFFER_M), predicate="intersects")).astype(int)
    risco_edge[idx] = True

# --- arestas compactas: [u, v, len, vcarro, carro, pe, nameIdx, risco] ---
edges = []
for e in range(E):
    edges.append([int(u[e]), int(v[e]), round(float(comp[e]), 1), round(float(vcarro[e]), 3),
                  int(bool(carro_ok[e]) and not loop[e]), int(bool(pedest_ok[e]) and not loop[e]),
                  int(edge_nameidx[e]), int(bool(risco_edge[e]))])


def parse_ids(s):
    if pd.isna(s) or str(s).strip() == "":
        return []
    return [int(x) for x in str(s).split(";") if x.strip() != ""]


# --- fechamentos informados pela Defesa Civil (interdicoes + vias principais) ---
interd = []   # {nome, tipo, obs, ids}
inter = pd.read_csv(DADOS / "interdicoes_defesa_civil.csv")
for _, r in inter.iterrows():
    interd.append({"nome": str(r["via"]), "grupo": "Interdição (Defesa Civil)",
                   "obs": str(r.get("status_associacao", "")), "ids": parse_ids(r.get("ids_trechos", ""))})
principais = pd.read_csv(DADOS / "vias_principais_defesa_civil.csv")
nomes_inter = {d["nome"] for d in interd}
for _, r in principais.iterrows():
    nome = str(r["nome"])
    if nome in nomes_inter:
        continue   # evita duplicar (ex.: Rua Blumenau esta nas duas listas)
    interd.append({"nome": nome, "grupo": "Via principal (Defesa Civil)",
                   "obs": str(r.get("status_associacao", "")), "ids": parse_ids(r.get("ids_trechos", ""))})

# --- pontos criticos (29) -> no mais proximo da rede ---
pts = gpd.read_file(DADOS / "pontos_criticos.geojson").to_crs(vias.crs)
pts_ll = pts.to_crs(4326)
pontos = []
for (_, r), (_, rll) in zip(pts.iterrows(), pts_ll.iterrows()):
    d = np.hypot(xy[:, 0] - r.geometry.x, xy[:, 1] - r.geometry.y)
    no = int(np.argmin(d))
    pontos.append({"grupo": str(r.get("grupo", "")), "nome": str(r.get("nome", "")),
                   "no": no, "lat": round(float(rll.geometry.y), 6), "lon": round(float(rll.geometry.x), 6),
                   "dist_no_m": round(float(d[no]), 1)})

# --- busca por nome de rua -> um no representativo (mais central entre os nos da rua) ---
ruas_busca = []
for nome in nomes_unicos:
    es = [e for e in range(E) if nome_de.get(e, "") == nome]
    nos = sorted(set(int(u[e]) for e in es) | set(int(v[e]) for e in es))
    if not nos:
        continue
    cen = xy[nos].mean(axis=0)
    no = nos[int(np.argmin(np.hypot(xy[nos, 0] - cen[0], xy[nos, 1] - cen[1])))]
    ruas_busca.append({"nome": nome, "no": int(no)})

# --- poligonos de risco (4326) p/ exibir ---
riscos_ll = riscos.to_crs(4326)
riscos_gj = json.loads(riscos_ll[["grau_num", "geometry"]].to_json())

centro = [float(np.mean([p["lat"] for p in pontos])), float(np.mean([p["lon"] for p in pontos]))]

DATA = {
    "centro": centro,
    "nodes": nodes_latlon,
    "edges": edges,
    "egeom": egeom,
    "names": names_tab,
    "interd": interd,
    "pontos": pontos,
    "ruas": ruas_busca,
    "riscos": riscos_gj,
    "vel_moto": VEL_MODO_MOTO,
    "vel_ped": VEL_PED,
}
print(f"Rede: {E} trechos, {N} nos | {len(interd)} fechamentos | {len(pontos)} pontos | {len(ruas_busca)} ruas na busca")

# ---- grava um JSON de apoio (p/ a verificacao JS x Python) e injeta no HTML ----
(RESULT / "mapa_rotas_dados.json").write_text(json.dumps(DATA, ensure_ascii=False), encoding="utf-8")
DATA_JSON = json.dumps(DATA, ensure_ascii=False, separators=(",", ":"))

# fonte unica do roteamento e do layout (compartilhados com a verificacao em Node)
AQUI = Path(__file__).resolve().parent
ROUTER_JS = (AQUI / "_rotas_router.js").read_text(encoding="utf-8")
_TEMPLATE = (AQUI / "_rotas_template.html").read_text(encoding="utf-8")

HTML = _TEMPLATE.replace("/*__ROUTER__*/", ROUTER_JS).replace("/*__DATA__*/", DATA_JSON)
(RESULT / "mapa_rotas.html").write_text(HTML, encoding="utf-8")
# copia tambem o router como modulo .js (a verificacao em Node usa exatamente este codigo)
(RESULT / "mapa_rotas_router.js").write_text(ROUTER_JS, encoding="utf-8")
print("Gravado resultados/mapa_rotas.html, mapa_rotas_dados.json e mapa_rotas_router.js")
