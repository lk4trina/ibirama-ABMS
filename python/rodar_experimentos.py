"""
Roda os mesmos fatores dos experimentos do GAML com N repeticoes. --experimento: Lote (padrao; tipo_evento x
severidade x info_nivel x rede_energizada), LoteChuva (duracao_chuva_min 0/60/120/240/780) ou LoteHorario
(inicio_evento_min 30/270/630 x chuva 60/780), com N repeticoes e grava um CSV com as MESMAS 69 colunas do GAMA.

    python python/rodar_experimentos.py                       # rede de teste (ficticia)
    python python/rodar_experimentos.py --reps 30 --rede real # rede real (para a verificacao cruzada)

Grava em resultados/resultados_python_<rede>.csv  (NUNCA em includes/resultados_gama_dc.csv, que e do GAMA).
A mesma semente gera a mesma populacao em todos os cenarios, entao da para comparar com a linha de base
(tipo_evento = nenhum), que o scripts/03_analise.py usa para o atraso pareado.
"""
import argparse
import itertools
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simulador import CABECALHO, RAIZ, Params, carregar_mundo, rodar_um  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--reps", type=int, default=5)
ap.add_argument("--rede", default="teste", choices=["teste", "real"])
ap.add_argument("--saida", default=None)
ap.add_argument("--experimento", default="Lote", choices=["Lote", "LoteChuva", "LoteHorario"])
a = ap.parse_args()

# Mesmos fatores do experimento Lote do GAML (models/ibirama.gaml, experiment Lote)
EVENTOS = ["nenhum", "alagamento", "deslizamento", "erosao", "combinado"]
SEVER = ["baixa", "media", "alta"]
INFO = ["local", "parcial", "amplo"]
REDE = [False, True]

carregar_mundo(a.rede)
linhas, t0 = [], time.time()
if a.experimento == "Lote":
    combos = [dict(tipo_evento=e, severidade=s, info_nivel=i, rede_energizada=r)
              for e, s, i, r in itertools.product(EVENTOS, SEVER, INFO, REDE)]
elif a.experimento == "LoteChuva":     # 0/60/120/240/780 (60 e 780 ancorados nas materias; resto = sensibilidade)
    combos = [dict(tipo_evento=e, duracao_chuva_min=c, severidade="alta", info_nivel="parcial")
              for e, c in itertools.product(["combinado", "alagamento"], [0.0, 60.0, 120.0, 240.0, 780.0])]
else:                                  # LoteHorario
    combos = [dict(tipo_evento=e, inicio_evento_min=i, duracao_chuva_min=c, severidade="alta", info_nivel="parcial")
              for e, i, c in itertools.product(["combinado", "alagamento"], [30.0, 270.0, 630.0], [60.0, 780.0])]
total = a.reps * len(combos)
feito = 0
for seed in range(1, a.reps + 1):
    for kw in combos:
        row, _ = rodar_um(Params(**kw), seed, a.rede)
        row["cenario"] = "|".join(f"{k}={v}" for k, v in kw.items())
        linhas.append(row)
        feito += 1
    print(f"semente {seed}/{a.reps} concluida  ({feito}/{total}, {time.time()-t0:.0f} s)", flush=True)

saida = Path(a.saida) if a.saida else RAIZ / "resultados" / f"resultados_python_{a.rede}.csv"
saida.parent.mkdir(exist_ok=True)
# ordem: as 69 colunas do GAMA + a coluna de apoio 'cenario'; NaN gravado como "NaN" (igual ao GAMA)
df = pd.DataFrame(linhas)[CABECALHO + ["cenario"]]
df.to_csv(saida, index=False, na_rep="NaN")
print(f"{len(linhas)} execucoes gravadas em {saida}")
