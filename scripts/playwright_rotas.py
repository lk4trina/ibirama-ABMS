"""
Abre resultados/mapa_rotas.html no Chromium headless (Playwright) e confere:
  - sem erros no console / sem pageerror;
  - busca por texto define origem/destino e tracou rota;
  - clique no mapa associa a um no (mostra distancia de associacao);
  - caso conhecido "sem alternativa": origem 128 -> destino 3 com a ponte fechada
    (rua inteira) deve dizer "SEM ROTA ALTERNATIVA" (e NAO desenhar linha reta).
Salva capturas FORA do repo (no scratchpad).

    python scripts/playwright_rotas.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
HTML = (RAIZ / "resultados" / "mapa_rotas.html").resolve()
SHOT = Path(r"D:\Temp\claude\C--Users-Brenda-Downloads-teste-final\916c2073-78ca-45b0-a2fe-06fdf9667a46\scratchpad")
SHOT.mkdir(parents=True, exist_ok=True)

erros = []
with sync_playwright() as p:
    nav = p.chromium.launch(headless=True)
    pg = nav.new_page(viewport={"width": 1280, "height": 820})
    pg.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
    pg.goto(HTML.as_uri())
    pg.wait_for_function("window.__ROTAS_APP && window.__ROTAS_APP.DATA", timeout=15000)

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

    # ---- 2) clique no mapa associa a um no ----
    pg.mouse.click(900, 430)   # dentro do mapa
    pg.wait_for_timeout(300)
    assoc2 = pg.inner_text("#assoc")
    print(f"[clique] #assoc: {assoc2}")
    assert "no" in assoc2.lower() or "nó" in assoc2.lower(), "clique nao associou a no"

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
