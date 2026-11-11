"""
ETAPA 2 - Tabelas T1-T6 e testes estatisticos, a partir do CSV do GAMA (rede real).

    python scripts/11_tabelas.py                                   # usa includes/resultados_gama_dc.csv
    python scripts/11_tabelas.py --csv <outro.csv> --saida <pasta>  # (para testar com dados parciais)

Grava em docs/tabelas/ (CSV com numeros; .tex com a tabela pronta, virgula decimal):
    resumo_por_cenario.csv          media, desvio padrao e n de TODAS as metricas, por cenario
    T1_desfechos.csv  + T1_chuva{60,780}_{carro,moto,pedestre}.tex
    T2_informacao.csv + T2_{carro,moto,pedestre}.tex
    T3_duracao_chuva.csv + T3.tex
    T4_acessibilidade.csv + T4_{25min,plato}.tex
    T5_concentracao.csv + T5.tex
    T6_horario.csv + T6.tex
    testes_estatisticos.csv, normalidade.csv, tabelas_texto.md

DESENHO ESTATISTICO (resumo; o texto completo vai em docs/resultados_para_artigo.md)
  - Unidade de analise = a SEMENTE (replicata). Cada cenario tem 10 (ou 5) execucoes. Cenarios que o relatorio agrupa
    (ex.: niveis de informacao, redes energizada ou nao) sao primeiro MEDIDOS POR SEMENTE, para nao tratar linhas
    do mesmo cenario como independentes.
  - Normalidade: Shapiro-Wilk em cada celula (cenario x metrica); com n=10 o teste tem pouco poder, e muitas metricas
    sao limitadas em [0,100] ou constantes. Por isso o teste PRINCIPAL e nao parametrico:
    Kruskal-Wallis (3+ grupos independentes) e Mann-Whitney (2 grupos), com correcao de Holm dentro de cada familia de
    testes (Holm controla o erro da familia como Bonferroni, mas e menos conservador).
  - Tamanho de efeito: A12 de Vargha-Delaney (prob. de um valor do grupo 1 ser maior que um do grupo 2; 0,5 = sem efeito;
    limiares 0,56/0,64/0,71 = pequeno/medio/grande) e epsilon^2 = H/(N-1) para Kruskal-Wallis.
  - Sensibilidade (so no efeito da informacao e da chuva): Wilcoxon pareado por semente, porque a populacao de agentes
    e a mesma em todos os cenarios com a mesma semente.
  - "significativo" so aparece quando p_holm < 0,05 foi CALCULADO. Com n=10 e muitos testes, p-valores sao
    indicativos, nao prova: o simulador roda quantas repeticoes quisermos, entao p pequeno pode vir so do n.
"""
import argparse
import itertools
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
ap = argparse.ArgumentParser()
ap.add_argument("--csv", default=str(REPO / "includes" / "resultados_gama_dc.csv"))
ap.add_argument("--saida", default=str(REPO / "docs" / "tabelas"))
a = ap.parse_args()
SAIDA = Path(a.saida)
SAIDA.mkdir(parents=True, exist_ok=True)

MODOS = ("carro", "moto", "pedestre")
DESF = ("concluiu", "voltou", "desistiu", "preso", "em_andamento")
DESF_PT = {"concluiu": "Concluiu", "voltou": "Voltou", "desistiu": "Desistiu", "preso": "Preso", "em_andamento": "Em andamento"}
EV = ["nenhum", "alagamento", "erosao", "deslizamento", "combinado"]
EV_PT = {"nenhum": "Sem evento", "alagamento": "Alagamento", "erosao": "Erosão", "deslizamento": "Deslizamento", "combinado": "Combinado"}
SEV = ["baixa", "media", "alta"]
SEV_PT = {"baixa": "baixa", "media": "média", "alta": "alta"}
INF = ["local", "parcial", "amplo"]
GRUPOS = ["hospital", "bombeiros", "defesa_civil", "educacao", "ubs", "abrigo"]
GRUPOS_PT = {"hospital": "Hospital", "bombeiros": "Bombeiros", "defesa_civil": "Defesa Civil", "educacao": "Educação", "ubs": "UBS", "abrigo": "Abrigo"}
MOD_PT = {"carro": "Carro", "moto": "Moto", "pedestre": "Pedestre"}
PICOS = [(60, 120), (300, 360), (660, 720)]   # min apos 06:00 (7-8 h, 11-12 h, 17-18 h)
FRAC_PICO, HORIZ = 0.6, 780.0                  # HIPOTESE do modelo

