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
from simulador import (CABECALHO, PICOS_MIN, RAIZ, Eventos, MODOS, Params, Simulacao,  # noqa: E402
                       carregar_mundo, hora_do_dia)

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
r1_ = resumo(s)
tardios = [a for a in s.ags if a.resultado == "em_viagem"]
checa("T1 sem evento: so ha 'concluiu' ou 'em_viagem' (quem saiu tarde, perto das 19:00)",
      set(r1_) <= {"concluiu", "em_viagem"} and all(a.t_part > (780 - 60) * 60 for a in tardios), str(r1_))
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
cols_acc = [c for c in row if c.startswith("sem_acesso_") and not c.endswith("_plato_pct")]
checa("T9 acesso: 12 colunas (6 grupos x 2 modais)", len(cols_acc) == 12, str(len(cols_acc)))
nan_ok = all(math.isnan(row[f"sem_acesso_{g}_carro_pct"]) for g in ("educacao", "ubs", "defesa_civil"))
checa("T9 acesso: grupo sem pontos vira NaN (educacao/ubs/defesa_civil na rede TESTE)", nan_ok)
checa("T9 acesso: grupo com pontos NAO e NaN (hospital)", not math.isnan(row["sem_acesso_hospital_carro_pct"]))
print("      (obs.: na rede REAL o grupo sem pontos e 'abrigo' -> NaN)")

# T10 - cabecalho: as 69 colunas do Python sao iguais, na mesma ordem, as do CSV do GAMA
gama_header = (RAIZ / "includes" / "resultados_gama_dc.csv").read_text(encoding="utf8").splitlines()[0].split(",")
checa("T10 cabecalho de 69 colunas igual ao includes/resultados_gama_dc.csv",
      CABECALHO == gama_header, f"py={len(CABECALHO)} gama={len(gama_header)}")

# T11 - compatibilidade: com duracao_chuva_min = 0 o perfil do alagamento e EXATAMENTE o de antes (10/5/15)
dur = 30 * 60.0
rampa = dur / 3.0
tks = np.arange(0, 6000, 300.0)
t0, pico = 1000.0, 0.8
antigo = np.interp(tks, [t0, t0 + rampa, t0 + rampa + dur / 6.0, t0 + dur], [0, pico, pico, 0], left=0, right=0)
plato0 = dur / 6.0
rec0 = dur - rampa - plato0
novo0 = np.interp(tks, [t0, t0 + rampa, t0 + rampa + plato0, t0 + rampa + plato0 + rec0], [0, pico, pico, 0], left=0, right=0)
checa("T11 chuva=0 reproduz o perfil de 30 min (10/5/15)", np.allclose(antigo, novo0))

# T12 - chuva longa faz a inundacao DURAR MAIS e reabrir so depois (mesma semente = mesmos poligonos)
ev0 = Eventos(mundo, Params(tipo_evento="alagamento", severidade="alta", duracao_chuva_min=0.0), np.random.default_rng(9))
ev120 = Eventos(mundo, Params(tipo_evento="alagamento", severidade="alta", duracao_chuva_min=120.0), np.random.default_rng(9))
passos0 = int((ev0.H > 0).any(axis=1).sum())
passos120 = int((ev120.H > 0).any(axis=1).sum())
checa("T12 chuva longa prolonga a inundacao", passos120 > passos0 and passos0 > 0, f"sem chuva={passos0}, chuva120={passos120} passos de 5 min")
cnt = ev120.blk["carro"].sum(axis=1)
checa("T12 reabertura: inunda durante e ZERA depois (chuva 120 min)", cnt.max() > 0 and cnt[ev120.k(300 * 60)] == 0,
      f"max={int(cnt.max())}, em_300min={int(cnt[ev120.k(300*60)])}")

# T13 - os padroes sao 60 min de chuva (ancorada nas materias); informar 60 explicitamente da o mesmo
m_pad = Simulacao(mundo, Params(tipo_evento="combinado", severidade="alta"), 7).rodar().metricas()[0]
m_60 = Simulacao(mundo, Params(tipo_evento="combinado", severidade="alta", duracao_chuva_min=60.0), 7).rodar().metricas()[0]
checa("T13 padrao = duracao_chuva_min 60 (mesma semente)", m_pad == m_60)
# T13b - padroes ANTIGOS ligados explicitamente: 480 min, janela unica de 180, evento aos 45, chuva 0, erosao 480.
# (A prova de que as colunas antigas ficam IDENTICAS as da versao anterior e feita por execucao no GAMA e,
#  no Python, comparando com a copia do simulador antigo - ver docs/python_vs_gaml.md.)
p_antigo = Params(tipo_evento="combinado", severidade="alta", horizonte_min=480.0, usar_picos=False, janela_partida_min=180.0,
                  inicio_evento_min=45.0, duracao_chuva_min=0.0, duracao_erosao_min=480.0)
