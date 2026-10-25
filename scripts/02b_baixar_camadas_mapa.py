"""
PASSO 2b (opcional, só para deixar o mapa bonito) - Baixa prédios, rios, água e áreas verdes de Ibirama
do OpenStreetMap e grava shapefiles que o GAMA desenha no fundo da simulação.
*** Precisa de internet. Rode no SEU computador. ***

Uso (na pasta raiz do projeto, depois de instalar com  pip install -r requirements.txt):
    python scripts/02b_baixar_camadas_mapa.py

Gera em dados/:  predios.shp  agua.shp  rios.shp  verde.shp   (em metros, UTM 22S)
Depois, no topo do ibirama.gaml, troque
    bool usar_camadas_mapa <- false;
por
    bool usar_camadas_mapa <- true;
e copie esses arquivos (todas as extensões: .shp .shx .dbf .prj .cpg) para Ibirama/includes/dados/.

Isto NÃO altera a simulação: são só desenhos de fundo.
"""
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from shapely.geometry import box

RAIZ = Path(__file__).resolve().parent.parent
CRS_METROS = "EPSG:31982"
MARGEM_M = 700

riscos = gpd.read_file(RAIZ / "dados" / "riscos.shp")
x0, y0, x1, y1 = riscos.total_bounds
x0, y0, x1, y1 = x0 - MARGEM_M, y0 - MARGEM_M, x1 + MARGEM_M, y1 + MARGEM_M
caixa_m = box(x0, y0, x1, y1)
caixa = gpd.GeoSeries([caixa_m], crs=CRS_METROS).to_crs(4326).total_bounds  # oeste, sul, leste, norte
oeste, sul, leste, norte = caixa
print(f"Área: lon {oeste:.4f}..{leste:.4f}  lat {sul:.4f}..{norte:.4f}")


def baixar(tags, rotulo):
    print(f"Baixando {rotulo} ...", flush=True)
    try:
        g = ox.features_from_bbox(bbox=(oeste, sul, leste, norte), tags=tags)
    except Exception as e:  # nada encontrado ou falha de rede
        print(f"  (sem resultado para {rotulo}: {type(e).__name__})")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return g.reset_index(drop=True)


def preparar(g, tipo, poligonos=True, area_min=0.0, simplificar=1.0):
    """Mantém só poligonos (ou só linhas), em metros, recortado na caixa, com um campo 'tipo'."""
    if len(g) == 0:
        return gpd.GeoDataFrame({"tipo": []}, geometry=[], crs=CRS_METROS)
    familia = ["Polygon", "MultiPolygon"] if poligonos else ["LineString", "MultiLineString"]
    g = g[g.geom_type.isin(familia)]
    g = gpd.GeoDataFrame({"tipo": [tipo] * len(g)}, geometry=list(g.geometry), crs=g.crs).to_crs(CRS_METROS)
    g["geometry"] = g.geometry.intersection(caixa_m)
    g = g[~g.geometry.is_empty & g.geometry.notna()]
    if poligonos and area_min:
        g = g[g.geometry.area >= area_min]
    g["geometry"] = g.geometry.simplify(simplificar)
    return g.reset_index(drop=True)


def gravar(g, nome):
    """O GAMA exige que o arquivo exista: se a camada veio vazia, grava um ponto mínimo invisível."""
    if len(g) == 0:
        g = gpd.GeoDataFrame({"tipo": ["vazio"]}, geometry=[box(x0, y0, x0 + 1, y0 + 1)], crs=CRS_METROS)
        print(f"  {nome}: vazio (gravado um quadrado de 1 m para o GAMA não reclamar)")
    else:
        print(f"  {nome}: {len(g)} objetos")
    g.to_file(RAIZ / "dados" / nome)


predios = preparar(baixar({"building": True}, "prédios"), "predio", area_min=25.0)
agua = preparar(baixar({"natural": "water", "landuse": "reservoir"}, "água (lagos e rios largos)"), "agua", area_min=50.0, simplificar=2.0)
rios = preparar(baixar({"waterway": ["river", "stream", "canal"]}, "rios e córregos"), "rio", poligonos=False, simplificar=2.0)
verde = preparar(baixar({"landuse": ["forest", "grass", "meadow", "village_green"], "natural": ["wood", "scrub", "grassland"],
                         "leisure": ["park", "garden"]}, "áreas verdes"), "verde", area_min=500.0, simplificar=3.0)

print("Gravando shapefiles em dados/ ...")
gravar(predios, "predios.shp")
gravar(agua, "agua.shp")
gravar(rios, "rios.shp")
gravar(verde, "verde.shp")
print("Pronto. Agora ligue 'usar_camadas_mapa' no ibirama.gaml e copie os arquivos para includes/dados/.")
