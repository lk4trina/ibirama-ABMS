"""
Testes de logica do simulador (alinhado ao GAML). Rodar:  python python/testes_logica.py
Cada teste confere uma regra numa situacao controlada. Usa a rede *_TESTE (ficticia) -- nada aqui vai
para o artigo. O aviso ">> ATENCAO: usando a rede *_TESTE" e impresso por carregar_mundo.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simulador import (CABECALHO, RAIZ, Eventos, MODOS, Params, Simulacao,  # noqa: E402
                       carregar_mundo)

mundo = carregar_mundo("teste")
ok = True


def checa(nome, cond, detalhe=""):
    global ok
    ok &= bool(cond)
    print(("PASSOU  " if cond else "FALHOU  ") + nome + (f"  [{detalhe}]" if detalhe else ""))


def resumo(sim):
    r = {}
    for a in sim.ags:
        r[a.resultado] = r.get(a.resultado, 0) + 1
    return r


# T1 - sem evento: todos chegam, ninguem replaneja nem arrisca
s = Simulacao(mundo, Params(tipo_evento="nenhum"), 1).rodar()
checa("T1 sem evento: 100% concluem", resumo(s) == {"concluiu": len(s.ags)}, str(resumo(s)))
checa("T1 sem evento: nenhum replanejamento/travessia arriscada", sum(a.replan + a.arriscou for a in s.ags) == 0)

# T2 - mesma semente, mesmo resultado (determinismo)
r1 = Simulacao(mundo, Params(tipo_evento="combinado", severidade="alta"), 5).rodar().metricas()[0]
r2 = Simulacao(mundo, Params(tipo_evento="combinado", severidade="alta"), 5).rodar().metricas()[0]
checa("T2 determinismo com a mesma semente", r1 == r2)

# T3 - quem nao aceita o risco nunca entra em trecho fechado
s = Simulacao(mundo, Params(tipo_evento="nenhum", info_nivel="local"), 2)
s.log = []
ref = Simulacao(mundo, Params(tipo_evento="nenhum"), 2).rodar()
top = np.argsort(-ref.passagens)[:40]          # fecha as 40 vias mais usadas
s.ev.forcar_bloqueio(top, 30 * 60)
s.rodar()
viol = [(t, e, i) for (t, e, i, fechado) in s.log if fechado and not s.ags[i].cruza]
checa("T3 ninguem entra em trecho fechado sem aceitar o risco", len(viol) == 0, f"violacoes={len(viol)}")
print("      resultado:", resumo(s), "| replanejamentos:", sum(a.replan for a in s.ags))

# T4 - pontes fechadas: quem precisa atravessar espera, volta ou fica preso
pontes = [e for e, h in enumerate(mundo.hw) if h == "secondary"]
res = {}
for info in ("local", "amplo"):
    s = Simulacao(mundo, Params(tipo_evento="nenhum", info_nivel=info), 3)
    s.ev.forcar_bloqueio(pontes, 20 * 60)
    s.rodar()
    res[info] = resumo(s)
    print(f"      info={info}: {res[info]}")
falhas_local = sum(res["local"].get(k, 0) for k in ("voltou", "preso", "desistiu"))
checa("T4 com pontes fechadas ha agentes que voltam, desistem ou ficam presos", falhas_local > 0, f"{falhas_local}")
checa("T4 todo agente tem um resultado final", all(a.resultado for a in s.ags))

# T5 - so quem aceita o risco atravessa trecho fechado
s = Simulacao(mundo, Params(tipo_evento="nenhum"), 4)
ref = Simulacao(mundo, Params(tipo_evento="nenhum"), 4).rodar()
top = np.argsort(-ref.passagens)[:60]
s.ev.forcar_bloqueio(top, 10 * 60, atravessavel=True)
s.rodar()
arr = sum(a.arriscou for a in s.ags if a.cruza)
cau = sum(a.arriscou for a in s.ags if not a.cruza)
checa("T5 so quem aceita o risco faz travessia arriscada", cau == 0 and arr > 0, f"arrojados={arr}, demais={cau}")

# T6 - ocupacao nao fica negativa e soma dos desfechos = nº de agentes
checa("T6 ocupacao das vias nao negativa", (s.ocup >= -1e-9).all(), f"min={s.ocup.min()}")
checa("T6 soma dos desfechos = nº de agentes", sum(resumo(s).values()) == len(s.ags))

# T7 - REABERTURA: deslizamento (30 min) fecha durante a janela e reabre depois
ev = Eventos(mundo, Params(tipo_evento="deslizamento", severidade="alta"), np.random.default_rng(7))
cnt = ev.blk["carro"].sum(axis=1)              # nº de trechos fechados a cada passo de 5 min
# inicio 45 min + offset <= 20 min + duracao 30 min -> tudo reabre ate 95 min; checa em 150 min
k_depois = ev.k(150 * 60)
checa("T7 reabertura: fecha na janela e ZERA depois do fim da duracao",
      cnt.max() > 0 and cnt[k_depois] == 0, f"max_fechados={int(cnt.max())}, em_150min={int(cnt[k_depois])}")

# T8 - rede_energizada: deslizamento sem rede = 30 min; com rede = entre 60 e 90 min
ev_n = Eventos(mundo, Params(tipo_evento="deslizamento", severidade="alta"), np.random.default_rng(3))
ev_e = Eventos(mundo, Params(tipo_evento="deslizamento", severidade="alta", rede_energizada=True), np.random.default_rng(3))
ok_n = len(ev_n.dur_desl) > 0 and all(abs(d - 30 * 60) < 1e-6 for d in ev_n.dur_desl)
ok_e = len(ev_e.dur_desl) > 0 and all(60 * 60 - 1e-6 <= d <= 90 * 60 + 1e-6 for d in ev_e.dur_desl)
checa("T8 rede_energizada=false -> deslizamento de 30 min", ok_n, f"n={len(ev_n.dur_desl)}")
checa("T8 rede_energizada=true  -> deslizamento entre 60 e 90 min", ok_e,
      f"min={min(ev_e.dur_desl)/60:.0f} max={max(ev_e.dur_desl)/60:.0f} min")

# T9 - 6 grupos de acesso (x2 modais = 12 colunas) e NaN quando o grupo nao tem pontos
row, _ = Simulacao(mundo, Params(tipo_evento="combinado", severidade="alta"), 1).rodar().metricas()
cols_acc = [c for c in row if c.startswith("sem_acesso_")]
checa("T9 acesso: 12 colunas (6 grupos x 2 modais)", len(cols_acc) == 12, str(len(cols_acc)))
nan_ok = all(math.isnan(row[f"sem_acesso_{g}_carro_pct"]) for g in ("educacao", "ubs", "defesa_civil"))
checa("T9 acesso: grupo sem pontos vira NaN (educacao/ubs/defesa_civil na rede TESTE)", nan_ok)
checa("T9 acesso: grupo com pontos NAO e NaN (hospital)", not math.isnan(row["sem_acesso_hospital_carro_pct"]))
print("      (obs.: na rede REAL o grupo sem pontos e 'abrigo' -> NaN)")

# T10 - cabecalho: as 53 colunas do Python sao iguais, na mesma ordem, as do CSV do GAMA
gama_header = (RAIZ / "includes" / "resultados_gama_dc.csv").read_text(encoding="utf8").splitlines()[0].split(",")
checa("T10 cabecalho de 53 colunas igual ao includes/resultados_gama_dc.csv",
      CABECALHO == gama_header, f"py={len(CABECALHO)} gama={len(gama_header)}")

print("\nTODOS OS TESTES PASSARAM" if ok else "\nHA TESTES FALHANDO")
sys.exit(0 if ok else 1)
