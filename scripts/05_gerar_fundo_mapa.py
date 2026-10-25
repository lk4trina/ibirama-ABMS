"""
PASSO 2d (opcional) - Gera uma IMAGEM de mapa real (ruas, relevo ou satélite) para ficar de fundo na simulação,
alinhada com a rede de ruas. *** Precisa de internet. Rode no SEU computador. ***

Instalação (uma vez):   pip install contextily

Uso (na pasta raiz do projeto):
    python scripts/05_gerar_fundo_mapa.py                    # mapa de ruas colorido (padrão)
    python scripts/05_gerar_fundo_mapa.py --fonte claro      # mapa de ruas em tons claros
    python scripts/05_gerar_fundo_mapa.py --fonte relevo     # mapa topográfico (curvas de nível, vegetação)
    python scripts/05_gerar_fundo_mapa.py --fonte satelite   # imagem de satélite
    python scripts/05_gerar_fundo_mapa.py --zoom 16 --largura 4000   # mais detalhe (mais lento)

Gera  dados/fundo_mapa.png  cobrindo EXATAMENTE a extensão da rede (dados/vias.shp).
Depois: copie o arquivo para Ibirama/includes/dados/ e, no topo do ibirama.gaml, troque
    bool usar_fundo_imagem <- false;     por     bool usar_fundo_imagem <- true;
(e deixe  usar_camadas_mapa  em false, para os desenhos vetoriais não cobrirem a imagem).

IMPORTANTE:
  * Isto só muda o DESENHO. Os agentes continuam andando pelas ruas do OpenStreetMap em vias.shp.
  * Fontes de mapa têm termos de uso: cite a fonte no artigo (a atribuição já vem escrita no canto da imagem).
        ruas/claro : (c) OpenStreetMap contributors / (c) CARTO
        relevo     : (c) OpenTopoMap, (c) OpenStreetMap contributors
        satelite   : Esri, Maxar, Earthstar Geographics e a comunidade de usuários GIS
  * Não use em volume: é para gerar a imagem uma vez e reaproveitá-la.
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--vias", default=None, help="shapefile das ruas (padrão: dados/vias.shp)")
ap.add_argument("--fonte", default="ruas", choices=["ruas", "claro", "relevo", "satelite"])
ap.add_argument("--zoom", type=int, default=15)
ap.add_argument("--largura", type=int, default=3000, help="largura da imagem em pixels")
ap.add_argument("--saida", default=None)
a = ap.parse_args()

vias_shp = Path(a.vias) if a.vias else RAIZ / "dados" / "vias.shp"
if not vias_shp.exists():
    sys.exit(f"Não encontrei {vias_shp}. Rode antes o scripts/02_baixar_rede_osm.py "
             f"(ou use --vias dados/vias_teste_SINTETICO.shp para testar).")
saida = Path(a.saida) if a.saida else RAIZ / "dados" / "fundo_mapa.png"

import contextily as ctx  # noqa: E402

FONTES = {
    "ruas": lambda: ctx.providers.OpenStreetMap.Mapnik,
    "claro": lambda: ctx.providers.CartoDB.Voyager,
    "relevo": lambda: ctx.providers.OpenTopoMap,
    "satelite": lambda: ctx.providers.Esri.WorldImagery,
}

vias = gpd.read_file(vias_shp)
x0, y0, x1, y1 = vias.total_bounds
w, h = x1 - x0, y1 - y0
print(f"Extensão da rede (m): largura {w:.0f}  altura {h:.0f}  CRS {vias.crs.to_string()}")

dpi = 100
fig = plt.figure(figsize=(a.largura / dpi, a.largura * h / w / dpi), dpi=dpi)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)
ax.axis("off")
print(f"Baixando o mapa ({a.fonte}, zoom {a.zoom}) ... pode levar um ou dois minutos")
ctx.add_basemap(ax, crs=vias.crs.to_string(), source=FONTES[a.fonte](), zoom=a.zoom, reset_extent=False)
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)
fig.savefig(saida, dpi=dpi)  # sem bbox_inches: mantém as proporções exatas da área
print(f"Imagem gravada em {saida}")
print("Copie para Ibirama/includes/dados/ e ligue 'usar_fundo_imagem' no ibirama.gaml.")
