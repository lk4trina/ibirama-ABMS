"""
ETAPA 3 - Figuras A-F do artigo (PNG 300 dpi, rotulos em portugues, paleta Okabe-Ito para daltonismo).

    python scripts/12_figuras.py                                  # includes/resultados_gama_dc.csv -> docs/figuras/
    python scripts/12_figuras.py --diag <pasta com agentes_*.csv>  # Figura E (saidas por agente, copia diagnostica do GAMA)

A  % que conclui por evento e severidade, chuva 60 x 780 (pontos = media entre sementes; barras = desvio padrao)
B  % que conclui x duracao da chuva (T3)
C  efeito do nivel de informacao por modal (% concluiu e replanejamentos)
D  efeito do horario de inicio do evento (T6), com os 3 picos sombreados
E  histograma das saidas (3 picos) e curva de viagens em andamento ao longo do dia
F  mapa dos trechos fechados e desvios de exemplo (de resultados/desvios_exemplos.geojson; planejamento, NAO e resultado do GAMA)
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
ap = argparse.ArgumentParser()
ap.add_argument("--csv", default=str(REPO / "includes" / "resultados_gama_dc.csv"))
ap.add_argument("--saida", default=str(REPO / "docs" / "figuras"))
ap.add_argument("--diag", default="/mnt/c/Temp/ibirama_final/diag")
ap.add_argument("--so", default="ABCDEF", help="quais figuras gerar")
a = ap.parse_args()
OUT = Path(a.saida)
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
                     "legend.fontsize": 7.5, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": 0.25, "grid.linewidth": 0.5, "savefig.dpi": 300, "figure.dpi": 100})
OI = {"azul": "#0072B2", "laranja": "#E69F00", "verm": "#D55E00", "verde": "#009E73", "ceu": "#56B4E9", "rosa": "#CC79A7", "cinza": "#666666", "amarelo": "#F0E442"}
MODOS = ("carro", "moto", "pedestre")
MOD_PT = {"carro": "Carro", "moto": "Moto", "pedestre": "A pé"}
EV = ["nenhum", "alagamento", "erosao", "deslizamento", "combinado"]
EV_PT = {"nenhum": "Sem\nevento", "alagamento": "Alag.", "erosao": "Eros.", "deslizamento": "Desl.", "combinado": "Comb."}
EV_NOME = {"alagamento": "Alagamento", "erosao": "Erosão", "deslizamento": "Deslizamento", "combinado": "Combinado"}
SEV = ["baixa", "media", "alta"]
SEV_COR = {"baixa": OI["ceu"], "media": OI["laranja"], "alta": OI["verm"]}
SEV_MK = {"baixa": "o", "media": "s", "alta": "^"}
SEV_PT = {"baixa": "baixa", "media": "média", "alta": "alta"}
EV_COR = {"alagamento": OI["azul"], "erosao": OI["laranja"], "deslizamento": OI["verde"], "combinado": OI["verm"]}
EV_MK = {"alagamento": "o", "erosao": "s", "deslizamento": "^", "combinado": "D"}
PICOS = [(60, 120), (300, 360), (660, 720)]

df = pd.read_csv(a.csv)
df["rede_energizada"] = df["rede_energizada"].astype(str).str.lower().eq("true")
P60 = df[(df.duracao_chuva_min == 60) & (df.inicio_evento_min == 60)]
P780 = df[(df.duracao_chuva_min == 780) & (df.inicio_evento_min == 60) & (df.seed <= 5)]


def ms(d, chaves, met):
    """media e dp ENTRE SEMENTES (primeiro media por semente dentro de cada grupo)."""
    s = d.groupby(chaves + ["seed"])[met].mean().reset_index()
    g = s.groupby(chaves)[met]
    return pd.DataFrame({"m": g.mean(), "sd": g.std(ddof=1), "n": g.size()}).reset_index()


def salva(fig, nome):
    from matplotlib.ticker import FuncFormatter
    for ax_ in fig.axes:   # virgula decimal nos eixos verticais; percentuais nao passam de 100
        if "%" in ax_.get_ylabel() and ax_.get_ylim()[1] > 100.5:
            ax_.set_ylim(top=100.5)
        ax_.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:g}".replace(".", ",")))
    fig.savefig(OUT / nome, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("gravada", OUT / nome)


def hora(min_):
    m = int(min_) + 360
    return f"{m // 60:02d}:{m % 60:02d}"


# ------------------------------------------------------------------------------------------ A
if "A" in a.so:
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 5.2), sharex=True)
    for r, (rot, D) in enumerate((("60", P60), ("780", P780))):
        n_sem = D.seed.nunique()
        for c, m in enumerate(MODOS):
            ax = axs[r, c]
            t = ms(D, ["tipo_evento", "severidade"], f"pct_concluiu_{m}")
            for i, e in enumerate(EV):
                if e == "nenhum":
                    x = t[t.tipo_evento == e]
                    ax.errorbar(i, x.m.iloc[0], yerr=x.sd.iloc[0], fmt="D", color=OI["cinza"], capsize=2.5, ms=4.5, lw=1)
                    continue
                for k, s in enumerate(SEV):
                    x = t[(t.tipo_evento == e) & (t.severidade == s)]
                    ax.errorbar(i + (k - 1) * 0.22, x.m.iloc[0], yerr=x.sd.iloc[0], fmt=SEV_MK[s], color=SEV_COR[s], capsize=2.5, ms=4.5, lw=1,
                                label=f"severidade {SEV_PT[s]}" if (i == 1) else None)
            ax.set_xticks(range(len(EV)))
            ax.set_xticklabels([EV_PT[e] for e in EV], fontsize=7)
            ax.set_title(f"{MOD_PT[m]} | chuva {rot} min (n={n_sem} sem.)", fontsize=8)
            if c == 0:
                ax.set_ylabel("viagens que concluem (%)")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.text(0.5, -0.06, "Pontos: média entre sementes; barras: ± 1 desvio padrão. O eixo vertical não começa em zero e cada painel tem sua escala.", ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    salva(fig, "A_conclusao_por_evento_severidade.png")

# ------------------------------------------------------------------------------------------ B
if "B" in a.so:
    CH = [0, 60, 120, 240, 780]
    B = df[(df.inicio_evento_min == 60) & (df.severidade == "alta") & (df.info_nivel == "parcial") & (~df.rede_energizada)
           & df.tipo_evento.isin(["combinado", "alagamento"]) & df.duracao_chuva_min.isin(CH)]
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.7))
    for c, m in enumerate(MODOS):
        ax = axs[c]
        for e in ("alagamento", "combinado"):
            t = ms(B[B.tipo_evento == e], ["duracao_chuva_min"], f"pct_concluiu_{m}").set_index("duracao_chuva_min").loc[CH]
            xs = np.arange(len(CH)) + (-0.06 if e == "alagamento" else 0.06)
            ax.errorbar(xs, t.m, yerr=t.sd, color=EV_COR[e], lw=1, capsize=2.5, label=EV_NOME[e])
            for k, ch in enumerate(CH):   # cheio = ancorado nas materias (60 e 780); vazado = sensibilidade (hipotese)
                anc = ch in (60, 780)
                ax.plot(xs[k], t.m.iloc[k], EV_MK[e], ms=5, mfc=EV_COR[e] if anc else "white", mec=EV_COR[e])
        ax.set_xticks(range(len(CH)))
        ax.set_xticklabels([str(x) for x in CH])
        ax.set_xlabel("duração da chuva (min)")
        ax.set_title(MOD_PT[m], fontsize=8)
        if c == 0:
            ax.set_ylabel("viagens que concluem (%)")
    axs[0].legend(frameon=False, loc="lower left")
    fig.text(0.5, -0.07, "Símbolo cheio: valor ancorado nas matérias (60 e 780 min); vazado: sensibilidade (hipótese). Severidade alta, informação parcial; média ± dp de 10 sementes.",
             ha="center", fontsize=7)
    fig.tight_layout()
    salva(fig, "B_conclusao_por_duracao_chuva.png")

# ------------------------------------------------------------------------------------------ C
if "C" in a.so:
    INF = ["local", "parcial", "amplo"]
    D = P60[(P60.severidade == "alta") & (P60.tipo_evento != "nenhum")].copy()
    for m in MODOS:
        D[f"replan100_{m}"] = 100.0 * D[f"replanejamentos_{m}"] / D[f"n_{m}"]
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 4.6), sharex=True)
    for c, m in enumerate(MODOS):
        for r, (met, yl) in enumerate(((f"pct_concluiu_{m}", "viagens que concluem (%)"), (f"replan100_{m}", "replanejamentos por 100 agentes"))):
            ax = axs[r, c]
            for e in ("alagamento", "erosao", "deslizamento", "combinado"):
                t = ms(D[D.tipo_evento == e], ["info_nivel"], met).set_index("info_nivel").loc[INF]
                xs = np.arange(3) + (list(EV_COR).index(e) - 1.5) * 0.06
                ax.errorbar(xs, t.m, yerr=t.sd, fmt=EV_MK[e] + "-", color=EV_COR[e], lw=1, ms=4, capsize=2, label=EV_NOME[e])
            ax.set_xticks(range(3))
            ax.set_xticklabels(["local", "parcial", "amplo"])
            if r == 0:
                ax.set_title(MOD_PT[m], fontsize=8)
            if c == 0:
                ax.set_ylabel(yl)
            if r == 1:
                ax.set_xlabel("nível de informação")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.text(0.5, -0.06, "Severidade alta, chuva 60 min; média ± dp de 10 sementes. O eixo vertical não começa em zero.", ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    salva(fig, "C_efeito_da_informacao.png")

# ------------------------------------------------------------------------------------------ D
if "D" in a.so:
    H = df[(df.severidade == "alta") & (df.info_nivel == "parcial") & (~df.rede_energizada) & df.tipo_evento.isin(["combinado", "alagamento"])
           & df.duracao_chuva_min.isin([60, 780]) & df.inicio_evento_min.isin([30, 60, 270, 630])]
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 4.6), sharex=True)
    for r, ch in enumerate((60, 780)):
        for c, m in enumerate(MODOS):
            ax = axs[r, c]
            for p0, p1 in PICOS:
                ax.axvspan(p0, p1, color=OI["amarelo"], alpha=0.35, lw=0)
            for e in ("alagamento", "combinado"):
                t = ms(H[(H.tipo_evento == e) & (H.duracao_chuva_min == ch)], ["inicio_evento_min"], f"pct_concluiu_{m}").sort_values("inicio_evento_min")
                off = -6 if e == "alagamento" else 6
                ax.errorbar(t.inicio_evento_min + off, t.m, yerr=t.sd, fmt=EV_MK[e], color=EV_COR[e], capsize=2.5, ms=4.5, lw=1, label=EV_NOME[e])
            ax.set_xticks([0, 240, 480, 720])
            ax.set_xticklabels([hora(x) for x in [0, 240, 480, 720]], fontsize=7)
            ax.set_title(f"{MOD_PT[m]} | chuva {ch} min", fontsize=8)
            if c == 0:
                ax.set_ylabel("viagens que concluem (%)")
            if r == 1:
                ax.set_xlabel("início do evento (hora)")
    h, l = axs[0, 0].get_legend_handles_labels()
    h.append(plt.Rectangle((0, 0), 1, 1, color=OI["amarelo"], alpha=0.5))
    l.append("picos de saída (7-8, 11-12, 17-18 h)")
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.text(0.5, -0.06, "Severidade alta, informação parcial; média ± dp entre sementes. Horários de início e picos são hipótese do modelo.", ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    salva(fig, "D_efeito_do_horario.png")

# ------------------------------------------------------------------------------------------ E
if "E" in a.so:
    pasta = Path(a.diag)
    arqs = {"Sem evento": pasta / "agentes_nenhum_s1.csv", "Combinado, alta, chuva 60 min": pasta / "agentes_combinado_s1.csv"}
    if not all(p.exists() for p in arqs.values()):
        print("Figura E: arquivos de saida por agente nao encontrados em", pasta, "- pulei.")
    else:
        dados = {k: pd.read_csv(p, names=["modo", "t_partida", "t_chegada", "estado"]) for k, p in arqs.items()}
        base = list(dados.values())[0]
        fig, axs = plt.subplots(2, 1, figsize=(6.6, 5.0), sharex=True)
        ax = axs[0]
        bins = np.arange(0, 781, 15)
        for p0, p1 in PICOS:
            ax.axvspan(p0, p1, color=OI["amarelo"], alpha=0.35, lw=0)
        ax.hist(base.t_partida / 60.0, bins=bins, color=OI["azul"], edgecolor="white", lw=0.4)
        ax.set_ylabel("saídas por 15 min (agentes)")
        ax.set_title(f"Horário de saída dos {len(base)} agentes (GAMA, semente 1)", fontsize=9)
        ax = axs[1]
        tt = np.arange(0, 781, 5.0)
        estilos = [(OI["cinza"], "--"), (OI["verm"], "-")]
        for (nome, d), (cor, ls) in zip(dados.items(), estilos):
            ini = d.t_partida.values / 60.0
            fim = np.where(d.estado.isin(["concluiu", "voltou", "desistiu", "preso"]), d.t_chegada.values / 60.0, np.inf)
            emv = [int(((ini <= t) & (fim > t)).sum()) for t in tt]
            ax.plot(tt, emv, color=cor, ls=ls, lw=1.4, label=nome)
        for p0, p1 in PICOS:
            ax.axvspan(p0, p1, color=OI["amarelo"], alpha=0.35, lw=0)
        ax.set_ylabel("agentes em viagem ou esperando rota")
        ax.set_xlabel("hora do dia")
        ax.set_xticks(range(0, 781, 120))
        ax.set_xticklabels([hora(x) for x in range(0, 781, 120)])
        ax.legend(frameon=False, loc="upper right")
        fig.text(0.5, -0.01, "Faixas amarelas: picos 7-8, 11-12 e 17-18 h (pesos e fração de 60 % nos picos são hipótese). Uma execução de cada cenário.", ha="center", fontsize=7)
        fig.tight_layout()
        salva(fig, "E_saidas_e_viagens_no_dia.png")

# ------------------------------------------------------------------------------------------ F
if "F" in a.so:
    import geopandas as gpd
    g = gpd.read_file(REPO / "resultados" / "desvios_exemplos.geojson").to_crs(31982)
    vias = gpd.read_file(REPO / "includes" / "dados" / "vias.shp").to_crs(31982)
    risc = gpd.read_file(REPO / "includes" / "dados" / "riscos.shp").to_crs(31982)
    pcs = gpd.read_file(REPO / "includes" / "dados" / "pontos_criticos.geojson").to_crs(31982)
    alvo = ["interdicao: Rua Santa Cruz (so <=40m do risco)", "interdicao: Rua Duque de Caxias (so <=40m do risco)",
            "interdicao: Rua Marquês do Herval (so <=40m do risco)", "interdicao: Ponte Ibirama-Apiúna (so <=40m do risco)"]
    fig, axs = plt.subplots(2, 2, figsize=(7.2, 6.4))
    for ax, cen in zip(axs.ravel(), alvo):
        s = g[g.cenario == cen]
        env = s.total_bounds
        mx, my = max(150, (env[2] - env[0]) * 0.35), max(150, (env[3] - env[1]) * 0.35)
        xmin, ymin, xmax, ymax = env[0] - mx, env[1] - my, env[2] + mx, env[3] + my
        vias.cx[xmin:xmax, ymin:ymax].plot(ax=ax, color="#bbbbbb", lw=0.6)
        risc.cx[xmin:xmax, ymin:ymax].plot(ax=ax, color=OI["laranja"], alpha=0.18, lw=0)
        s[s.parte == "caminho_original"].plot(ax=ax, color="#222222", lw=1.6, ls="--")
        s[s.parte == "desvio"].plot(ax=ax, color=OI["verde"], lw=2.2)
        s[s.parte == "trecho_fechado"].plot(ax=ax, color=OI["verm"], lw=3.5)
        dest = s.destino.iloc[0]
        pc = pcs[pcs.nome == dest]
        if len(pc):
            pc.plot(ax=ax, color="black", marker="*", markersize=70, zorder=5)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        ax.set_axis_off()
        nome = cen.replace("interdicao: ", "").replace(" (so <=40m do risco)", "")
        ax.set_title(f"{nome}\n+{s.acrescimo_dist_m.iloc[0]:.0f} m, +{s.acrescimo_tempo_min.iloc[0]:.1f} min; destino: {dest}".replace(".", ","), fontsize=7.5)
    from matplotlib.lines import Line2D
    leg = [Line2D([0], [0], color=OI["verm"], lw=3.5, label="trecho fechado (≤ 40 m do risco)"),
           Line2D([0], [0], color="#222222", lw=1.6, ls="--", label="caminho original"),
           Line2D([0], [0], color=OI["verde"], lw=2.2, label="desvio sugerido"),
           Line2D([0], [0], color=OI["laranja"], lw=6, alpha=0.3, label="área de risco"),
           Line2D([0], [0], color="black", marker="*", ls="", ms=8, label="destino")]
    fig.legend(handles=leg, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.text(0.5, -0.07, "Desvios pré-calculados para planejamento (rede OSM, sem sentido único, fluxo livre). Não é alerta em tempo real nem resultado do GAMA.", ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    salva(fig, "F_mapa_desvios.png")
