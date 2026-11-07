"""
PASSO 2c - Tabela de apoio com os NOMES das ruas, SEM mexer no vias.shp.

O vias.shp (1.182 trechos) nao tem nome de rua (so highway, carro, pedest, comp). Este script:
  1. Baixa a rede do OpenStreetMap guardando os campos `name` e `ref` (ex.: SC-340, BR-470).
  2. Associa CADA trecho do vias.shp ao trecho do OSM mais sobreposto (buffer de 5 m, maior
     comprimento sobreposto, no CRS EPSG:31982).
  3. Grava includes/dados/vias_nomes.csv  (id_trecho, name, ref, highway, comp) - uma linha por trecho.
  4. Cruza com as ruas informadas pela Defesa Civil (interdicoes_defesa_civil.csv e
     vias_principais_defesa_civil.csv) e acrescenta nelas as colunas ids_trechos e status_associacao.

*** Precisa de internet (OSM/Overpass). Rode no SEU computador. ***
  - Se o Overpass der timeout, defina um espelho:  set OVERPASS_URL=https://overpass.kumi.systems/api
  - Reexecucao: se includes/dados/vias_nomes.csv ja existir, o download e PULADO (use --forcar para baixar de novo).

IMPORTANTE: isto NAO altera o vias.shp, nem o numero de trechos, nem o modelo GAMA. So gera dados de apoio.
"""
import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import STRtree

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "includes" / "dados"
CRS_METROS = "EPSG:31982"
MARGEM_M = 700
BUFFER_M = 5.0
MIN_SOBREPOSICAO = 0.30   # exige cobrir ao menos 30% do comprimento do trecho para aceitar o nome

ap = argparse.ArgumentParser()
ap.add_argument("--forcar", action="store_true", help="baixa do OSM de novo mesmo se vias_nomes.csv existir")
args = ap.parse_args()

vias = gpd.read_file(DADOS / "vias.shp")
if vias.crs is None or vias.crs.to_epsg() != 31982:
    vias = vias.to_crs(CRS_METROS)
n = len(vias)
tab_path = DADOS / "vias_nomes.csv"


def txt(v):
    """Junta listas (name/ref podem vir como lista no OSM), descarta nan/None, remove duplicatas."""
    if isinstance(v, (list, tuple)):
        vals = [str(x).strip() for x in v if x is not None and str(x).strip().lower() != "nan"]
        return "; ".join(dict.fromkeys(vals))
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


# ---------------------------------------------------------------- 1-3) tabela de nomes ----------
if tab_path.exists() and not args.forcar:
    print(f"Ja existe {tab_path.name}; pulando o download (use --forcar para refazer).")
    tab = pd.read_csv(tab_path, dtype=str).fillna("")
    tab["id_trecho"] = tab["id_trecho"].astype(int)
    qualidade = None
