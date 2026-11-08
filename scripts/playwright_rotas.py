"""
Abre resultados/mapa_rotas.html no Chromium headless (Playwright) e confere:
  - sem erros no console / sem pageerror;
  - tiles de fundo carregam SEM status 403 (abrindo por file://);
  - enquadramento abre sobre Ibirama (zoom >= 12, centro na area de estudo);
  - busca por texto define origem/destino e tracou rota;
  - clique no mapa associa a um no (<=500 m) e REJEITA clique longe ("mais perto de uma rua");
  - atalhos "ir ao abrigo" e "ir ao hospital" definem destino e tracam rota;
  - caso conhecido "sem alternativa": origem 128 -> destino 3 com a ponte fechada
    (rua inteira) deve dizer "SEM ROTA ALTERNATIVA" (e NAO desenhar linha reta).
Salva capturas (satelite e ruas) FORA do repo (no scratchpad).

    python scripts/playwright_rotas.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
HTML = (RAIZ / "resultados" / "mapa_rotas.html").resolve()
SHOT = Path(r"D:\Temp\claude\C--Users-Brenda-Downloads-teste-final\916c2073-78ca-45b0-a2fe-06fdf9667a46\scratchpad")
SHOT.mkdir(parents=True, exist_ok=True)
TILE_HOSTS = ("arcgisonline.com", "cartocdn.com", "tile.openstreetmap.org")

erros = []
tiles = []   # (url, status) de requisicoes de tile


def on_resp(r):
    u = r.url
    if any(h in u for h in TILE_HOSTS):
        tiles.append((u, r.status))


with sync_playwright() as p:
    nav = p.chromium.launch(headless=True)
    pg = nav.new_page(viewport={"width": 1280, "height": 820})
    pg.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
    pg.on("response", on_resp)
    pg.goto(HTML.as_uri())
    pg.wait_for_function("window.__ROTAS_APP && window.__ROTAS_APP.map", timeout=15000)
    # espera os tiles carregarem
    try:
        pg.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    pg.wait_for_timeout(1500)

    # ---- 0) enquadramento e tiles ----
    zoom = pg.evaluate("window.__ROTAS_APP.map.getZoom()")
    centro = pg.evaluate("(()=>{const c=window.__ROTAS_APP.map.getCenter();return [c.lat,c.lng];})()")
    tiles403 = [t for t in tiles if t[1] == 403]
    tiles_ok = [t for t in tiles if 200 <= t[1] < 300]
    osm_req = [t for t in tiles if "openstreetmap.org" in t[0]]
    print(f"[enquadramento] zoom={zoom} centro={centro}")
    print(f"[tiles] carregados={len(tiles_ok)} | 403={len(tiles403)} | requisicoes OSM={len(osm_req)}")
    assert zoom >= 12, f"zoom inicial {zoom} < 12 (nao enquadrou Ibirama)"
    assert -27.3 < centro[0] < -26.8 and -49.8 < centro[1] < -49.2, f"centro fora de Ibirama: {centro}"
    assert not tiles403, f"tiles com 403: {tiles403[:3]}"
    assert not osm_req, "ainda ha requisicao a tile.openstreetmap.org (deveria ter saido do padrao)"
    pg.screenshot(path=str(SHOT / "rotas_0_satelite.png"))

    # troca para o mapa de ruas (Esri) e captura
    pg.evaluate("""() => { const A = window.__ROTAS_APP;
        A.map.removeLayer(A.bases.sat); A.map.addLayer(A.bases.ruasEsri); }""")
    try:
        pg.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    pg.wait_for_timeout(1200)
    tiles403b = [t for t in tiles if t[1] == 403]
    assert not tiles403b, f"tiles com 403 apos trocar p/ ruas: {tiles403b[:3]}"
    pg.screenshot(path=str(SHOT / "rotas_0b_ruas.png"))
    pg.evaluate("""() => { const A = window.__ROTAS_APP;
        A.map.removeLayer(A.bases.ruasEsri); A.map.addLayer(A.bases.sat); }""")

    # ---- 1) busca por texto: rua -> ponto critico ----
    rua = pg.evaluate("window.__ROTAS_APP.DATA.ruas[0].nome")
    ponto = pg.evaluate("(()=>{const p=window.__ROTAS_APP.DATA.pontos.find(x=>x.grupo==='hospital');return p.nome+' ('+p.grupo+')';})()")
    pg.fill("#inOrigem", rua)
    pg.dispatch_event("#inOrigem", "change")
    pg.fill("#inDestino", ponto)
    pg.dispatch_event("#inDestino", "change")
    pg.wait_for_timeout(400)
    res1 = pg.inner_text("#resultado")
    assoc1 = pg.inner_text("#assoc")
    paths_verdes = pg.evaluate("document.querySelectorAll('.leaflet-rotas-pane path[stroke=\"#1b7a3d\"]').length")
    print(f"[busca] origem='{rua}' destino='{ponto}'")
    print(f"  #resultado: {res1[:90]}")
    print(f"  #assoc: {assoc1}")
    print(f"  segmentos verdes desenhados: {paths_verdes}")
    assert ("km" in res1 or "m" in res1) and paths_verdes > 0, "rota nao desenhada na busca"
    pg.screenshot(path=str(SHOT / "rotas_1_busca.png"))

    # ---- 2) clique no mapa associa a um no (<=500 m) ----
    pg.mouse.click(900, 430)   # dentro do mapa, sobre a cidade
    pg.wait_for_timeout(300)
    assoc2 = pg.inner_text("#assoc")
    print(f"[clique perto] #assoc: {assoc2}")
    assert "associação" in assoc2 and "nó" in assoc2, "clique perto nao associou a no"

    # ---- 2b) clique longe (>500 m) deve ser rejeitado, sem definir origem/destino ----
    rej = pg.evaluate("""() => {
        const A = window.__ROTAS_APP; const antes = A.destino;
        A.map.fire('click', { latlng: L.latLng(-27.0, -41.0) });  // longe da rede
        return { assoc: document.getElementById('assoc').innerText,
                 res: document.getElementById('resultado').innerText,
                 mudouDestino: A.destino !== antes };
    }""")
    print(f"[clique longe] #assoc: {rej['assoc']}")
    assert "mais perto de uma rua" in rej["assoc"].lower() or "mais perto de uma rua" in rej["res"].lower(), \
        "nao rejeitou clique longe"
    assert not rej["mudouDestino"], "clique longe nao deveria definir destino"

    # ---- 2c) atalhos: ir ao abrigo / ir ao hospital a partir de uma origem valida ----
    for grupo, btn in (("abrigo", "#bAbrigo"), ("hospital", "#bHospital")):
        pg.evaluate("""(g) => { const A = window.__ROTAS_APP, D = A.DATA;
            A.porNo('origem', 500, D.nodes[500][0], D.nodes[500][1], 'origem teste', 0); }""", grupo)
        pg.click(btn)
        pg.wait_for_timeout(300)
        destino_lb = pg.evaluate("window.__ROTAS_APP.destino && window.__ROTAS_APP.destino.label")
        resA = pg.inner_text("#resultado")
        verdesA = pg.evaluate("document.querySelectorAll('.leaflet-rotas-pane path[stroke=\"#1b7a3d\"]').length")
        print(f"[atalho {grupo}] destino='{destino_lb}' | verdes={verdesA} | res={resA[:60]}")
        assert destino_lb and ("(" + grupo + ")") in destino_lb, f"atalho {grupo} nao definiu destino do grupo"
        assert verdesA > 0, f"atalho {grupo} nao desenhou rota"

    # ---- 3) caso conhecido SEM ALTERNATIVA (ponte fechada, rua inteira): 128 -> 3 ----
    pg.check('input[name=fmodo][value=inteira]')
    pg.evaluate("""() => {
        const A = window.__ROTAS_APP, D = A.DATA;
        A.porNo('origem', 128, D.nodes[128][0], D.nodes[128][1], 'no 128 (teste)', 0);
        A.porNo('destino', 3, D.nodes[3][0], D.nodes[3][1], 'no 3 (teste)', 0);
        const i = D.interd.findIndex(x => /Ponte/i.test(x.nome));
        const cb = document.querySelector('.fech[value="' + i + '"]');
        cb.checked = true; cb.dispatchEvent(new Event('change', {bubbles:true}));
    }""")
    pg.wait_for_timeout(400)
    res3 = pg.inner_text("#resultado")
    verdes3 = pg.evaluate("document.querySelectorAll('.leaflet-rotas-pane path[stroke=\"#1b7a3d\"]').length")
    cinza3 = pg.evaluate("document.querySelectorAll('.leaflet-rotas-pane path[stroke=\"#555\"]').length")
    vermelhos3 = pg.evaluate("document.querySelectorAll('.leaflet-fech-pane path[stroke=\"#b30000\"]').length")
    print(f"[sem alternativa] #resultado: {res3[:120]}")
    print(f"  segmentos desvio(verde): {verdes3} | normal(cinza): {cinza3} | fechados(vermelho): {vermelhos3}")
    pg.screenshot(path=str(SHOT / "rotas_2_sem_alternativa.png"))
    assert "SEM ROTA ALTERNATIVA" in res3, "nao exibiu 'sem alternativa' no caso da ponte"
    assert verdes3 == 0, "desenhou rota de desvio onde nao ha alternativa"
    assert vermelhos3 > 0, "nao desenhou os trechos fechados em vermelho"

    nav.close()

print("\nConsole/pageerror capturados:", erros if erros else "nenhum erro")
print("Capturas salvas em:", SHOT)
# so falha se houver erro de verdade (ignora warnings de tiles por falta de internet)
graves = [e for e in erros if e[0] == "pageerror" or (e[0] == "console.error" and "tile" not in e[1].lower())]
if graves:
    print("ERROS GRAVES:", graves); sys.exit(1)
print("OK: todas as verificacoes passaram.")
