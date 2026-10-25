"""
PASSO 2b - Converte a lista de pontos críticos (hospital, bombeiros, abrigos) em shapefile para o GAMA.

Preencha dados/pontos_criticos.csv com as colunas:   tipo,nome,lat,lon
  tipo  : hospital | bombeiros | defesa_civil | abrigo   (exatamente assim, minúsculo, sem acento)
          hospital e bombeiros são obrigatórios; abrigo e defesa_civil são opcionais
  nome  : nome do local
  lat,lon: coordenadas em graus decimais (no Google Maps: clique com o botão direito no local e copie
           os números que aparecem, ex.: -27.0572, -49.5186)
Exemplo:
    tipo,nome,lat,lon
    hospital,(nome do hospital),-27.0000,-49.0000   <- números de exemplo, use os reais

Rodar:  python scripts/04_pontos_criticos_para_shapefile.py
Gera dados/pontos_criticos.shp (metros, UTM 22S). O simulador Python lê o CSV direto.
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
csv = RAIZ / "dados" / "pontos_criticos.csv"
if not csv.exists():
    sys.exit(f"Crie {csv} com as colunas tipo,nome,lat,lon (veja o exemplo no topo deste arquivo).")
df = pd.read_csv(csv)
df["tipo"] = df["tipo"].str.strip().str.lower()
VALIDOS = {"hospital", "bombeiros", "defesa_civil", "abrigo"}
ruins = set(df["tipo"]) - VALIDOS
if ruins:
    sys.exit(f"Tipos inválidos: {ruins}. Use: {', '.join(sorted(VALIDOS))}.")
faltam = {"hospital", "bombeiros"} - set(df["tipo"])
if faltam:
    sys.exit(f"Falta pelo menos um ponto dos tipos: {faltam}")
if not df["lat"].between(-27.2, -26.9).all() or not df["lon"].between(-49.7, -49.3).all():
    sys.exit("Coordenadas fora da região de Ibirama: confira se lat/lon não estão trocadas.")
g = gpd.GeoDataFrame(df[["tipo", "nome"]], geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326").to_crs("EPSG:31982")
g.to_file(RAIZ / "dados" / "pontos_criticos.shp")
if "abrigo" not in set(df["tipo"]):
    print("AVISO: nenhum abrigo informado. As métricas de acesso a abrigo ficam vazias (NaN) até haver coordenadas.")
print(f"{len(g)} pontos gravados em dados/pontos_criticos.shp:")
print(df.tipo.value_counts().to_string())
