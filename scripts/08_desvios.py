"""
PASSO 8 - Desvios (rotas alternativas) para trechos fechados, a pedido da Defesa Civil de Ibirama
(ideia parecida com o Alerta Blu de Blumenau).

    python scripts/08_desvios.py

O que gera (todos NOVOS, nao altera vias.shp nem o modelo):
    includes/dados/desvios_sugeridos.csv     1 linha por cenario de fechamento x modal (carro/pedestre)
    resultados/desvios_exemplos.geojson      geometrias (trecho fechado, caminho original, desvio) EPSG:4326
    resultados/mapa_desvios.html             mapa interativo (folium)
    resultados/fig_desvios.png               figura 300 dpi (acrescimo por rua interditada)

Dependencias (ja no requirements.txt): geopandas, shapely, numpy, pandas, scipy, matplotlib, folium.

RESSALVA (vale para TODA saida): isto NAO e um alerta em tempo real; sao desvios PRE-CALCULADOS para
PLANEJAMENTO, sobre a rede do OpenStreetMap, SEM sentido unico e SEM semaforo, pelo caminho mais rapido
em fluxo livre (sem congestionamento). Os arquivos *_TESTE/*_SINTETICO sao ficticios e NAO sao usados.

Velocidades e regras copiadas do modelo (fonte da verdade):
  VEL_CLASSE_KMH -> models/ibirama.gaml linha 86 ; python/simulador.py linhas 42-43
  VEL_PED 1.3 m/s -> ibirama.gaml linha 90 ; simulador.py linha 46
  PESO_VIA -> ibirama.gaml linha 88 ; simulador.py PESO_VIA
  buffer de 40 m (buffer_m) -> ibirama.gaml linha 54
  campos 'carro'/'pedest' por trecho -> ibirama.gaml linha 139 (via from vias.shp)
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from shapely import STRtree
from shapely.geometry import LineString, mapping

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "includes" / "dados"
RESULT = RAIZ / "resultados"
RESULT.mkdir(exist_ok=True)
SEED = 42
BUFFER_M = 40.0
N_ORIGENS = 200
MAX_RECON = 400   # p/ nao reconstruir caminhos demais: amostra por cenario (dist e nomes do desvio)

VEL_KMH = {"motorway": 80, "trunk": 60, "primary": 50, "secondary": 50, "tertiary": 40, "unclassified": 30,
           "residential": 30, "living_street": 20, "service": 20, "track": 20}
VEL_PADRAO = 30
VEL_PED = 1.3
PESO_VIA = {"motorway": 10, "trunk": 10, "primary": 8, "secondary": 6, "tertiary": 4,
            "unclassified": 1.5, "residential": 1.5, "living_street": 1.0, "service": 0.5, "track": 0.2}
PESO_PADRAO = 1.0

RESSALVA = ("Desvios PRE-CALCULADOS para planejamento - NAO e alerta em tempo real. "
            "Rede OSM, sem sentido unico, sem semaforo, caminho mais rapido em fluxo livre.")

print(RESSALVA)
print("Lendo a rede...")
vias = gpd.read_file(DADOS / "vias.shp")          # 1182 trechos, EPSG:31982; id_trecho = indice da linha
assert vias.crs is not None and vias.crs.to_epsg() == 31982, "vias.shp deve estar em EPSG:31982"
E = len(vias)
hw = vias["highway"].astype(str).values
carro_ok = vias["carro"].astype(int).values.astype(bool) if "carro" in vias.columns else np.ones(E, bool)
pedest_ok = vias["pedest"].astype(int).values.astype(bool) if "pedest" in vias.columns else np.ones(E, bool)
comp = vias["comp"].astype(float).values if "comp" in vias.columns else vias.geometry.length.values

# --- nos (extremos arredondados a 0,1 m, como em simulador.py linhas 109-110) ---
node_map, u, v, geoms = {}, np.empty(E, int), np.empty(E, int), list(vias.geometry.values)
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

vel = np.array([VEL_KMH.get(h, VEL_PADRAO) for h in hw]) / 3.6
tempo = {"carro": comp / vel, "pedestre": comp / VEL_PED}      # s de fluxo livre por trecho
peso_via = np.array([PESO_VIA.get(h, PESO_PADRAO) for h in hw])
loop = u == v                                                  # auto-laco: nao entra no roteamento

# melhor aresta entre dois nos (menor tempo), para recuperar nomes/geometria de um caminho de nos
aresta_entre = {}
for e in range(E):
    if loop[e]:
        continue
    for key in ((u[e], v[e]), (v[e], u[e])):
        if key not in aresta_entre or tempo["carro"][e] < tempo["carro"][aresta_entre[key]]:
            aresta_entre[key] = e


def grafo(mask, modo):
    uu, vv, w = u[mask], v[mask], tempo[modo][mask]
    return csr_matrix((np.r_[w, w], (np.r_[uu, vv], np.r_[vv, uu])), shape=(N, N))


# componente de carro (nos uteis), peso por no e sorteio das origens
mcarro = carro_ok & ~loop
_, lab = connected_components(grafo(mcarro, "carro"), directed=False)
inc = np.r_[u[mcarro], v[mcarro]]
grande = np.argmax(np.bincount(lab[np.unique(inc)]))
nos_veic = np.where(lab == grande)[0]
peso_no = np.zeros(N)
np.maximum.at(peso_no, u[mcarro], peso_via[mcarro])
np.maximum.at(peso_no, v[mcarro], peso_via[mcarro])
rng = np.random.default_rng(SEED)
pw = peso_no[nos_veic]
origens = rng.choice(nos_veic, size=min(N_ORIGENS, len(nos_veic)), replace=False, p=pw / pw.sum())

# destinos: 29 pontos criticos -> no mais proximo entre nos_veic (como no GAML: no_rede = nos_veic closest_to)
pts = gpd.read_file(DADOS / "pontos_criticos.geojson").to_crs(vias.crs)
dest_nodes, dest_nomes = [], []
setv = set(int(x) for x in nos_veic)
for _, r in pts.iterrows():
    d = np.hypot(xy[:, 0] - r.geometry.x, xy[:, 1] - r.geometry.y)
    d[~np.isin(np.arange(N), nos_veic)] = np.inf
    dest_nodes.append(int(np.argmin(d)))
    dest_nomes.append(str(r.get("nome", "")))
dest_nodes = np.array(dest_nodes)
print(f"Rede: {E} trechos, {N} nos | {len(nos_veic)} nos de carro | {len(origens)} origens | {len(dest_nodes)} destinos")

# nomes das ruas por trecho (vias_nomes.csv)
nomes_tab = pd.read_csv(DADOS / "vias_nomes.csv")
nome_de = {int(r.id_trecho): (str(r["name"]) if pd.notna(r["name"]) else "") for _, r in nomes_tab.iterrows()}
ref_de = {int(r.id_trecho): (str(r["ref"]) if pd.notna(r["ref"]) else "") for _, r in nomes_tab.iterrows()}


def nomes_do_caminho(edges):
    vistos, out = set(), []
    for e in edges:
        nm = nome_de.get(e, "")
        if nm and nm not in vistos:
            vistos.add(nm); out.append(nm)
    return out


# --- trechos dentro de 40 m de cada poligono de risco (como edges_poli em simulador.py 160-166) ---
riscos = gpd.read_file(DADOS / "riscos.shp").to_crs(vias.crs)
arvore = STRtree(geoms)
edges_poli = []
buffer_union = set()
for _, r in riscos.iterrows():
    idx = np.atleast_1d(arvore.query(r.geometry.buffer(BUFFER_M), predicate="intersects")).astype(int)
    edges_poli.append(set(int(x) for x in idx))
    buffer_union.update(int(x) for x in idx)
GRAU_TXT = {1: "Medio", 2: "Alto", 3: "MuitoAlto"}


# ============================ A1: montar os cenarios de fechamento ============================
def parse_ids(s):
    if pd.isna(s) or str(s).strip() == "":
        return set()
    return set(int(x) for x in str(s).split(";") if x.strip() != "")


cenarios = []   # (nome, tipo, set_ids, obs)
inter = pd.read_csv(DADOS / "interdicoes_defesa_civil.csv")
for _, r in inter.iterrows():
    ids = parse_ids(r.get("ids_trechos", ""))
    nome = str(r["via"])
    cenarios.append((f"interdicao: {nome} (rua inteira)", "interdicao_inteira", ids, str(r.get("status_associacao", ""))))
    cenarios.append((f"interdicao: {nome} (so <=40m do risco)", "interdicao_buffer", ids & buffer_union, "intersecao com buffer 40 m"))
principais = pd.read_csv(DADOS / "vias_principais_defesa_civil.csv")
for _, r in principais.iterrows():
    ids = parse_ids(r.get("ids_trechos", ""))
    nome = str(r["nome"])
    cenarios.append((f"via principal: {nome} (via inteira)", "via_principal_inteira", ids, str(r.get("status_associacao", ""))))
    cenarios.append((f"via principal: {nome} (so <=40m do risco)", "via_principal_buffer", ids & buffer_union, "intersecao com buffer 40 m"))
for i, (_, r) in enumerate(riscos.iterrows()):
    g = int(r.grau_num)
    cenarios.append((f"poligono {i} (grau {GRAU_TXT.get(g, g)})", "poligono", edges_poli[i], f"grau_num={g}"))
# BR-470 / ponte: trechos trunk com ref BR-470
br = {e for e in range(E) if ("br470" in ref_de.get(e, "").lower().replace("-", "").replace(" ", "")) and hw[e].startswith("trunk")}
cenarios.append(("BR-470 / ponte Ibirama-Apiuna", "br470", br, "pendente_geometria (vao exato sem geometria); sem alternativa proxima (Serra da Guaricana)"))

print(f"{len(cenarios)} cenarios montados.")


# ============================ baseline (caminho mais rapido sem fechamento) ============================
def reconstruir(pred_row, origem):
    """nos de origem ate o destino (pred aponta para o destino, que foi a 'source' do dijkstra)."""
    caminho, x, lim = [origem], origem, 0
    while pred_row[x] >= 0 and lim < 100000:
        x = pred_row[x]; caminho.append(x); lim += 1
    return caminho


def caminho_edges(nos):
    return [aresta_entre[(nos[i], nos[i + 1])] for i in range(len(nos) - 1) if (nos[i], nos[i + 1]) in aresta_entre]


base = {}
for modo in ("carro", "pedestre"):
    mask = (carro_ok if modo == "carro" else pedest_ok) & ~loop
    dist0, pred0 = dijkstra(grafo(mask, modo), indices=dest_nodes, return_predecessors=True)
    edgeset, dist_m, time_s, pathedges = {}, {}, {}, {}
    for di in range(len(dest_nodes)):
        for o in origens:
            if not np.isfinite(dist0[di][o]):
                continue
            nos = reconstruir(pred0[di], o)
            ed = caminho_edges(nos)
            edgeset[(di, o)] = set(ed)
            pathedges[(di, o)] = ed
            dist_m[(di, o)] = float(sum(comp[e] for e in ed))
            time_s[(di, o)] = float(dist0[di][o])
    base[modo] = dict(mask=mask, dist0=dist0, edgeset=edgeset, dist_m=dist_m, time_s=time_s, pathedges=pathedges)
print("Baseline calculado (carro e pedestre).")


# ============================ A2: desvio por cenario x modal ============================
def pctl(a, q):
    return float(np.percentile(a, q)) if len(a) else np.nan


linhas_csv = []
exemplos_geo = []    # features p/ o geojson de exemplos
resumo_ruas = {}     # nome_cenario -> dados p/ o mapa (carro)

for (nome, tipo, S, obs) in cenarios:
    for modo in ("carro", "pedestre"):
        b = base[modo]
        Sm = {e for e in S if b["mask"][e]}            # so trechos que esse modal usaria
        n_trechos = len(S)
        metros = float(sum(comp[e] for e in S))
        if not Sm:
            linhas_csv.append(dict(cenario=nome, tipo=tipo, modal=modo, n_trechos_fechados=n_trechos,
                                   metros_fechados=round(metros, 1), n_pares_afetados=0, pct_sem_alternativa=np.nan,
                                   acrescimo_dist_mediana_m=np.nan, acrescimo_dist_p90_m=np.nan,
                                   acrescimo_tempo_mediana_min=np.nan, acrescimo_tempo_p90_min=np.nan,
                                   top3_ruas_desvio="", observacao=(obs + "; nenhum trecho usavel por este modal").strip("; ")))
            continue
        # pares afetados: baseline passa por algum trecho fechado
        afetados = [(di, o) for (di, o), es in b["edgeset"].items() if es & Sm]
        # grafo com o fechamento e dijkstra por destino
        mask1 = b["mask"].copy()
        for e in Sm:
            mask1[e] = False
        dist1, pred1 = dijkstra(grafo(mask1, modo), indices=dest_nodes, return_predecessors=True)
        d_time, sem_alt = [], 0
        recon = afetados if len(afetados) <= MAX_RECON else [afetados[i] for i in
                 np.random.default_rng(SEED).choice(len(afetados), MAX_RECON, replace=False)]
        reconset = set(recon)
        d_dist, ruas_cont, ex_cand = [], {}, []
        for (di, o) in afetados:
            t1 = dist1[di][o]
            if not np.isfinite(t1):
                sem_alt += 1
                continue
            dt = (t1 - b["time_s"][(di, o)]) / 60.0
            d_time.append(dt)
            if (di, o) in reconset:
                nos = reconstruir(pred1[di], o)
                ed = caminho_edges(nos)
                dd = float(sum(comp[e] for e in ed)) - b["dist_m"][(di, o)]
                d_dist.append(dd)
                novos = [e for e in ed if e not in b["edgeset"][(di, o)]]
                for nm in nomes_do_caminho(novos):
                    ruas_cont[nm] = ruas_cont.get(nm, 0) + 1
                ex_cand.append((dd, dt, di, o, ed))
        n_af = len(afetados)
        pct_sem = round(100.0 * sem_alt / n_af, 1) if n_af else np.nan
        top3 = "; ".join(nm for nm, _ in sorted(ruas_cont.items(), key=lambda kv: -kv[1])[:3])
        linhas_csv.append(dict(
            cenario=nome, tipo=tipo, modal=modo, n_trechos_fechados=n_trechos, metros_fechados=round(metros, 1),
            n_pares_afetados=n_af, pct_sem_alternativa=pct_sem,
            acrescimo_dist_mediana_m=round(pctl(d_dist, 50), 1), acrescimo_dist_p90_m=round(pctl(d_dist, 90), 1),
            acrescimo_tempo_mediana_min=round(pctl(d_time, 50), 2), acrescimo_tempo_p90_min=round(pctl(d_time, 90), 2),
            top3_ruas_desvio=top3, observacao=obs))
        # exemplo representativo (acrescimo de distancia mediano) - so para carro e cenarios de rua
        if modo == "carro":
            resumo_ruas[nome] = dict(tipo=tipo, S=S, pct_sem=pct_sem, med_dist=pctl(d_dist, 50),
                                     med_tempo=pctl(d_time, 50), top3=top3, n_af=n_af)
            if ex_cand and tipo in ("interdicao_buffer", "via_principal_buffer", "br470", "interdicao_inteira", "via_principal_inteira"):
                ex_cand.sort(key=lambda z: z[0])
                dd, dt, di, o, ed = ex_cand[len(ex_cand) // 2]
                orig_ed = base["carro"]["pathedges"][(di, o)]
                exemplos_geo.append((nome, di, o, round(dd, 1), round(dt, 2), orig_ed, ed, S))

print(f"{len(linhas_csv)} linhas de resultado; {len(exemplos_geo)} exemplos de desvio.")

# ============================ A3: desvios_sugeridos.csv ============================
dfcsv = pd.DataFrame(linhas_csv)
dfcsv.to_csv(DADOS / "desvios_sugeridos.csv", index=False, na_rep="NaN")
print("Gravado includes/dados/desvios_sugeridos.csv")

# ============================ A3: desvios_exemplos.geojson (EPSG:4326) ============================
to4326 = gpd.GeoSeries([], crs=vias.crs)


def edges_to_line4326(edges):
    pts = []
    for e in edges:
        pts.append(tuple(xy[u[e]])); pts.append(tuple(xy[v[e]]))
    if len(pts) < 2:
        return None
    ls = LineString(pts)
    return gpd.GeoSeries([ls], crs=vias.crs).to_crs(4326).iloc[0]


feats = []
for (nome, di, o, dd, dt, orig_ed, det_ed, S) in exemplos_geo:
    for rotulo, edges, cor in (("trecho_fechado", list(S), "#c0392b"),
                               ("caminho_original", orig_ed, "#888888"),
                               ("desvio", det_ed, "#2e8b57")):
        geom = edges_to_line4326(edges)
        if geom is None:
            continue
        feats.append({"type": "Feature",
                      "properties": {"cenario": nome, "parte": rotulo, "cor": cor,
                                     "acrescimo_dist_m": dd, "acrescimo_tempo_min": dt,
                                     "destino": dest_nomes[di], "ressalva": RESSALVA},
                      "geometry": mapping(geom)})
gj = {"type": "FeatureCollection", "name": "desvios_exemplos",
      "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}, "features": feats}
(RESULT / "desvios_exemplos.geojson").write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
print("Gravado resultados/desvios_exemplos.geojson")

# ============================ A3: mapa_desvios.html (folium) ============================
try:
    import folium
    riscos4326 = riscos.to_crs(4326)
    centro = riscos4326.geometry.union_all().centroid
    mapa = folium.Map(location=[centro.y, centro.x], zoom_start=14, tiles="OpenStreetMap", control_scale=True)
    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri, Maxar", name="Fundo: satelite", max_zoom=19).add_to(mapa)
    COR = {1: "#f4d03f", 2: "#e67e22", 3: "#c0392b"}
    folium.GeoJson(riscos4326[["grau_num", "geometry"]], name="Areas de risco",
                   style_function=lambda f: {"color": COR.get(f["properties"]["grau_num"], "#888"), "weight": 1,
                                             "fillColor": COR.get(f["properties"]["grau_num"], "#888"), "fillOpacity": 0.35}).add_to(mapa)
    # ruas interditadas (vermelho) + popup com o desvio de carro
    fg_int = folium.FeatureGroup(name="Ruas interditadas (fechamento)")
    for nome, info in resumo_ruas.items():
        if info["tipo"] not in ("interdicao_buffer", "via_principal_buffer", "br470"):
            continue
        edges = [e for e in info["S"]]
        if not edges:
            continue
        geom = edges_to_line4326(edges)
        if geom is None:
            continue
        top = info["top3"] or "sem nome no OSM"
        semalt = "sim" if (info["pct_sem"] and info["pct_sem"] > 0) else "nao"
        med_d = info["med_dist"]; med_t = info["med_tempo"]
        txt = (f"<b>Se fechar: {nome}</b><br>Desvio por: {top}<br>"
               f"Acrescimo mediano (carro): {0 if not np.isfinite(med_d) else round(med_d)} m, "
               f"{0 if not np.isfinite(med_t) else round(med_t,1)} min<br>"
               f"Sem alternativa proxima: {semalt}<br><i>{RESSALVA}</i>")
        folium.GeoJson(mapping(geom), style_function=lambda f: {"color": "#c0392b", "weight": 5, "opacity": 0.9},
                       popup=folium.Popup(txt, max_width=320)).add_to(fg_int)
    fg_int.add_to(mapa)
    # exemplos: desvio (verde) e original (cinza tracejado)
    fg_des = folium.FeatureGroup(name="Desvio sugerido (verde)")
    fg_ori = folium.FeatureGroup(name="Caminho original (cinza tracejado)")
    for (nome, di, o, dd, dt, orig_ed, det_ed, S) in exemplos_geo:
        g1 = edges_to_line4326(det_ed); g2 = edges_to_line4326(orig_ed)
        if g1 is not None:
            folium.GeoJson(mapping(g1), style_function=lambda f: {"color": "#2e8b57", "weight": 4, "opacity": 0.9},
                           tooltip=f"Desvio: {nome} (+{round(dd)} m, +{round(dt,1)} min)").add_to(fg_des)
        if g2 is not None:
            folium.GeoJson(mapping(g2), style_function=lambda f: {"color": "#888888", "weight": 3, "opacity": 0.8, "dashArray": "6,6"},
                           tooltip=f"Original: {nome}").add_to(fg_ori)
    fg_des.add_to(mapa); fg_ori.add_to(mapa)
    # pontos criticos
    pts4326 = pts.to_crs(4326)
    cores = {"hospital": "red", "bombeiros": "orange", "abrigo": "green", "defesa_civil": "purple", "ubs": "pink", "educacao": "blue"}
    fgp = folium.FeatureGroup(name="Pontos criticos")
    for _, r in pts4326.iterrows():
        folium.CircleMarker([r.geometry.y, r.geometry.x], radius=4, color=cores.get(str(r.get("grupo")), "gray"),
                            fill=True, fill_opacity=0.9, tooltip=f"{r.get('grupo','')}: {r.get('nome','')}").add_to(fgp)
    fgp.add_to(mapa)
    legenda = f"""<div style="position:fixed;bottom:20px;left:10px;z-index:9999;background:white;padding:8px 10px;
