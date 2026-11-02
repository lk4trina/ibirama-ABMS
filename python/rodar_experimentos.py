"""
Roda todos os cenários (4 eventos x 3 severidades x 3 níveis de informação, mais a linha de base)
com N repetições e grava um CSV.

    python python/rodar_experimentos.py
    python python/rodar_experimentos.py --reps 30 --rede real

A mesma semente gera a mesma população em todos os cenários, então dá para comparar cada agente
com a linha de base.
"""
import argparse
import itertools
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simulador import RAIZ, Params, carregar_mundo, rodar_um  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--reps", type=int, default=10)
ap.add_argument("--rede", default="teste", choices=["teste", "real"])
ap.add_argument("--saida", default=None)
a = ap.parse_args()

EVENTOS = ["alagamento", "deslizamento", "erosao", "combinado"]
SEVER = ["baixa", "media", "alta"]
INFO = ["local", "parcial", "amplo"]

carregar_mundo(a.rede)
linhas, t0 = [], time.time()
total = a.reps * (1 + len(EVENTOS) * len(SEVER) * len(INFO))
feito = 0
for seed in range(1, a.reps + 1):
    base_t = {}
    # linha de base (sem evento), uma por nível de informação
    for info in INFO:
        row, tempos = rodar_um(Params(evento="nenhum", info=info), seed, a.rede)
        base_t[info] = tempos
        row["cenario"] = f"nenhum|-|{info}"
        linhas.append(row)
        feito += 1
    for ev, sv, inf in itertools.product(EVENTOS, SEVER, INFO):
        row, _ = rodar_um(Params(evento=ev, severidade=sv, info=inf), seed, a.rede, ref=base_t[inf])
        row["cenario"] = f"{ev}|{sv}|{inf}"
        linhas.append(row)
        feito += 1
    print(f"semente {seed}/{a.reps} concluída  ({time.time()-t0:.0f} s)", flush=True)

saida = Path(a.saida) if a.saida else RAIZ / "resultados" / f"resultados_python_{a.rede}.csv"
saida.parent.mkdir(exist_ok=True)
pd.DataFrame(linhas).to_csv(saida, index=False)
print(f"{len(linhas)} execuções gravadas em {saida}")
