"""
PASSO 2 - Baixa as ruas REAIS de Ibirama (OpenStreetMap) e grava dados/vias.shp.
*** Precisa de internet. Rode no SEU computador. ***

Instalação (uma vez):
    pip install osmnx geopandas

Uso (na pasta raiz do projeto):
    python scripts/02_baixar_rede_osm.py

O que faz:
  1. Lê a extensão dos polígonos de risco e acrescenta uma margem de 700 m.
  2. Baixa do OpenStreetMap todas as vias dessa área (ruas, vielas, escadarias, caminhos).
  3. Mantém só a maior parte conectada (ruas isoladas não servem para rota).
  4. Reprojeta para metros (UTM 22S) e grava com os campos:
        highway : tipo da via no OSM (primary, residential, footway, ...)
        carro   : 1 se carros e motos podem usar (0 = calçada, escada, caminho)
        pedest  : 1 se pedestres podem usar
        comp    : comprimento em metros
Observações / limitações (citar no artigo):
  * O sentido único (oneway) é ignorado: todo trecho é bidirecional.
  * Qualidade do OSM em Ibirama não foi auditada. Confira no QGIS/mapa e corrija trechos críticos.
"""
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox

RAIZ = Path(__file__).resolve().parent.parent
CRS_METROS = "EPSG:31982"
MARGEM_M = 700

riscos = gpd.read_file(RAIZ / "dados" / "riscos.shp")  # já em metros
x0, y0, x1, y1 = riscos.total_bounds
caixa = gpd.GeoSeries.from_xy([x0 - MARGEM_M, x1 + MARGEM_M], [y0 - MARGEM_M, y1 + MARGEM_M], crs=CRS_METROS).to_crs(4326)
oeste, sul = caixa.x.min(), caixa.y.min()
leste, norte = caixa.x.max(), caixa.y.max()
print(f"Baixando vias entre lon {oeste:.4f}..{leste:.4f} e lat {sul:.4f}..{norte:.4f} (pode levar alguns minutos)")

G = ox.graph_from_bbox((oeste, sul, leste, norte), network_type="all", simplify=True, retain_all=True)
G = ox.convert.to_undirected(G)
maior = max(nx.connected_components(G), key=len)
G = G.subgraph(maior).copy()
arestas = ox.convert.graph_to_gdfs(G, nodes=False).reset_index(drop=True)


def tipo_principal(h):
    if isinstance(h, list):
        h = h[0]
    return str(h)


arestas["highway"] = arestas["highway"].map(tipo_principal)
NAO_VEICULO = {"footway", "path", "steps", "pedestrian", "cycleway", "bridleway", "corridor", "elevator"}
NAO_PEDESTRE = {"motorway", "motorway_link", "trunk", "trunk_link"}
arestas["carro"] = (~arestas.highway.isin(NAO_VEICULO)).astype(int)
arestas["pedest"] = (~arestas.highway.isin(NAO_PEDESTRE)).astype(int)
arestas = arestas.to_crs(CRS_METROS)
arestas["comp"] = arestas.geometry.length.round(1)
vias = arestas[["highway", "carro", "pedest", "comp", "geometry"]]
vias.to_file(RAIZ / "dados" / "vias.shp")
print(f"{len(vias)} trechos gravados em dados/vias.shp")
print(vias.highway.value_counts().head(10).to_string())
