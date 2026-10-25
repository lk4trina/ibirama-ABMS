"""
PASSO 3 - Análise estatística e gráficos a partir do CSV de resultados.

Funciona com o CSV do simulador Python (python/rodar_experimentos.py) e, se as colunas tiverem os
mesmos nomes, com o CSV exportado pelo experimento batch do GAMA.

    python scripts/03_analise.py resultados/resultados_python_real.csv

O que gera em resultados/analise/:
    resumo_por_cenario.csv      média e desvio padrão de cada métrica por cenário (o que o enunciado pede)
    testes_estatisticos.csv     Kruskal-Wallis (efeito de cada fator) e Mann-Whitney com Bonferroni
    graficos *.png              atraso por evento/severidade/informação, desfechos, acessibilidade

Por que testes não paramétricos: as métricas (tempos, percentuais) em geral não são normais e as
amostras são pequenas. Os testes não supõem normalidade.
"""
import sys
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

arq = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "resultados" / "resultados_python_real.csv"
saida = arq.parent / "analise"
saida.mkdir(exist_ok=True)
# Colunas do CSV do GAMA (a ordem é a mesma gravada por modelo/ibirama.gaml, que não grava cabeçalho)
COLUNAS_GAMA = ["evento", "severidade", "info", "seed", "polig_ativos"]
for _m in ("carro", "moto", "pedestre"):
    COLUNAS_GAMA += [f"{_m}_{c}" for c in ("n", "concluiu_pct", "voltou_pct", "desistiu_pct", "preso_pct", "emviagem_pct",
                                          "tempo_medio_min", "dist_media_m", "travessias_arriscadas", "replanejamentos")]
COLUNAS_GAMA += ["fluxo_gini", "fluxo_top10_pct"]
for _t in ("hospital", "bombeiros", "abrigo"):
    COLUNAS_GAMA += [f"acc_{_t}_{_m}_sem_acesso_pct" for _m in ("carro", "pedestre")]

with open(arq, encoding="utf8") as f:
    primeira = f.readline()
if primeira.lstrip().lower().startswith("evento"):
    df = pd.read_csv(arq)
else:  # CSV do GAMA, sem cabeçalho
    df = pd.read_csv(arq, header=None, names=COLUNAS_GAMA)
if "cenario" not in df:
    df["cenario"] = df["evento"] + "|" + df["severidade"].astype(str) + "|" + df["info"]
if "carro_atraso_pareado_min" not in df and "carro_tempo_medio_min" in df:
    # CSV do GAMA: atraso = tempo médio do cenário - tempo médio da linha de base com a MESMA semente
    # (se a semente não se repetir entre cenários, usa a média geral da linha de base)
    base = df[df.evento == "nenhum"]
    for _m in ("carro", "moto", "pedestre"):
        col = f"{_m}_tempo_medio_min"
        por_semente = base.groupby("seed")[col].mean()
        ref = df["seed"].map(por_semente).fillna(base[col].mean())
        df[f"{_m}_atraso_pareado_min"] = df[col] - ref
com_evento = df[df.evento != "nenhum"].copy()
reps = df.groupby("cenario").size().min()
print(f"{len(df)} execuções, {df.cenario.nunique()} cenários, mínimo {reps} repetições por cenário")

METRICAS = [c for c in [
    "carro_atraso_pareado_min", "moto_atraso_pareado_min", "pedestre_atraso_pareado_min",
    "carro_concluiu_pct", "moto_concluiu_pct", "pedestre_concluiu_pct",
    "carro_voltou_pct", "carro_desistiu_pct", "carro_preso_pct",
    "carro_dist_extra_m", "moto_dist_extra_m", "pedestre_dist_extra_m",
    "carro_travessias_arriscadas", "moto_travessias_arriscadas", "pedestre_travessias_arriscadas",
    "fluxo_gini", "fluxo_top10_pct",
    "acc_hospital_carro_sem_acesso_pct", "acc_hospital_carro_tempo_medio_min",
    "acc_abrigo_pedestre_sem_acesso_pct", "trechos_fechados_pico_carro",
] if c in df and df[c].notna().any()]   # ignora colunas ausentes ou totalmente vazias (ex.: abrigo sem pontos)

# ---- 1) resumo por cenário: média e desvio padrão ------------------------------------------------
resumo = df.groupby("cenario")[METRICAS].agg(["mean", "std"]).round(3)
resumo.columns = [f"{a}_{b}" for a, b in resumo.columns]
resumo.insert(0, "n_repeticoes", df.groupby("cenario").size())
resumo.to_csv(saida / "resumo_por_cenario.csv")

