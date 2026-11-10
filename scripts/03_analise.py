"""
PASSO 3 - Analise estatistica e graficos a partir do CSV de resultados.

Funciona com o CSV do simulador Python (python/rodar_experimentos.py) e com o CSV do experimento
batch do GAMA (includes/resultados_gama_dc.csv), que tem as MESMAS 69 colunas.

    python scripts/03_analise.py resultados/resultados_python_real.csv

O que gera em <pasta do csv>/analise/:
    resumo_por_cenario.csv      media e desvio padrao de cada metrica por cenario
    testes_estatisticos.csv     Kruskal-Wallis (efeito de cada fator) e Mann-Whitney com Bonferroni
    graficos *.png              atraso por evento/severidade/informacao, desfechos, acessibilidade

Colunas ausentes ou totalmente NaN (ex.: 'abrigo' sem pontos) sao ignoradas automaticamente.
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))
from simulador import CABECALHO  # noqa: E402  (as 69 colunas, na ordem do GAMA)

MODOS = ("carro", "moto", "pedestre")
arq = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "resultados" / "resultados_python_real.csv"
saida = arq.parent / "analise"
saida.mkdir(exist_ok=True)

with open(arq, encoding="utf8") as f:
    primeira = f.readline()
if primeira.lstrip().lower().startswith("tipo_evento"):
    df = pd.read_csv(arq)
else:  # CSV do GAMA sem cabecalho: usa as 69 colunas na ordem conhecida
    df = pd.read_csv(arq, header=None, names=CABECALHO)

# fatores (mesmos nomes do GAML)
if "cenario" not in df:
    df["cenario"] = (df["tipo_evento"] + "|" + df["severidade"].astype(str) + "|" + df["info_nivel"]
                     + "|" + df.get("rede_energizada", "normal").astype(str)
                     + "|chuva" + df.get("duracao_chuva_min", 0).astype(str)
                     + "|inicio" + df.get("inicio_evento_min", 0).astype(str))
# fatores de cenario presentes (inclui a duracao da chuva quando o CSV varia esse campo)
FATORES = [c for c in ("tipo_evento", "severidade", "info_nivel", "duracao_chuva_min", "inicio_evento_min")
           if c in df.columns]
# atraso pareado = tempo medio do cenario - tempo medio da linha de base (tipo_evento = nenhum), mesma semente
base = df[df.tipo_evento == "nenhum"]
for m in MODOS:
    col = f"tempo_medio_{m}_min"
    if col in df and not base.empty:
        por_semente = base.groupby("seed")[col].mean()
        ref = df["seed"].map(por_semente)
        ref = ref.fillna(base[col].mean())
        df[f"atraso_pareado_{m}_min"] = df[col] - ref

com_evento = df[df.tipo_evento != "nenhum"].copy()
reps = df.groupby("cenario").size().min()
print(f"{len(df)} execucoes, {df.cenario.nunique()} cenarios, minimo {reps} repeticoes por cenario")

CANDIDATAS = []
for m in MODOS:
    CANDIDATAS += [f"atraso_pareado_{m}_min", f"pct_concluiu_{m}", f"pct_voltou_{m}", f"pct_desistiu_{m}",
                   f"pct_preso_{m}", f"distancia_media_{m}_m", f"travessias_perigosas_{m}"]
for m in MODOS:
    CANDIDATAS += [f"pct_em_andamento_{m}"]
CANDIDATAS += ["gini_fluxo", "pct_fluxo_top10_vias"]
for g in ("hospital", "bombeiros", "defesa_civil", "educacao", "ubs", "abrigo"):
    CANDIDATAS += [f"sem_acesso_{g}_carro_pct", f"sem_acesso_{g}_pedestre_pct",
                   f"sem_acesso_{g}_carro_plato_pct", f"sem_acesso_{g}_pedestre_plato_pct"]
# ignora colunas ausentes ou totalmente vazias (ex.: abrigo sem pontos na rede real)
METRICAS = [c for c in CANDIDATAS if c in df and df[c].notna().any()]

# ---- 1) resumo por cenario: media e desvio padrao ------------------------------------------------
resumo = df.groupby("cenario")[METRICAS].agg(["mean", "std"]).round(3)
resumo.columns = [f"{a_}_{b_}" for a_, b_ in resumo.columns]
resumo.insert(0, "n_repeticoes", df.groupby("cenario").size())
resumo.to_csv(saida / "resumo_por_cenario.csv")

# ---- 2) testes estatisticos ----------------------------------------------------------------------
def a12(x, y):
    """Vargha-Delaney: prob. de um valor de x ser maior que um de y (0,5 = sem efeito)."""
    x, y = np.asarray(x), np.asarray(y)
    r = stats.rankdata(np.concatenate([x, y]))
    return (r[: len(x)].sum() / len(x) - (len(x) + 1) / 2) / len(y)


linhas = []
for met in METRICAS:
    d = com_evento[FATORES + [met]].dropna()
    for fator in FATORES:
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
    t["significativo_5pct"] = np.where(t.get("p_bonferroni", t["p"]).fillna(t["p"]) < 0.05, "sim", "nao")
t.to_csv(saida / "testes_estatisticos.csv", index=False)

# ---- 3) graficos ---------------------------------------------------------------------------------
def barras(metrica, por, titulo, arquivo, ylabel):
    if metrica not in com_evento or not com_evento[metrica].notna().any():
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


for modo in MODOS:
    barras(f"atraso_pareado_{modo}_min", "tipo_evento", f"Atraso medio - {modo}, por tipo de evento",
           f"atraso_{modo}_por_evento.png", "min (+- desvio)")
barras("atraso_pareado_carro_min", "info_nivel", "Atraso medio - carro, por nivel de informacao",
       "atraso_carro_por_info.png", "min (+- desvio)")

fig, ax = plt.subplots(figsize=(7, 3.8))
for modo, cor in (("carro", "#3b6ea5"), ("moto", "#c0504d"), ("pedestre", "#6a9f3a")):
    col = f"atraso_pareado_{modo}_min"
    if col in com_evento and com_evento[col].notna().any():
        g = com_evento.groupby("severidade")[col].mean().reindex(["baixa", "media", "alta"])
        ax.plot(g.index, g.values, marker="o", label=modo, color=cor)
ax.set_title("Atraso medio por severidade e modal", fontsize=11)
ax.set_ylabel("min")
ax.legend()
ax.grid(alpha=.3)
fig.tight_layout()
fig.savefig(saida / "atraso_por_severidade_modal.png", dpi=160)
plt.close(fig)

des = [c for c in [f"pct_concluiu_carro", "pct_voltou_carro", "pct_desistiu_carro", "pct_preso_carro",
                   "pct_em_andamento_carro"] if c in com_evento]
if des:
    g = com_evento.groupby("info_nivel")[des].mean().reindex(["local", "parcial", "amplo"])
    ax = g.plot(kind="bar", stacked=True, figsize=(6.5, 3.8), colormap="viridis")
    ax.set_title("Desfecho das viagens de carro por nivel de informacao", fontsize=11)
    ax.set_ylabel("% dos agentes")
    ax.legend([c.replace("pct_", "").replace("_carro", "") for c in des], fontsize=8, loc="lower left")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(saida / "desfechos_carro_por_info.png", dpi=160)
    plt.close()

print("Analise gravada em", saida)
if len(t):
    sig = t[(t.teste == "Kruskal-Wallis") & (t.p < 0.05)]
    print("Kruskal-Wallis com p<0,05:")
    print(sig[["metrica", "fator", "estatistica", "p"]].to_string(index=False) if len(sig) else "  (nenhum)")