else:
    import osmnx as ox
    ox.settings.requests_timeout = 120
    mirror = os.environ.get("OVERPASS_URL")
    if mirror:
        ox.settings.overpass_url = mirror
        print(f"Usando espelho Overpass: {mirror}")

    riscos = gpd.read_file(DADOS / "riscos.shp")
    x0, y0, x1, y1 = riscos.total_bounds
    caixa = gpd.GeoSeries.from_xy([x0 - MARGEM_M, x1 + MARGEM_M], [y0 - MARGEM_M, y1 + MARGEM_M],
                                  crs=CRS_METROS).to_crs(4326)
    oeste, sul, leste, norte = caixa.x.min(), caixa.y.min(), caixa.x.max(), caixa.y.max()
    print(f"Baixando OSM entre lon {oeste:.4f}..{leste:.4f} / lat {sul:.4f}..{norte:.4f} ...")
    try:
        G = ox.graph_from_bbox((oeste, sul, leste, norte), network_type="all", simplify=True, retain_all=True)
    except Exception as e:
        sys.exit(f"PARANDO: falha ao baixar do OSM/Overpass ({e}).\n"
                 f"Verifique a internet ou defina OVERPASS_URL com um espelho e rode de novo.")
    edges = ox.convert.graph_to_gdfs(G, nodes=False).reset_index(drop=True).to_crs(CRS_METROS)
    edges["name_txt"] = edges["name"].map(txt) if "name" in edges.columns else ""
    edges["ref_txt"] = edges["ref"].map(txt) if "ref" in edges.columns else ""
    print(f"OSM: {len(edges)} trechos baixados ({(edges['name_txt'] != '').sum()} com nome).")

    geoms = list(edges.geometry.values)
    nomes = edges["name_txt"].tolist()
    refs = edges["ref_txt"].tolist()
    tree = STRtree(geoms)

    rows, dists, ambig = [], [], 0
    for i in range(n):
        g = vias.geometry.values[i]
        comp = g.length
        buf = g.buffer(BUFFER_M)
        idx = np.atleast_1d(tree.query(buf, predicate="intersects"))
        best, best_ov = None, 0.0
        nomes_ov = {}
        for j in idx:
            ov = geoms[j].intersection(buf).length
            if nomes[j]:
                nomes_ov[nomes[j]] = max(nomes_ov.get(nomes[j], 0.0), ov)
            if ov > best_ov:
                best_ov, best = ov, j
        name = ref = ""
        if best is not None and best_ov >= MIN_SOBREPOSICAO * comp:
            name, ref = nomes[best], refs[best]
            dists.append(g.hausdorff_distance(geoms[best]))
            fortes = [k for k, o in nomes_ov.items() if o >= 0.5 * best_ov]
            if len(fortes) >= 2:
                ambig += 1
        rows.append({"id_trecho": i, "name": name, "ref": ref,
                     "highway": txt(vias["highway"].values[i]) if "highway" in vias.columns else "",
                     "comp": round(float(comp), 1)})
    tab = pd.DataFrame(rows)
    tab.to_csv(tab_path, index=False, encoding="utf-8")
    qualidade = (dists, ambig)
    print(f"Gravado {tab_path}")

com_nome = int((tab["name"].astype(str) != "").sum())
com_ref = int((tab["ref"].astype(str) != "").sum())
sem_nome = n - com_nome
print("\n===== Cobertura de nomes =====")
print(f"Trechos no vias.shp: {n}")
print(f"  com nome: {com_nome} ({100*com_nome/n:.1f}%)")
print(f"  com ref : {com_ref} ({100*com_ref/n:.1f}%)")
print(f"  sem nome: {sem_nome} ({100*sem_nome/n:.1f}%)")
if qualidade and qualidade[0]:
    d, amb = qualidade
    print(f"  qualidade da associacao (Hausdorff): media {np.mean(d):.1f} m, mediana {np.median(d):.1f} m, max {np.max(d):.1f} m")
    print(f"  trechos ambiguos (2+ nomes concorrentes no buffer): {amb}")

