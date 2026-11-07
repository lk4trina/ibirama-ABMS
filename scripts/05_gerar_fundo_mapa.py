"""
PASSO 2d (opcional) - Gera uma IMAGEM de mapa real (ruas, relevo ou satelite) para ficar de fundo na
simulacao, alinhada com a rede de ruas. *** Precisa de internet. Rode no SEU computador. ***

Instalacao (uma vez):   pip install contextily pillow

Uso (na pasta raiz do projeto):
    python scripts/05_gerar_fundo_mapa.py                      # fundo leve (jpg) do mapa de ruas (padrao)
    python scripts/05_gerar_fundo_mapa.py --fonte claro        # mapa de ruas em tons claros
    python scripts/05_gerar_fundo_mapa.py --fonte relevo       # mapa topografico (relevo, vegetacao)
    python scripts/05_gerar_fundo_mapa.py --fonte satelite     # imagem de satelite
    python scripts/05_gerar_fundo_mapa.py --formato png        # grava PNG quantizado em vez de JPEG
    python scripts/05_gerar_fundo_mapa.py --clarear 0.30       # clareia 30%% (ruas coloridas se destacam mais)
    python scripts/05_gerar_fundo_mapa.py --largura 3200 --qualidade 85

Gera, por padrao, uma imagem LEVE (alvo < 3 MB) cobrindo EXATAMENTE a extensao da rede
(includes/dados/vias.shp), com nome previsivel  includes/dados/fundo_mapa_leve.jpg.
O ibirama.gaml usa essa imagem automaticamente se ela existir (file_exists); senao cai no fundo vetorial.

IMPORTANTE:
  * Isto so muda o DESENHO. Os agentes continuam andando pelas ruas do OpenStreetMap em vias.shp.
  * Fontes de mapa tem termos de uso: cite a fonte no artigo (a atribuicao ja vem escrita no canto da imagem).
        ruas/claro : (c) OpenStreetMap contributors / (c) CARTO
        relevo     : (c) OpenTopoMap, (c) OpenStreetMap contributors
        satelite   : Esri, Maxar, Earthstar Geographics e a comunidade de usuarios GIS
  * Nao use em volume: e para gerar a imagem uma vez e reaproveita-la.
"""
import argparse
import io
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--vias", default=None, help="shapefile das ruas (padrao: includes/dados/vias.shp)")
ap.add_argument("--fonte", default="ruas", choices=["ruas", "claro", "relevo", "satelite"])
ap.add_argument("--formato", default="jpg", choices=["jpg", "png"], help="formato de saida (padrao: jpg)")
ap.add_argument("--zoom", type=int, default=15)
ap.add_argument("--largura", type=int, default=2800, help="largura da imagem em pixels (2400-3200 = leve)")
ap.add_argument("--qualidade", type=int, default=82, help="qualidade do JPEG (80-85 = leve e nitido)")
ap.add_argument("--clarear", type=float, default=0.0,
                help="0 a 1: camada branca semitransparente para dar contraste as ruas (ex.: 0.30)")
ap.add_argument("--saida", default=None, help="caminho de saida (padrao: includes/dados/fundo_mapa_leve.<fmt>)")
a = ap.parse_args()

vias_shp = Path(a.vias) if a.vias else RAIZ / "includes" / "dados" / "vias.shp"
if not vias_shp.exists():
    sys.exit(f"Nao encontrei {vias_shp}. Rode antes o scripts/02_baixar_rede_osm.py "
             f"(ou use --vias includes/dados/vias_teste_SINTETICO.shp para testar).")
saida = Path(a.saida) if a.saida else RAIZ / "includes" / "dados" / f"fundo_mapa_leve.{a.formato}"

import contextily as ctx  # noqa: E402
from PIL import Image  # noqa: E402

# Obs.: CartoDB passou a exigir API key; por isso "claro" usa Esri (gratuito, sem chave).
FONTES = {
    "ruas": lambda: ctx.providers.OpenStreetMap.Mapnik,
    "claro": lambda: ctx.providers.Esri.WorldGrayCanvas,
    "relevo": lambda: ctx.providers.OpenTopoMap,
    "satelite": lambda: ctx.providers.Esri.WorldImagery,
}

vias = gpd.read_file(vias_shp)
x0, y0, x1, y1 = vias.total_bounds
w, h = x1 - x0, y1 - y0
print(f"Extensao da rede (m): largura {w:.0f}  altura {h:.0f}  CRS {vias.crs.to_string()}")

dpi = 100
fig = plt.figure(figsize=(a.largura / dpi, a.largura * h / w / dpi), dpi=dpi)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)
ax.axis("off")
print(f"Baixando o mapa ({a.fonte}, zoom {a.zoom}) ... pode levar um ou dois minutos")
ctx.add_basemap(ax, crs=vias.crs.to_string(), source=FONTES[a.fonte](), zoom=a.zoom, reset_extent=False)
# Clareia (camada branca semitransparente) para as ruas coloridas e os icones se destacarem.
if a.clarear > 0:
    ax.add_patch(Rectangle((x0, y0), w, h, facecolor="white", edgecolor="none",
                           alpha=min(1.0, a.clarear), zorder=10))
# Mantem EXATAMENTE o retangulo da rede (mesmo envelope que o GAMA usa em world.shape = envelope(vias)).
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)

# Renderiza para memoria e grava leve (JPEG com qualidade, ou PNG quantizado).
buf = io.BytesIO()
fig.savefig(buf, format="png", dpi=dpi)  # sem bbox_inches: preserva as proporcoes exatas da area
buf.seek(0)
img = Image.open(buf)
saida.parent.mkdir(parents=True, exist_ok=True)
if a.formato == "jpg":
    img.convert("RGB").save(saida, format="JPEG", quality=a.qualidade, optimize=True, progressive=True)
else:
    img.convert("RGB").quantize(colors=256, method=Image.FASTOCTREE).save(saida, format="PNG", optimize=True)

mb = saida.stat().st_size / 1_048_576
print(f"Imagem gravada em {saida}  ({img.width}x{img.height} px, {mb:.2f} MB)")
if mb >= 3:
    print("AVISO: ficou com 3 MB ou mais. Reduza --largura ou --qualidade, ou use --formato jpg.")
print("Para o GAMA usar: deixe o arquivo em includes/dados/fundo_mapa_leve.jpg (ja e o padrao).")