# ------------------------------------------------------------------------------------------ dados
df = pd.read_csv(a.csv)
assert df.shape[1] == 69, f"esperava 69 colunas, achei {df.shape[1]}"
df["rede_energizada"] = df["rede_energizada"].astype(str).str.lower().eq("true")
df["tipo_evento"] = pd.Categorical(df["tipo_evento"], EV, ordered=True)
df["severidade"] = pd.Categorical(df["severidade"], SEV, ordered=True)
df["info_nivel"] = pd.Categorical(df["info_nivel"], INF, ordered=True)
P60 = df[(df.duracao_chuva_min == 60) & (df.inicio_evento_min == 60)].copy()
P780 = df[(df.duracao_chuva_min == 780) & (df.inicio_evento_min == 60) & (df.seed <= 5)].copy()   # bloco D (sementes 1-5)
print(f"{len(df)} linhas | chuva 60: {len(P60)} | chuva 780 (sementes 1-5): {len(P780)}")

TESTES = []     # linhas dos testes (Holm e aplicado no fim, por 'familia')


def fmt(x, casas=1):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "--"
    t = f"{x:.{casas}f}"
    if float(t) == 0:
        t = t.lstrip("-")          # evita "-0,0"
    return t.replace(".", ",")


def mdp(m, s, casas=1):
    if m is None or (isinstance(m, float) and math.isnan(m)):
        return "--"
    return f"{fmt(m, casas)} $\\pm$ {fmt(0.0 if (isinstance(s, float) and math.isnan(s)) else s, casas)}"


def tex_escape(s):
    return str(s).replace("%", "\\%").replace("_", "\\_").replace("&", "\\&")


def grava_tex(nome, tabela, legenda, rotulo, alinhar=None, tamanho="\\scriptsize", nota=None):
    """tabela: DataFrame de TEXTO ja formatado (cabecalho = nomes de coluna). Escreve .tex com booktabs."""
    cols = list(tabela.columns)
    fm = alinhar or ("l" * 2 + "r" * (len(cols) - 2) if len(cols) > 2 else "l" * len(cols))
    L = ["\\begin{table}[htbp]", "\\centering", tamanho, f"\\caption{{{legenda}}}", f"\\label{{{rotulo}}}",
         f"\\begin{{tabular}}{{{fm}}}", "\\toprule", " & ".join(tex_escape(c) if "$" not in c else c for c in cols) + " \\\\", "\\midrule"]
    for _, r in tabela.iterrows():
        L.append(" & ".join(str(v) for v in r.values) + " \\\\")
    L += ["\\bottomrule", "\\end{tabular}"]
    if nota:
        L += [f"\\par\\vspace{{2pt}}{{\\footnotesize {nota}}}"]
    L += ["\\end{table}"]
    (SAIDA / f"{nome}.tex").write_text("\n".join(L) + "\n", encoding="utf8")


def md_tabela(t):
    """DataFrame de texto -> tabela markdown (para tabelas_texto.md)."""
    cab = "| " + " | ".join(str(c) for c in t.columns) + " |"
    sep = "|" + "|".join("---" for _ in t.columns) + "|"
    linhas = ["| " + " | ".join(str(v).replace("$\\pm$", "±") for v in r.values) + " |" for _, r in t.iterrows()]
    return "\n".join([cab, sep] + linhas)


MD = []


def md(titulo, texto):
    MD.append(f"### {titulo}\n\n{texto}\n")


