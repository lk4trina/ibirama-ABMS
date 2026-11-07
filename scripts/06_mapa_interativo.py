"""
PASSO 2e (opcional) - Gera um MAPA INTERATIVO (zoom e arrastar, como o Google Meu Mapas da Defesa Civil)
em um arquivo HTML que abre no navegador. Mostra: áreas de risco (clique para ver grau/tipo/fonte),
ruas da simulação, pontos críticos e, se existirem, os resultados.
*** Precisa de internet para carregar o mapa de fundo ao abrir o HTML. ***

Instalação (uma vez):   pip install folium      (já está no requirements.txt)

Uso (na pasta raiz do projeto):
    python scripts/06_mapa_interativo.py
    python scripts/06_mapa_interativo.py --vias includes/dados/vias_teste_SINTETICO.shp --pontos includes/dados/pontos_criticos_TESTE.shp

Gera  resultados/mapa_interativo.html  (dê duplo clique). No canto superior direito há o seletor de camadas:
fundo de ruas, satélite ou relevo, e liga/desliga de cada camada.

Observação: é uma visualização À PARTE do GAMA (o GAMA não tem mapa com zoom de resolução infinita).
Use este mapa para explorar a área, apresentar e conferir ruas; use o GAMA para rodar a simulação.
Os pontos críticos *_TESTE são fictícios.
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd

try:
    import folium
except ImportError:
    sys.exit("Falta instalar o folium:  pip install folium")

RAIZ = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--vias", default=None)
ap.add_argument("--pontos", default=None)
ap.add_argument("--saida", default=None)
a = ap.parse_args()

dados = RAIZ / "includes" / "dados"
riscos_shp = dados / "riscos.shp"
vias_shp = Path(a.vias) if a.vias else dados / "vias.shp"
if a.pontos:
    pontos_shp = Path(a.pontos)
else:
    pontos_shp = dados / "pontos_criticos.shp"
    if not pontos_shp.exists():
        pontos_shp = dados / "pontos_criticos_TESTE.shp"
saida = Path(a.saida) if a.saida else RAIZ / "resultados" / "mapa_interativo.html"
saida.parent.mkdir(exist_ok=True)

if not riscos_shp.exists():
    sys.exit(f"Não encontrei {riscos_shp}")

riscos = gpd.read_file(riscos_shp).to_crs(4326)
centro = riscos.geometry.union_all().centroid if hasattr(riscos.geometry, "union_all") else riscos.geometry.unary_union.centroid
m = folium.Map(location=[centro.y, centro.x], zoom_start=14, tiles=None, control_scale=True)

folium.TileLayer("OpenStreetMap", name="Fundo: ruas (OSM)").add_to(m)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri, Maxar, Earthstar Geographics", name="Fundo: satélite", max_zoom=19).add_to(m)
folium.TileLayer(
    tiles="https://tile.opentopomap.org/{z}/{x}/{y}.png",
    attr="OpenTopoMap, OpenStreetMap contributors", name="Fundo: relevo", max_zoom=17).add_to(m)

# ---- ruas da simulação (só desenha; o arquivo é simplificado para o navegador não travar)
if vias_shp.exists():
    vias = gpd.read_file(vias_shp).to_crs(4326)
    vias["geometry"] = vias.geometry.simplify(0.000005)
    campos = [c for c in ["highway", "comp"] if c in vias.columns]
    folium.GeoJson(
        vias[campos + ["geometry"]], name="Ruas da simulação (OSM)",
        style_function=lambda f: {"color": "#444444", "weight": 2, "opacity": 0.8},
        tooltip=folium.GeoJsonTooltip(fields=campos, aliases=["tipo de via", "comprimento (m)"][:len(campos)]) if campos else None,
        show=True).add_to(m)
else:
    print(f"(sem ruas: {vias_shp} não existe; rode o scripts/02_baixar_rede_osm.py)")

# ---- áreas de risco
COR = {1: "#f4d03f", 2: "#e67e22", 3: "#c0392b"}
campos_r = [c for c in ["id", "grau", "tipo_txt", "fonte"] if c in riscos.columns]
folium.GeoJson(
    riscos[campos_r + ["grau_num", "geometry"]], name="Áreas de risco (Defesa Civil)",
    style_function=lambda f: {"color": COR.get(f["properties"]["grau_num"], "#888"), "weight": 2,
                              "fillColor": COR.get(f["properties"]["grau_num"], "#888"), "fillOpacity": 0.45},
    tooltip=folium.GeoJsonTooltip(fields=campos_r, aliases=["id", "grau", "tipo", "fonte"][:len(campos_r)])).add_to(m)

# ---- pontos críticos
if pontos_shp.exists():
    pts = gpd.read_file(pontos_shp).to_crs(4326)
    cores = {"hospital": "red", "bombeiros": "orange", "abrigo": "green", "defesa_civil": "purple"}
    fg = folium.FeatureGroup(name=f"Pontos críticos ({pontos_shp.name})")
    for _, r in pts.iterrows():
        folium.Marker([r.geometry.y, r.geometry.x], tooltip=f"{r.get('tipo', '')}: {r.get('nome', '')}",
                      icon=folium.Icon(color=cores.get(str(r.get("tipo")), "blue"))).add_to(fg)
    fg.add_to(m)

# ---- semáforo(s) informado(s) pela equipe (só aparece no mapa; o modelo ainda não usa atraso de semáforo)
sem_csv = dados / "semaforos.csv"
if sem_csv.exists():
    import pandas as pd
    fg2 = folium.FeatureGroup(name="Semáforo")
    for _, r in pd.read_csv(sem_csv).iterrows():
        folium.Marker([r.lat, r.lon], tooltip=str(r.nome), icon=folium.Icon(color="darkblue", icon="info-sign")).add_to(fg2)
    fg2.add_to(m)

legenda = """
<div style="position:fixed;bottom:25px;left:10px;z-index:9999;background:white;padding:8px 10px;
border:1px solid #888;border-radius:4px;font:12px sans-serif;line-height:1.5">
<b>Áreas de risco</b><br>
<span style="background:#f4d03f;padding:0 8px"></span> Médio<br>
<span style="background:#e67e22;padding:0 8px"></span> Alto<br>
<span style="background:#c0392b;padding:0 8px"></span> Muito alto<br>
<span style="border-top:3px solid #444;display:inline-block;width:16px"></span> Ruas da simulação
</div>"""
m.get_root().html.add_child(folium.Element(legenda))
folium.LayerControl(collapsed=False).add_to(m)
m.save(str(saida))
print(f"Mapa gravado em {saida}\nAbra o arquivo no navegador (precisa de internet para o fundo).")