border:1px solid #888;border-radius:4px;font:12px sans-serif;line-height:1.4;max-width:300px">
<b>Desvios para planejamento</b><br>
<span style="border-top:5px solid #c0392b;display:inline-block;width:16px"></span> rua interditada (clique)<br>
<span style="border-top:4px solid #2e8b57;display:inline-block;width:16px"></span> desvio sugerido<br>
<span style="border-top:3px dashed #888;display:inline-block;width:16px"></span> caminho original<br>
<i>{RESSALVA}</i></div>"""
    mapa.get_root().html.add_child(folium.Element(legenda))
    folium.LayerControl(collapsed=False).add_to(mapa)
    mapa.save(str(RESULT / "mapa_desvios.html"))
    print("Gravado resultados/mapa_desvios.html")
except ImportError:
    print("(folium nao instalado: pulei o mapa HTML)")

# ============================ A3: fig_desvios.png (300 dpi) ============================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ruas_fig = [(n, i) for n, i in resumo_ruas.items() if i["tipo"] in ("interdicao_buffer", "via_principal_buffer")]
ruas_fig = [(n, i) for n, i in ruas_fig if i["n_af"] > 0]
if ruas_fig:
    nomes = [n.split(":")[1].split("(")[0].strip() for n, _ in ruas_fig]
    med = [i["med_dist"] if np.isfinite(i["med_dist"]) else 0 for _, i in ruas_fig]
    semalt = [i["pct_sem"] and i["pct_sem"] > 0 for _, i in ruas_fig]
    fig, ax = plt.subplots(figsize=(9, max(3, 0.45 * len(nomes))))
    cores = ["#d55e00" if s else "#0072b2" for s in semalt]   # laranja=sem alternativa, azul=ok (daltonico-ok)
    ax.barh(range(len(nomes)), med, color=cores)
    ax.set_yticks(range(len(nomes))); ax.set_yticklabels(nomes, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("acrescimo mediano de distancia no desvio - carro (m)")
    ax.set_title("Desvio por rua interditada (so trechos a <=40 m do risco)")
    ax.grid(axis="x", alpha=.3)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#0072b2", label="tem alternativa"), Patch(color="#d55e00", label="algum par sem alternativa")],
              fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(RESULT / "fig_desvios.png", dpi=300)
    print("Gravado resultados/fig_desvios.png")
else:
    print("(sem ruas com pares afetados para a figura)")

print("\nPRONTO.", RESSALVA)
