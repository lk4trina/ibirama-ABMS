"""
PASSO 1 - Converte o mapa de áreas de risco (KMZ) em arquivos que o GAMA lê.

O que faz:
  1. Abre o KMZ e lê os 49 polígonos de risco.
  2. Extrai, do texto da descrição, o grau de risco, a tipologia e a fonte do mapeamento.
  3. Classifica cada polígono em três famílias de evento que o modelo usa:
       alaga = inundação / alagamento / enxurrada
       eros  = erosão fluvial / solapamento de margem
       desl  = deslizamento / queda de blocos / fluxo de detritos / rastejo
     (um polígono pode ter mais de uma família)
  4. Reprojeta para metros (SIRGAS 2000 / UTM 22S, EPSG:31982), porque o GAMA trabalha em metros.
  5. Grava includes/dados/riscos.shp (para o GAMA) e includes/dados/riscos_wgs84.geojson (para o QGIS / mapas).

Como rodar (na pasta raiz do projeto):
    python scripts/01_kmz_para_shapefile.py
"""
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd
from shapely.geometry import Polygon

RAIZ = Path(__file__).resolve().parent.parent
KMZ = RAIZ / "includes" / "dados" / "AREAS_DE_RISCO_IBIRAMA.kmz"
SAIDA_SHP = RAIZ / "includes" / "dados" / "riscos.shp"
SAIDA_GEOJSON = RAIZ / "includes" / "dados" / "riscos_wgs84.geojson"
CRS_METROS = "EPSG:31982"  # SIRGAS 2000 / UTM zona 22S (Ibirama fica nesta zona)

K = "{http://www.opengis.net/kml/2.2}"
GRAU_NUM = {"medio": 1, "alto": 2, "muito alto": 3}


def sem_acento(s: str) -> str:
    tabela = str.maketrans("áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ", "aaaaeeioooucAAAAEEIOOOUC")
    return s.translate(tabela)


def campo(texto: str, rotulos):
    for r in rotulos:
        m = re.search(rf"{r}:\s*([^<]*)", texto)
        if m:
            return m.group(1).strip().rstrip(".").strip()
    return ""


def main():
    if not KMZ.exists():
        sys.exit(f"Não encontrei {KMZ}")
    with zipfile.ZipFile(KMZ) as z:
        nome_kml = next(n for n in z.namelist() if n.lower().endswith(".kml"))
        raiz = ET.fromstring(z.read(nome_kml))

    linhas = []
    for i, pm in enumerate(raiz.iter(K + "Placemark"), start=1):
        desc = pm.find(K + "description").text or ""
        tipo = campo(desc, ["Tipologia do Risco", "Tipo de Risco"])
        grau = campo(desc, ["Grau de Risco"])
        fonte = campo(desc, ["Mapeamentos", "Mapeamento"])
        atualiz = campo(desc, ["Atualização"])

        coords = pm.find(f".//{K}outerBoundaryIs//{K}coordinates").text.split()
        pts = [tuple(map(float, c.split(",")[:2])) for c in coords]
        geom = Polygon(pts)
        if not geom.is_valid:
            geom = geom.buffer(0)

        t = sem_acento(tipo.lower())
        alaga = int(any(k in t for k in ("inunda", "alagam", "enxurr")))
        eros = int(any(k in t for k in ("eros", "solap")))
        desl = int(any(k in t for k in ("desliz", "queda de bloco", "detrito", "rastejo")))
        if not (alaga or eros or desl):
            print(f"  AVISO: polígono {i} sem família reconhecida: {tipo!r}")

        g = sem_acento(grau.lower())
        linhas.append(
            dict(
                id=i,
                grau=grau,
                grau_num=GRAU_NUM.get(g, 0),
                tipo_txt=tipo[:80],
                alaga=alaga,
                eros=eros,
                desl=desl,
                fonte=(fonte + (" | atualiz. " + atualiz if atualiz else ""))[:80],
                geometry=geom,
            )
        )

    gdf = gpd.GeoDataFrame(linhas, geometry="geometry", crs="EPSG:4326")
    gdf.to_file(SAIDA_GEOJSON, driver="GeoJSON")

    gm = gdf.to_crs(CRS_METROS)
    gm["area_m2"] = gm.geometry.area.round(0)
    gm.to_file(SAIDA_SHP)  # cria .shp/.dbf/.shx/.prj

    print(f"{len(gm)} polígonos gravados em {SAIDA_SHP}")
    print("Por grau :", gm["grau"].str.rstrip('.').value_counts().to_dict())
    print("Famílias : alagamento/inundação =", int(gm.alaga.sum()),
          "| erosão/solapamento =", int(gm.eros.sum()),
          "| deslizamento/detritos =", int(gm.desl.sum()))
    x0, y0, x1, y1 = gm.total_bounds
    print(f"Extensão (m, UTM 22S): x {x0:.0f}..{x1:.0f}  y {y0:.0f}..{y1:.0f}")


if __name__ == "__main__":
    main()