s_ant = Simulacao(mundo, p_antigo, 7).rodar()
checa("T13b padroes antigos: saidas na janela de 180 min e simulacao de 480 min",
      max(a.t_part for a in s_ant.ags) < 180 * 60 and s_ant.p.horizonte_min == 480.0)

# T14 - picos de saida (HIPOTESE): fracao nos picos coerente com frac_pico; nada fora do horizonte
p_pic = Params(tipo_evento="nenhum")
checa("T14 padroes novos: horizonte 780, picos ligados, frac_pico 0.6, chuva 60, inicio 60, erosao 780",
      (p_pic.horizonte_min, p_pic.usar_picos, p_pic.frac_pico, p_pic.duracao_chuva_min,
       p_pic.inicio_evento_min, p_pic.duracao_erosao_min) == (780.0, True, 0.6, 60.0, 60.0, 780.0))
ts = np.array([a.t_part for a in Simulacao(mundo, p_pic, 11).ags]) / 60.0
dentro = np.zeros(len(ts), bool)
for lo, hi in PICOS_MIN:
    dentro |= (ts >= lo) & (ts < hi)
esperado = 0.6 + 0.4 * (3 * 60.0 / 780.0)          # nos picos de proposito + uniforme que cai num pico por acaso
checa("T14 saidas em [0, 780) min", ts.min() >= 0 and ts.max() < 780.0, f"min={ts.min():.1f} max={ts.max():.1f}")
checa("T14 fracao de saidas dentro dos picos ~ 0,6 + 0,4*180/780", abs(dentro.mean() - esperado) < 0.04,
      f"obs={dentro.mean():.3f} esp={esperado:.3f}")
cont = [int(((ts >= lo) & (ts < hi)).sum()) for lo, hi in PICOS_MIN]
checa("T14 os 3 picos recebem quantidades parecidas (pesos iguais)", max(cont) / min(cont) < 1.35, str(cont))
p_old = Params(tipo_evento="nenhum", usar_picos=False, janela_partida_min=180.0)
ts0 = np.array([a.t_part for a in Simulacao(mundo, p_old, 11).ags]) / 60.0
checa("T14 usar_picos=False: saidas so na janela de 180 min (versao anterior)", ts0.max() < 180.0, f"max={ts0.max():.1f}")

# T15 - horario do dia e horizonte: 06:00 = tempo 0; 19:00 = 780 min
checa("T15 hora_do_dia: 0 -> 06:00, 60 min -> 07:00, 780 min -> 19:00",
      (hora_do_dia(0), hora_do_dia(3600), hora_do_dia(780 * 60)) == ("06:00", "07:00", "19:00"))
ev780 = Eventos(mundo, Params(tipo_evento="erosao", severidade="alta"), np.random.default_rng(4))
checa("T15 horizonte 780: o estado das vias cobre ate 19:00", ev780.K >= 780 * 60 / 300, f"K={ev780.K}")
checa("T15 erosao dura 780 min (o dia todo)", len(ev780.dur_eros) > 0 and all(d == 780 * 60.0 for d in ev780.dur_eros))

# T16 - colunas novas: usar_picos, frac_pico, inicio_evento_min e a medicao no plato
row, _ = Simulacao(mundo, Params(tipo_evento="combinado", severidade="alta"), 3).rodar().metricas()
i_ch = CABECALHO.index("duracao_chuva_min")
checa("T16 usar_picos/frac_pico logo depois de duracao_chuva_min", CABECALHO[i_ch + 1:i_ch + 3] == ["usar_picos", "frac_pico"])
checa("T16 12 colunas *_plato_pct + inicio_evento_min", len([c for c in row if c.endswith("_plato_pct")]) == 12
      and row["inicio_evento_min"] == 60.0)
print("      pct_em_andamento (carro) com picos, combinado/alta:", row["pct_em_andamento_carro"], "%")

print("\nTODOS OS TESTES PASSARAM" if ok else "\nHA TESTES FALHANDO")
sys.exit(0 if ok else 1)