# ---------------------------------------------------------------- 4) cruzamento Defesa Civil ----
STOP = {"rua", "avenida", "av", "r", "de", "do", "da", "dos", "das", "e", "", "estrada", "travessa"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.,/]", " ", s)
    s = re.sub(r"\bxv\b", "15", s)
    s = re.sub(r"\bquinze\b", "15", s)
    s = re.sub(r"\b(dr|doutor)\b", "doutor", s)
    s = re.sub(r"\bpe\b", "padre", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def toks(s):
    return [t for t in norm(s).split() if t not in STOP]


def refs_no_texto(*textos):
    achados = set()
    for t in textos:
        for m in re.findall(r"\b(br|sc)[-\s]?(\d{3})\b", norm(t)):
            achados.add(m[0] + m[1])   # ex.: br470, sc340
    return achados


tab_nome_toks = [toks(x) for x in tab["name"].tolist()]
tab_ref_norm = [re.sub(r"[^a-z0-9]", "", norm(x)) for x in tab["ref"].tolist()]


def lev(a, b):
    """Distancia de edicao (para tolerar grafias: Aurich/Aurcih, Getulio com/sem Doutor)."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 2:
        return 9
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[len(b)]


def token_perto(q, t):
    if q == t:
        return True
    if min(len(q), len(t)) >= 5 and (q.startswith(t) or t.startswith(q)):
        return True
    limite = 2 if max(len(q), len(t)) >= 6 else (1 if max(len(q), len(t)) >= 4 else 0)
    return lev(q, t) <= limite


def casa_todos(qt, nt):
    """So casa se TODOS os tokens da rua informada tiverem um token proximo no trecho."""
    return bool(qt) and bool(nt) and all(any(token_perto(q, t) for t in nt) for q in qt)


def achar(nome, aux=""):
    """Retorna (ids, nomes_distintos, por_ref) dos trechos que batem com a rua informada."""
    qt = toks(nome)
    refs_q = refs_no_texto(nome, aux)
    ids, nomes_set, por_ref = [], set(), False
    for i in range(len(tab)):
        if casa_todos(qt, tab_nome_toks[i]):
            ids.append(int(tab["id_trecho"].values[i]))
            nomes_set.add(tab["name"].values[i])
        elif refs_q and tab_ref_norm[i] and tab_ref_norm[i] in refs_q:
            ids.append(int(tab["id_trecho"].values[i]))
            por_ref = True
    return sorted(set(ids)), sorted(nomes_set), por_ref


def comprimento(ids):
    if not ids:
        return 0.0
    return round(float(tab[tab["id_trecho"].isin(ids)]["comp"].astype(float).sum()), 1)


def highways(ids):
    if not ids:
        return ""
    vals = tab[tab["id_trecho"].isin(ids)]["highway"].astype(str)
    return "; ".join(sorted(set(v for v in vals if v)))


def processa_csv(caminho, col_nome, col_aux):
    df = pd.read_csv(caminho, dtype=str).fillna("")
    ids_col, status_col = [], []
    print(f"\n===== {caminho.name} =====")
    for _, r in df.iterrows():
        nome, aux = r[col_nome], (r[col_aux] if col_aux in df.columns else "")
        ids, nomes_set, por_ref = achar(nome, aux)
        if not ids:
            status = "nao_encontrado"
        elif len(nomes_set) >= 2:
            status = "parcial"      # bateu, mas com nomes concorrentes (conferir manualmente)
        elif por_ref and not nomes_set and "ponte" in toks(nome):
            status = "parcial"      # achou a rodovia (ref), mas nao o vao especifico da ponte
        else:
            status = "associado"
        ids_col.append(";".join(str(x) for x in ids))
        status_col.append(status)
        det = f"{len(ids)} trecho(s), {comprimento(ids):.0f} m, tipos [{highways(ids)}]" if ids else "-"
        extra = f" nomes={nomes_set}" if nomes_set else (" (so por ref)" if por_ref else "")
        print(f"  {nome:28s} -> {status:14s} {det}{extra}")
    df["ids_trechos"] = ids_col
    df["status_associacao"] = status_col
    df.to_csv(caminho, index=False, encoding="utf-8")
    print(f"  (atualizado com ids_trechos e status_associacao)")
    return df


processa_csv(DADOS / "interdicoes_defesa_civil.csv", "via", "bairros")
processa_csv(DADOS / "vias_principais_defesa_civil.csv", "nome", "observacao")

# ---------------------------------------------------------------- 6f) pendencias do video --------
print("\n===== Pendencias citadas no video (nao estao nas CSVs) =====")
for nome in ["Rua Tiradentes", "Areado", "Loteamento Luizinho"]:
    ids, nomes_set, _ = achar(nome)
    if ids:
        print(f"  {nome}: encontrado na tabela de nomes -> {len(ids)} trecho(s), {comprimento(ids):.0f} m, nomes={nomes_set}")
    else:
        print(f"  {nome}: PENDENTE (nao encontrado na tabela de nomes; Areado/Luizinho sao areas/bairros, nao ruas)")