# ---- 2) testes estatísticos ----------------------------------------------------------------------
def a12(x, y):
    """Tamanho de efeito de Vargha-Delaney: prob. de um valor de x ser maior que um de y (0,5 = sem efeito)."""
    x, y = np.asarray(x), np.asarray(y)
    r = stats.rankdata(np.concatenate([x, y]))
    return (r[: len(x)].sum() / len(x) - (len(x) + 1) / 2) / len(y)


linhas = []
for met in METRICAS:
    d = com_evento[["evento", "severidade", "info", met]].dropna()
    for fator in ("evento", "severidade", "info"):
        grupos = [g[met].values for _, g in d.groupby(fator) if len(g) > 1]
        if len(grupos) > 1 and np.ptp(np.concatenate(grupos)) > 0:
            h, pv = stats.kruskal(*grupos)
            linhas.append(dict(metrica=met, teste="Kruskal-Wallis", fator=fator, estatistica=round(h, 3), p=pv))
        nomes = sorted(d[fator].unique())
        pares = list(combinations(nomes, 2))
        for x, y in pares:
            gx, gy = d[d[fator] == x][met].values, d[d[fator] == y][met].values
            if len(gx) > 1 and len(gy) > 1 and np.ptp(np.concatenate([gx, gy])) > 0:
                u, pv = stats.mannwhitneyu(gx, gy, alternative="two-sided")
                linhas.append(dict(metrica=met, teste="Mann-Whitney", fator=fator, comparacao=f"{x} x {y}",
                                   estatistica=round(u, 1), p=pv, p_bonferroni=min(1.0, pv * len(pares)),
                                   efeito_A12=round(a12(gx, gy), 3)))
t = pd.DataFrame(linhas)
if len(t):
    t["significativo_5pct"] = np.where(t.get("p_bonferroni", t["p"]).fillna(t["p"]) < 0.05, "sim", "não")
t.to_csv(saida / "testes_estatisticos.csv", index=False)

# ---- 3) gráficos ---------------------------------------------------------------------------------
def barras(metrica, por, titulo, arquivo, ylabel):
    if metrica not in com_evento:
        return
    g = com_evento.groupby(por)[metrica].agg(["mean", "std"])
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.bar(g.index.astype(str), g["mean"], yerr=g["std"], capsize=4, color="#3b6ea5")
    ax.set_title(titulo, fontsize=11)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=.3)
    fig.tight_layout()
    fig.savefig(saida / arquivo, dpi=160)
    plt.close(fig)


for modo in ("carro", "moto", "pedestre"):
    barras(f"{modo}_atraso_pareado_min", "evento", f"Atraso médio – {modo}, por tipo de evento", f"atraso_{modo}_por_evento.png", "min (± desvio)")
barras("carro_atraso_pareado_min", "info", "Atraso médio – carro, por nível de informação", "atraso_carro_por_info.png", "min (± desvio)")

fig, ax = plt.subplots(figsize=(7, 3.8))
for modo, cor in (("carro", "#3b6ea5"), ("moto", "#c0504d"), ("pedestre", "#6a9f3a")):
    col = f"{modo}_atraso_pareado_min"
    if col in com_evento:
        g = com_evento.groupby("severidade")[col].mean().reindex(["baixa", "media", "alta"])
        ax.plot(g.index, g.values, marker="o", label=modo, color=cor)
ax.set_title("Atraso médio por severidade e modal", fontsize=11)
ax.set_ylabel("min")
ax.legend()
ax.grid(alpha=.3)
fig.tight_layout()
fig.savefig(saida / "atraso_por_severidade_modal.png", dpi=160)
plt.close(fig)

des = [c for c in ["carro_concluiu_pct", "carro_voltou_pct", "carro_desistiu_pct", "carro_preso_pct", "carro_emviagem_pct"] if c in com_evento]
if des:
    g = com_evento.groupby("info")[des].mean().reindex(["local", "parcial", "amplo"])
    ax = g.plot(kind="bar", stacked=True, figsize=(6.5, 3.8), colormap="viridis")
    ax.set_title("Desfecho das viagens de carro por nível de informação", fontsize=11)
    ax.set_ylabel("% dos agentes")
    ax.legend([c.replace("carro_", "").replace("_pct", "") for c in des], fontsize=8, loc="lower left")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(saida / "desfechos_carro_por_info.png", dpi=160)
    plt.close()

print("Análise gravada em", saida)
if len(t):
    sig = t[(t.teste == "Kruskal-Wallis") & (t.p < 0.05)]
    print("Kruskal-Wallis com p<0,05:")
    print(sig[["metrica", "fator", "estatistica", "p"]].to_string(index=False) if len(sig) else "  (nenhum)")
