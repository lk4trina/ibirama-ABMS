"""
Roda os mesmos fatores do experimento Lote do GAML (tipo_evento x severidade x info_nivel x
rede_energizada) com N repeticoes e grava um CSV com as MESMAS 54 colunas do GAMA.

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
a = ap.parse_args()

# Mesmos fatores do experimento Lote do GAML (models/ibirama.gaml, experiment Lote)
EVENTOS = ["nenhum", "alagamento", "deslizamento", "erosao", "combinado"]
SEVER = ["baixa", "media", "alta"]
INFO = ["local", "parcial", "amplo"]
REDE = [False, True]

carregar_mundo(a.rede)
linhas, t0 = [], time.time()
combos = list(itertools.product(EVENTOS, SEVER, INFO, REDE))
total = a.reps * len(combos)
feito = 0
for seed in range(1, a.reps + 1):
    for ev, sv, inf, rede in combos:
        row, _ = rodar_um(Params(tipo_evento=ev, severidade=sv, info_nivel=inf, rede_energizada=rede),
                          seed, a.rede)
        row["cenario"] = f"{ev}|{sv}|{inf}|{'energizada' if rede else 'normal'}"
        linhas.append(row)
        feito += 1
    print(f"semente {seed}/{a.reps} concluida  ({feito}/{total}, {time.time()-t0:.0f} s)", flush=True)

saida = Path(a.saida) if a.saida else RAIZ / "resultados" / f"resultados_python_{a.rede}.csv"
saida.parent.mkdir(exist_ok=True)
# ordem: as 54 colunas do GAMA + a coluna de apoio 'cenario'; NaN gravado como "NaN" (igual ao GAMA)
df = pd.DataFrame(linhas)[CABECALHO + ["cenario"]]
df.to_csv(saida, index=False, na_rep="NaN")
print(f"{len(linhas)} execucoes gravadas em {saida}")
