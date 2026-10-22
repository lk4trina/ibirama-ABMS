"""
Testes de lógica do simulador. Rodar:  python python/testes_logica.py
Cada teste verifica uma regra de comportamento dos agentes em situação controlada.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simulador import MODOS, Params, Simulacao, carregar_mundo  # noqa: E402

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


# T1 - sem evento: todos chegam, ninguém replaneja nem arrisca
s = Simulacao(mundo, Params(evento="nenhum"), 1).rodar()
checa("T1 sem evento: 100% concluem", resumo(s) == {"concluiu": len(s.ags)}, str(resumo(s)))
checa("T1 sem evento: nenhum replanejamento/travessia arriscada", sum(a.replan + a.arriscou for a in s.ags) == 0)

# T2 - determinismo: mesma semente => mesmo resultado
r1 = Simulacao(mundo, Params(evento="combinado", severidade="alta"), 5).rodar().metricas()[0]
r2 = Simulacao(mundo, Params(evento="combinado", severidade="alta"), 5).rodar().metricas()[0]
checa("T2 determinismo com a mesma semente", r1 == r2)

# T3 - invariante: quem NÃO arrisca nunca entra em trecho fechado
s = Simulacao(mundo, Params(evento="nenhum", info="local"), 2)
s.log = []
trechos = np.argsort(-s.passagens)[:0]
# fecha as 40 vias mais usadas numa rodada de referência
ref = Simulacao(mundo, Params(evento="nenhum"), 2).rodar()
top = np.argsort(-ref.passagens)[:40]
s.ev.forcar_bloqueio(top, 30 * 60)
s.rodar()
viol = [(t, e, i) for (t, e, i, fechado) in s.log if fechado and not s.ags[i].cruza]
dentro = [(t, e) for (t, e, i, f) in s.log if e in set(top) and t >= 30 * 60 + 300 and not s.ags[i].cruza]
checa("T3 ninguém entra em trecho fechado sem aceitar o risco", len(viol) == 0, f"violações={len(viol)}")
print("      resultado:", resumo(s), "| replanejamentos:", sum(a.replan for a in s.ags))

# T4 - rio isolado: fechar todas as pontes (secondary) cedo -> quem precisa atravessar espera, volta ou fica preso
pontes = [e for e, h in enumerate(mundo.hw) if h == "secondary"]
res = {}
for info in ("local", "amplo"):
    s = Simulacao(mundo, Params(evento="nenhum", info=info), 3)
    s.ev.forcar_bloqueio(pontes, 20 * 60)
    s.rodar()
    res[info] = resumo(s)
    print(f"      info={info}: {res[info]}")
falhas_local = sum(res["local"].get(k, 0) for k in ("voltou", "preso", "desistiu"))
checa("T4 com pontes fechadas há agentes que voltam, desistem ou ficam presos", falhas_local > 0, f"{falhas_local}")
checa("T4 todo agente tem um resultado final", all(a.resultado for a in s.ags))

# T5 - 'arrojado' atravessa trecho atravessável; cauteloso não
s = Simulacao(mundo, Params(evento="nenhum"), 4)
ref = Simulacao(mundo, Params(evento="nenhum"), 4).rodar()
top = np.argsort(-ref.passagens)[:60]
s.ev.forcar_bloqueio(top, 10 * 60, atravessavel=True)
s.rodar()
arr = sum(a.arriscou for a in s.ags if a.cruza)
cau = sum(a.arriscou for a in s.ags if not a.cruza)
checa("T5 só quem aceita o risco faz travessia arriscada", cau == 0 and arr > 0, f"arrojados={arr}, demais={cau}")

# T6 - conservação: ocupação nunca fica negativa e soma dos resultados = nº de agentes
checa("T6 ocupação das vias não negativa", (s.ocup >= -1e-9).all(), f"min={s.ocup.min()}")
checa("T6 soma dos resultados = nº de agentes", sum(resumo(s).values()) == len(s.ags))

print("\nTODOS OS TESTES PASSARAM" if ok else "\nHÁ TESTES FALHANDO")
sys.exit(0 if ok else 1)