# ------------------------------------------------------------------------------------------ estatistica
def a12(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    r = stats.rankdata(np.concatenate([x, y]))
    return (r[: len(x)].sum() / len(x) - (len(x) + 1) / 2) / len(y)


def magn(A):
    d = abs(A - 0.5)
    return "desprezível" if d < 0.06 else ("pequeno" if d < 0.14 else ("médio" if d < 0.21 else "grande"))


def kw(grupos):
    todos = np.concatenate(grupos)
    if np.ptp(todos) == 0:
        return float("nan"), 1.0, 0.0
    H, p = stats.kruskal(*grupos)
    return float(H), float(p), float(H / (len(todos) - 1))


def mwu(x, y):
    if np.ptp(np.concatenate([x, y])) == 0:
        return float("nan"), 1.0, 0.5
    U, p = stats.mannwhitneyu(x, y, alternative="two-sided")
    return float(U), float(p), float(U / (len(x) * len(y)))


def wilc(x, y):
    """Wilcoxon pareado; efeito = correlacao por postos pareada (rank-biserial)."""
    d = np.asarray(x, float) - np.asarray(y, float)
    if np.all(d == 0):
        return float("nan"), 1.0, 0.0
    W, p = stats.wilcoxon(x, y, zero_method="wilcox")
    nz = d[d != 0]
    r = stats.rankdata(np.abs(nz))
    rb = (r[nz > 0].sum() - r[nz < 0].sum()) / r.sum()
    return float(W), float(p), float(rb)


def reg(tabela, familia, metrica, modal, estrato, teste, comparacao, nA, nB, est, p, ef, tipo_ef, mag=""):
    TESTES.append(dict(tabela=tabela, familia=familia, metrica=metrica, modal=modal, estrato=estrato, teste=teste,
                       comparacao=comparacao, n_grupo1=nA, n_grupo2=nB, estatistica=est, p=p, efeito=ef,
                       tipo_efeito=tipo_ef, magnitude=mag))


def holm(ps):
    ps = np.asarray(ps, float)
    m = len(ps)
    ordem = np.argsort(ps)
    aj = np.empty(m)
    atual = 0.0
    for rank, i in enumerate(ordem):
        atual = max(atual, (m - rank) * ps[i])
        aj[i] = min(1.0, atual)
    return aj


def por_semente(d, chaves, mets):
    """Media por (chaves, semente): junta linhas de um mesmo grupo na mesma semente (ex.: niveis de informacao)."""
    return d.groupby(chaves + ["seed"], observed=True)[mets].mean().reset_index()


def resumo(d, chaves, mets):
    """media e desvio padrao ENTRE SEMENTES (ddof=1) das medias por semente; n = no de sementes."""
    s = por_semente(d, chaves, mets)
    g = s.groupby(chaves, observed=True)
    out = g[mets].mean().add_suffix("__media").join(g[mets].std(ddof=1).add_suffix("__dp")).join(g.size().rename("n_sementes"))
    return out.reset_index()


def vals(d, met, **filtros):
    q = d
    for k, v in filtros.items():
        q = q[q[k] == v] if not isinstance(v, (list, tuple)) else q[q[k].isin(v)]
    return q[met].astype(float).values


# ------------------------------------------------------------------------------------------ resumo geral
CH_CENARIO = ["tipo_evento", "severidade", "info_nivel", "rede_energizada", "duracao_chuva_min", "inicio_evento_min"]
CONST = {"duracao_alagamento_min", "duracao_deslizamento_min", "duracao_erosao_min", "usar_picos", "frac_pico"}
METS_TODAS = [c for c in df.columns if c not in CH_CENARIO and c not in CONST and c != "seed" and df[c].dtype.kind in "fi"]
g = df.groupby(CH_CENARIO, observed=True)
rs = g[METS_TODAS].mean().add_suffix("__media").join(g[METS_TODAS].std(ddof=1).add_suffix("__dp")).join(g.size().rename("n"))
rs = rs.reset_index().sort_values(["duracao_chuva_min", "inicio_evento_min", "tipo_evento", "severidade", "info_nivel", "rede_energizada"])
rs.to_csv(SAIDA / "resumo_por_cenario.csv", index=False, float_format="%.4f")
print(f"resumo_por_cenario.csv: {len(rs)} cenarios")

# ------------------------------------------------------------------------------------------ normalidade
nor = []
for chaves, d in df.groupby(CH_CENARIO, observed=True):
    for m in MODOS:
        for dsf in ("concluiu", "desistiu", "preso"):
            x = d[f"pct_{dsf}_{m}"].values.astype(float)
            if len(x) >= 3 and np.ptp(x) > 0:
                nor.append(dict(cenario="|".join(map(str, chaves)), metrica=f"pct_{dsf}_{m}", n=len(x), shapiro_W=stats.shapiro(x)[0], p=stats.shapiro(x)[1]))
            else:
                nor.append(dict(cenario="|".join(map(str, chaves)), metrica=f"pct_{dsf}_{m}", n=len(x), shapiro_W=np.nan, p=np.nan))
nor = pd.DataFrame(nor)
nor.to_csv(SAIDA / "normalidade.csv", index=False, float_format="%.5f")
val = nor.dropna(subset=["p"])
NORM_TXT = (f"Shapiro-Wilk em {len(nor)} celulas (cenario x desfecho x modal): {len(nor) - len(val)} constantes (sem variacao, nao testaveis); "
            f"das {len(val)} testaveis, {int((val.p < 0.05).sum())} ({100 * (val.p < 0.05).mean():.0f} %) rejeitam normalidade a 5 %.")
print(NORM_TXT)

# ------------------------------------------------------------------------------------------ T1
def atraso_pareado(d, base):
    """tempo medio do cenario - tempo medio do cenario 'nenhum' na MESMA semente (por modal)."""
    out = d.copy()
    for m in MODOS:
        col = f"tempo_medio_{m}_min"
        ref = base.groupby("seed")[col].mean()
        out[f"atraso_{m}_min"] = out[col] - out["seed"].map(ref)
    return out


T1_linhas, T1_disp = [], {}
for rotulo, D in (("60", P60), ("780", P780)):
    base = D[D.tipo_evento == "nenhum"]
    D = atraso_pareado(D, base)
    mets = [f"pct_{k}_{m}" for m in MODOS for k in DESF] + [f"atraso_{m}_min" for m in MODOS] + [f"tempo_medio_{m}_min" for m in MODOS] + ["n_poligonos_com_evento"]
    R = resumo(D, ["tipo_evento", "severidade"], mets)
    R = R[R["n_sementes"] > 0].dropna(subset=["n_sementes"])
    R.insert(0, "chuva_min", int(rotulo))
    T1_linhas.append(R)
    for m in MODOS:
        linhas = []
        for _, r in R.iterrows():
            nome_ev = EV_PT[r.tipo_evento]
            sev = "--" if r.tipo_evento == "nenhum" else SEV_PT[r.severidade]
            linhas.append([nome_ev, sev] + [mdp(r[f"pct_{k}_{m}__media"], r[f"pct_{k}_{m}__dp"]) for k in DESF]
                          + [mdp(r[f"atraso_{m}_min__media"], r[f"atraso_{m}_min__dp"]) if r.tipo_evento != "nenhum" else "--"])
        t = pd.DataFrame(linhas, columns=["Evento", "Severidade"] + [DESF_PT[k] + " (%)" for k in DESF] + ["Atraso (min)"])
        T1_disp[(rotulo, m)] = t
        n_sem = int(R["n_sementes"].min())
        grava_tex(f"T1_chuva{rotulo}_{m}", t,
                  f"Desfechos das viagens de {m} (\\% dos agentes; média $\\pm$ desvio padrão entre {n_sem} sementes), chuva de {rotulo} min. "
                  "Média sobre os níveis de informação e (deslizamento/combinado) sobre rede energizada ou não. Atraso = tempo médio de quem concluiu menos o do cenário sem evento, mesma semente.",
                  f"tab:t1_{rotulo}_{m}", tamanho="\\scriptsize")
        md(f"T1 - {MOD_PT[m]}, chuva {rotulo} min (média ± dp entre sementes)", md_tabela(t))
T1 = pd.concat(T1_linhas)
# testes T1: cada evento x severidade contra "sem evento" (mesmas sementes). Familia de Holm = as 3 severidades de um
# mesmo evento, por modal e desfecho (com n=5 sementes, no bloco 780, o menor p exato do Mann-Whitney e 0,0079; Holm sobre
# 12 testes nunca daria p < 0,05, entao a familia e menor e isso e dito no texto).
for rot_, D_ in (("60", P60), ("780", P780)):
    base_ = D_[D_.tipo_evento == "nenhum"].groupby("seed")
    for m in MODOS:
        for dsf in ("concluiu", "desistiu"):
            met = f"pct_{dsf}_{m}"
            b = base_[met].mean().sort_index()
            for e in EV[1:]:
                for sv in SEV:
                    x = D_[(D_.tipo_evento == e) & (D_.severidade == sv)].groupby("seed")[met].mean().sort_index()
                    U, p, A12 = mwu(x.values, b.values)
                    reg("T1", f"T1|chuva{rot_}|{e}|{met}", met, m, f"{e}/{sv} (chuva {rot_})", "Mann-Whitney", "cenário x sem evento", len(x), len(b), U, p, A12, "A12", magn(A12))
                    W, pw, rb = wilc(x.values, b.values)
                    reg("T1", f"T1w|chuva{rot_}|{e}|{met}", met, m, f"{e}/{sv} (chuva {rot_})", "Wilcoxon pareado (sensibilidade)", "cenário x sem evento", len(x), len(b), W, pw, rb, "rank-biserial", "")
T1.to_csv(SAIDA / "T1_desfechos.csv", index=False, float_format="%.4f")

# ------------------------------------------------------------------------------------------ T2
d2 = P60[P60.tipo_evento != "nenhum"].copy()
mets2 = []
for m in MODOS:
    mets2 += [f"pct_{k}_{m}" for k in DESF] + [f"replanejamentos_{m}", f"travessias_perigosas_{m}", f"tempo_medio_{m}_min"]
R2 = resumo(d2, ["tipo_evento", "severidade", "info_nivel"], mets2)
R2["tipo_evento"] = R2["tipo_evento"].astype(str)
R2.to_csv(SAIDA / "T2_informacao.csv", index=False, float_format="%.4f")
estratos = [(e, s) for e in EV[1:] for s in SEV]
for m in MODOS:
    # (i) por estrato (evento x severidade): Kruskal-Wallis entre os 3 niveis; n=10 por nivel (media por semente sobre a rede)
    S = por_semente(d2, ["tipo_evento", "severidade", "info_nivel"], [f"pct_concluiu_{m}", f"pct_desistiu_{m}", f"replanejamentos_{m}"])
    for met in (f"pct_concluiu_{m}", f"pct_desistiu_{m}", f"replanejamentos_{m}"):
        for e, s in estratos:
            gs = [S[(S.tipo_evento == e) & (S.severidade == s) & (S.info_nivel == i)][met].values for i in INF]
            H, p, eps = kw(gs)
            reg("T2", f"T2|estrato|{met}", met, m, f"{e}/{s}", "Kruskal-Wallis", "local x parcial x amplo", len(gs[0]), len(gs[1]), H, p, eps, "epsilon2")
    # (ii) agregado: media por semente sobre todos os estratos (n=10 por nivel)
    A = d2.groupby(["info_nivel", "seed"], observed=True)[[f"pct_concluiu_{m}", f"pct_desistiu_{m}", f"pct_preso_{m}", f"replanejamentos_{m}"]].mean().reset_index()
    for met in (f"pct_concluiu_{m}", f"pct_desistiu_{m}", f"pct_preso_{m}", f"replanejamentos_{m}"):
        gs = [A[A.info_nivel == i].sort_values("seed")[met].values for i in INF]
        H, p, eps = kw(gs)
        reg("T2", f"T2|agregado-kw|{met}", met, m, "todos os estratos", "Kruskal-Wallis", "local x parcial x amplo", len(gs[0]), len(gs[1]), H, p, eps, "epsilon2")
        for (i, j) in itertools.combinations(range(3), 2):
            U, p, A12 = mwu(gs[i], gs[j])
            reg("T2", f"T2|agregado-mw|{met}", met, m, "todos os estratos", "Mann-Whitney", f"{INF[i]} x {INF[j]}", len(gs[i]), len(gs[j]), U, p, A12, "A12", magn(A12))
            W, pw, rb = wilc(gs[i], gs[j])
            reg("T2", f"T2|agregado-wilcoxon|{met}", met, m, "todos os estratos", "Wilcoxon pareado (sensibilidade)", f"{INF[i]} x {INF[j]}", len(gs[i]), len(gs[j]), W, pw, rb, "rank-biserial", "")
    # LaTeX: % concluiu por estrato x nivel, + p (KW, Holm entre os 12 estratos)
    linhas = []
    for e, s in estratos:
        sub = R2[(R2.tipo_evento == e) & (R2.severidade == s)].set_index("info_nivel")
        linhas.append([EV_PT[e], SEV_PT[s]] + [mdp(sub.loc[i, f"pct_concluiu_{m}__media"], sub.loc[i, f"pct_concluiu_{m}__dp"]) for i in INF] + ["@@" + f"{e}/{s}"])
    t = pd.DataFrame(linhas, columns=["Evento", "Severidade", "Local (%)", "Parcial (%)", "Amplo (%)", "p Holm"])
    T2_pre = t   # p preenchido depois do Holm
    globals()[f"T2_pre_{m}"] = t

# ------------------------------------------------------------------------------------------ T3
B = df[(df.inicio_evento_min == 60) & (df.severidade == "alta") & (df.info_nivel == "parcial") & (~df.rede_energizada)
       & (df.tipo_evento.isin(["combinado", "alagamento"])) & (df.duracao_chuva_min.isin([0, 60, 120, 240, 780]))].copy()
mets3 = [f"pct_{k}_{m}" for m in MODOS for k in DESF] + ["n_poligonos_com_evento", "gini_fluxo"] + [f"sem_acesso_hospital_{m}{s}_pct" for m in ("carro", "pedestre") for s in ("", "_plato")]
R3 = resumo(B, ["tipo_evento", "duracao_chuva_min"], mets3)
R3["tipo_evento"] = R3["tipo_evento"].astype(str)
R3.to_csv(SAIDA / "T3_duracao_chuva.csv", index=False, float_format="%.4f")
CH = [0, 60, 120, 240, 780]
for e in ("combinado", "alagamento"):
    for m in MODOS:
        for dsf in ("concluiu", "desistiu", "preso"):
            met = f"pct_{dsf}_{m}"
            gs = [vals(B, met, tipo_evento=e, duracao_chuva_min=c) for c in CH]
            H, p, eps = kw(gs)
            reg("T3", f"T3|kw|{met}", met, m, e, "Kruskal-Wallis", "chuva 0 x 60 x 120 x 240 x 780", len(gs[0]), len(gs[-1]), H, p, eps, "epsilon2")
            for (i, j) in itertools.combinations(range(5), 2):
                U, p, A12 = mwu(gs[i], gs[j])
                reg("T3", f"T3|mw|{e}|{met}", met, m, e, "Mann-Whitney", f"chuva {CH[i]} x {CH[j]}", len(gs[i]), len(gs[j]), U, p, A12, "A12", magn(A12))
                if met == f"pct_concluiu_{m}":
                    W, pw, rb = wilc(gs[i], gs[j])
                    reg("T3", f"T3|wilcoxon|{e}|{met}", met, m, e, "Wilcoxon pareado (sensibilidade)", f"chuva {CH[i]} x {CH[j]}", len(gs[i]), len(gs[j]), W, pw, rb, "rank-biserial", "")
linhas = []
for e in ("combinado", "alagamento"):
    for c in CH:
        r = R3[(R3.tipo_evento == e) & (R3.duracao_chuva_min == c)].iloc[0]
        linhas.append([EV_PT[e], str(c)] + [mdp(r[f"pct_concluiu_{m}__media"], r[f"pct_concluiu_{m}__dp"]) for m in MODOS]
                      + [mdp(r["pct_desistiu_carro__media"], r["pct_desistiu_carro__dp"]), mdp(r["pct_preso_carro__media"], r["pct_preso_carro__dp"]),
                         fmt(r["n_poligonos_com_evento__media"]), str(int(r["n_sementes"]))])
T3 = pd.DataFrame(linhas, columns=["Evento", "Chuva (min)", "Carro concluiu (%)", "Moto concluiu (%)", "Pedestre concluiu (%)", "Carro desistiu (%)", "Carro preso (%)", "Polígonos ativos", "n"])
grava_tex("T3", T3, "Sensibilidade à duração da chuva (severidade alta, informação parcial, sem rede energizada; média $\\pm$ dp entre sementes). "
          "60 e 780 min estão ancorados nas matérias; 0, 120 e 240 são sensibilidade (hipótese).", "tab:t3")
md("T3 - duração da chuva (média ± dp entre sementes)", md_tabela(T3))

# ------------------------------------------------------------------------------------------ T4
T4_linhas = []
for rotulo, D in (("60", P60), ("780", P780)):
    mets4 = [f"sem_acesso_{gr}_{m}{s}_pct" for gr in GRUPOS for m in ("carro", "pedestre") for s in ("", "_plato")]
    R4 = resumo(D, ["tipo_evento", "severidade"], mets4)
    R4.insert(0, "chuva_min", int(rotulo))
    T4_linhas.append(R4)
T4 = pd.concat(T4_linhas)
T4["tipo_evento"] = T4["tipo_evento"].astype(str)
T4.to_csv(SAIDA / "T4_acessibilidade.csv", index=False, float_format="%.4f")
for medida, suf, nomef in (("+25 min após o início do evento", "", "25min"), ("no platô da chuva (+60 min)", "_plato", "plato")):
    for rotulo in ("60", "780"):
        R4 = T4[T4.chuva_min == int(rotulo)]
        linhas = []
        for _, r in R4.iterrows():
            linha = [EV_PT[r.tipo_evento], "--" if r.tipo_evento == "nenhum" else SEV_PT[r.severidade]]
            for gr in GRUPOS:
                for m in ("carro", "pedestre"):
                    linha.append(mdp(r[f"sem_acesso_{gr}_{m}{suf}_pct__media"], r[f"sem_acesso_{gr}_{m}{suf}_pct__dp"], 0))
            linhas.append(linha)
        cab = ["Evento", "Sev."] + [f"{GRUPOS_PT[gr]} {'C' if m == 'carro' else 'P'}" for gr in GRUPOS for m in ("carro", "pedestre")]
        t = pd.DataFrame(linhas, columns=cab)
        grava_tex(f"T4_{nomef}_chuva{rotulo}", t, f"Agentes sem acesso (\\% dos nós amostrados), medido {medida}, chuva {rotulo} min. C = carro, P = a pé. Média $\\pm$ dp entre sementes.",
                  f"tab:t4_{nomef}_{rotulo}", tamanho="\\tiny", alinhar="ll" + "r" * 12)
        md(f"T4 - sem acesso (%) medido {medida}, chuva {rotulo} min (C=carro, P=a pé; média ± dp)", md_tabela(t))
# testes T4: efeito da severidade (KW 3 niveis) por evento, grupo, modal e medida (chuva 60); familia unica = Holm no T4
for e in EV[1:]:
    S = por_semente(P60[P60.tipo_evento == e], ["severidade"], [f"sem_acesso_{gr}_{m}{s}_pct" for gr in GRUPOS for m in ("carro", "pedestre") for s in ("", "_plato")])
    for gr in GRUPOS:
        for m in ("carro", "pedestre"):
            for s in ("", "_plato"):
                met = f"sem_acesso_{gr}_{m}{s}_pct"
                gs = [S[S.severidade == v][met].values for v in SEV]
                H, p, eps = kw(gs)
                reg("T4", "T4|severidade", met, m, e, "Kruskal-Wallis", "baixa x media x alta", len(gs[0]), len(gs[2]), H, p, eps, "epsilon2")
# testes T4: +25 min x platao (Wilcoxon pareado por execucao; combinado/alta, chuva 60, medias por semente)
for e in ("alagamento", "deslizamento", "combinado"):
    D = P60[(P60.tipo_evento == e) & (P60.severidade == "alta")].groupby("seed").mean(numeric_only=True)
    for gr in GRUPOS:
        for m in ("carro", "pedestre"):
            x, y = D[f"sem_acesso_{gr}_{m}_pct"].values, D[f"sem_acesso_{gr}_{m}_plato_pct"].values
            W, p, rb = wilc(x, y)
            reg("T4", "T4|25-vs-plato", f"sem_acesso_{gr}_{m} (+25 min vs platô)", m, f"{e}/alta", "Wilcoxon pareado", "+25 min x platô", len(x), len(y), W, p, rb, "rank-biserial")

# ------------------------------------------------------------------------------------------ T5
T5_linhas = []
for rotulo, D in (("60", P60), ("780", P780)):
    R5 = resumo(D, ["tipo_evento", "severidade"], ["gini_fluxo", "pct_fluxo_top10_vias"])
    R5.insert(0, "chuva_min", int(rotulo))
    T5_linhas.append(R5)
    base = D[D.tipo_evento == "nenhum"].groupby("seed")[["gini_fluxo", "pct_fluxo_top10_vias"]].mean()
    for met in ("gini_fluxo", "pct_fluxo_top10_vias"):
        for e in EV[1:]:
            for s in SEV:
                x = D[(D.tipo_evento == e) & (D.severidade == s)].groupby("seed")[met].mean().values
                U, p, A12 = mwu(x, base[met].values)
                reg("T5", f"T5|vs-nenhum|chuva{rotulo}|{met}", met, "-", f"{e}/{s} (chuva {rotulo})", "Mann-Whitney", "cenário x sem evento", len(x), len(base), U, p, A12, "A12", magn(A12))
T5 = pd.concat(T5_linhas)
T5["tipo_evento"] = T5["tipo_evento"].astype(str)
T5.to_csv(SAIDA / "T5_concentracao.csv", index=False, float_format="%.4f")
linhas = []
for ch in (60, 780):
    for _, r in T5[T5.chuva_min == ch].iterrows():
        linhas.append([str(ch), EV_PT[r.tipo_evento], "--" if r.tipo_evento == "nenhum" else SEV_PT[r.severidade],
                       mdp(r["gini_fluxo__media"], r["gini_fluxo__dp"], 3), mdp(r["pct_fluxo_top10_vias__media"], r["pct_fluxo_top10_vias__dp"])])
T5d = pd.DataFrame(linhas, columns=["Chuva (min)", "Evento", "Sev.", "Gini do fluxo", "Fluxo nas 10 vias mais usadas (%)"])
grava_tex("T5", T5d, "Concentração do fluxo: Gini das passagens por trecho e \\% do fluxo nas 10 vias mais usadas (média $\\pm$ dp entre sementes).", "tab:t5", alinhar="lllrr")
md("T5 - concentração do fluxo", md_tabela(T5d))

# ------------------------------------------------------------------------------------------ T6
def sobreposicao(a_, b_):
    return max(0.0, min(b_, HORIZ) - max(a_, 0.0))


def exposicao(ini, chuva):
    """% das SAIDAS (modelo: 60 % em 3 picos de peso igual + 40 % uniformes) que cai dentro da chuva. Hipotese do modelo."""
    fim = min(ini + chuva, HORIZ)
    pic = sum(sobreposicao(max(ini, p0), min(fim, p1)) / (p1 - p0) for p0, p1 in PICOS) / 3.0
    return 100.0 * (FRAC_PICO * pic + (1 - FRAC_PICO) * sobreposicao(ini, fim) / HORIZ)


def picos_atingidos(ini, chuva):
    fim = min(ini + chuva, HORIZ)
    nomes = ["manhã (7-8 h)", "meio-dia (11-12 h)", "tarde (17-18 h)"]
    r = [n for n, (p0, p1) in zip(nomes, PICOS) if min(fim, p1) > max(ini, p0)]
    return ", ".join(r) if r else "nenhum"


def hhmm(ini):
    m = int(ini) + 360
    return f"{m // 60:02d}:{m % 60:02d}"


H6 = df[(df.severidade == "alta") & (df.info_nivel == "parcial") & (~df.rede_energizada) & (df.tipo_evento.isin(["combinado", "alagamento"]))
        & (df.duracao_chuva_min.isin([60, 780])) & (df.inicio_evento_min.isin([30, 60, 270, 630]))].copy()
mets6 = [f"pct_{k}_{m}" for m in MODOS for k in DESF] + ["n_poligonos_com_evento"] + [f"sem_acesso_hospital_{m}{s}_pct" for m in ("carro", "pedestre") for s in ("", "_plato")]
R6 = resumo(H6, ["tipo_evento", "duracao_chuva_min", "inicio_evento_min"], mets6)
R6["tipo_evento"] = R6["tipo_evento"].astype(str)
R6["exposicao_saidas_pct"] = [exposicao(i, c) for i, c in zip(R6.inicio_evento_min, R6.duracao_chuva_min)]
R6["picos_atingidos"] = [picos_atingidos(i, c) for i, c in zip(R6.inicio_evento_min, R6.duracao_chuva_min)]
R6.to_csv(SAIDA / "T6_horario.csv", index=False, float_format="%.4f")
INI = [30, 60, 270, 630]
for e in ("combinado", "alagamento"):
    for c in (60, 780):
        for m in MODOS:
            for dsf in ("concluiu", "desistiu"):
                met = f"pct_{dsf}_{m}"
                gs = [vals(H6, met, tipo_evento=e, duracao_chuva_min=c, inicio_evento_min=i) for i in INI]
                H, p, eps = kw(gs)
                reg("T6", f"T6|kw|{met}", met, m, f"{e}, chuva {c}", "Kruskal-Wallis", "início 06:30 x 07:00 x 10:30 x 16:30", len(gs[0]), len(gs[-1]), H, p, eps, "epsilon2")
                for (i, j) in itertools.combinations(range(4), 2):
                    U, p, A12 = mwu(gs[i], gs[j])
                    reg("T6", f"T6|mw|{met}", met, m, f"{e}, chuva {c}", "Mann-Whitney", f"início {hhmm(INI[i])} x {hhmm(INI[j])}", len(gs[i]), len(gs[j]), U, p, A12, "A12", magn(A12))
linhas = []
for _, r in R6.sort_values(["tipo_evento", "duracao_chuva_min", "inicio_evento_min"]).iterrows():
    linhas.append([EV_PT[r.tipo_evento], str(int(r.duracao_chuva_min)), hhmm(r.inicio_evento_min), r.picos_atingidos, fmt(r.exposicao_saidas_pct, 0)]
                  + [mdp(r[f"pct_concluiu_{m}__media"], r[f"pct_concluiu_{m}__dp"]) for m in MODOS]
                  + [mdp(r["pct_desistiu_carro__media"], r["pct_desistiu_carro__dp"]), str(int(r["n_sementes"]))])
T6 = pd.DataFrame(linhas, columns=["Evento", "Chuva (min)", "Início", "Picos atingidos pela chuva", "Saídas na chuva (%)", "Carro concluiu (%)", "Moto concluiu (%)", "Pedestre concluiu (%)", "Carro desistiu (%)", "n"])
grava_tex("T6", T6, "Efeito do horário de início do evento (severidade alta, informação parcial). \"Saídas na chuva\" é a fração das viagens que saem durante a chuva, calculada com a distribuição de saídas do modelo (picos e fração nos picos são hipótese). Início às 07:00 é o cenário padrão.",
          "tab:t6", alinhar="llllrrrrrr")
md("T6 - horário do evento (média ± dp entre sementes)", md_tabela(T6))

# ------------------------------------------------------------------------------------------ extra: rede energizada
rede = []
for e in ("deslizamento", "combinado"):
    for s in SEV:
        d = P60[(P60.tipo_evento == e) & (P60.severidade == s)]
        S = d.groupby(["rede_energizada", "seed"])[["pct_concluiu_carro", "pct_desistiu_carro", "sem_acesso_hospital_carro_pct"]].mean().reset_index()
        for met in ("pct_concluiu_carro", "pct_desistiu_carro", "sem_acesso_hospital_carro_pct"):
            x, y = S[S.rede_energizada][met].values, S[~S.rede_energizada][met].values
            U, p, A12 = mwu(x, y)
            reg("EXTRA-rede", "EXTRA-rede", met, "carro", f"{e}/{s}", "Mann-Whitney", "rede energizada x não", len(x), len(y), U, p, A12, "A12", magn(A12))

# ------------------------------------------------------------------------------------------ Holm + gravacao dos testes
TT = pd.DataFrame(TESTES)
TT["p_holm"] = np.nan
for fam, idx in TT.groupby("familia").groups.items():
    TT.loc[idx, "p_holm"] = holm(TT.loc[idx, "p"].values)
TT["significativo_5pct_holm"] = np.where(TT.p_holm < 0.05, "sim", "não")
TT.to_csv(SAIDA / "testes_estatisticos.csv", index=False, float_format="%.6g")
print(f"testes_estatisticos.csv: {len(TT)} testes, {int((TT.p_holm < 0.05).sum())} com p_holm < 0,05")

# T2: preenche p Holm (KW por estrato) e grava LaTeX
for m in MODOS:
    t = globals()[f"T2_pre_{m}"].copy()
    met = f"pct_concluiu_{m}"
    sub = TT[(TT.tabela == "T2") & (TT.familia == f"T2|estrato|{met}")].set_index("estrato")
    t["p Holm"] = [("<0,001" if sub.loc[k[2:], "p_holm"] < 0.001 else fmt(sub.loc[k[2:], "p_holm"], 3)) for k in t["p Holm"]]
    grava_tex(f"T2_{m}", t, f"Efeito do nível de informação em \\% de viagens de {m} que concluem (chuva 60 min; média $\\pm$ dp entre 10 sementes; "
              "p de Kruskal-Wallis com correção de Holm entre os 12 estratos).", f"tab:t2_{m}")
    md(f"T2 - nível de informação, % que conclui ({MOD_PT[m]}), chuva 60 min", md_tabela(t))

# ------------------------------------------------------------------------------------------ texto
resumo_md = [f"# Tabelas T1-T6 (geradas por scripts/11_tabelas.py)\n", f"Fonte: `{Path(a.csv).name}` (GAMA, rede real). {len(df)} execuções.\n",
             f"Normalidade: {NORM_TXT}\n",
             f"Testes calculados: {len(TT)}; com p_Holm < 0,05: {int((TT.p_holm < 0.05).sum())}. Detalhes em `testes_estatisticos.csv`.\n"]
(SAIDA / "tabelas_texto.md").write_text("\n".join(resumo_md + MD), encoding="utf8")
print("tabelas gravadas em", SAIDA)
