"""
Consolida as linhas de cada execucao do GAMA (runs/<experimento>/<cenario>_<semente>.csv, fora do repositorio)
e VALIDA cada experimento:

  - 69 campos por linha, na ordem do cabecalho de includes/resultados_gama_dc.csv
  - sem duplicatas (mesmo cenario + mesma semente)
  - numero de linhas e conjunto de cenarios x sementes exatamente como o esperado
  - sem NaN/vazio inesperado (o grupo abrigo existe; duracao_chuva_min e inicio_evento_min corretos)

    python scripts/10_consolidar.py                      # valida e grava os consolidados em <raiz>/consolidados/
    python scripts/10_consolidar.py --final              # idem + grava includes/resultados_gama_dc.csv (so no fim!)

Os 4 experimentos (sementes 1 a 10; D usa 1 a 5):
  A_principal 550 | B_chuva 100 | C_horario 120 | D_persistente 275   (total 1045)
A, B e D tem celulas em comum (mesmo cenario e semente) - ver --final: a linha repetida e comparada byte a byte
(reprodutibilidade) e entra uma vez so no CSV final (1015 linhas unicas).
"""
import argparse
import itertools
import sys
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
sys.path.insert(0, str(REPO / "python"))
from simulador import CABECALHO  # noqa: E402  (as 69 colunas, na ordem do GAMA)

ap = argparse.ArgumentParser()
ap.add_argument("--raiz", default="/mnt/c/Temp/ibirama_final")
ap.add_argument("--final", action="store_true", help="grava includes/resultados_gama_dc.csv (so quando os 4 estiverem completos)")
a = ap.parse_args()
RAIZ = Path(a.raiz)

SEV, INF = ["baixa", "media", "alta"], ["local", "parcial", "amplo"]
CHAVE = ["tipo_evento", "severidade", "info_nivel", "rede_energizada", "duracao_chuva_min", "inicio_evento_min"]


def cenarios_a(chuva):
    L = [("nenhum", "baixa", "local", "false", chuva, 60.0)]
    for e in ("alagamento", "erosao"):
        L += [(e, s, i, "false", chuva, 60.0) for s, i in itertools.product(SEV, INF)]
    for e in ("deslizamento", "combinado"):
        L += [(e, s, i, r, chuva, 60.0) for s, i, r in itertools.product(SEV, INF, ("false", "true"))]
    return L


def esperado(exp):
    if exp == "A_principal":
        return cenarios_a(60.0), range(1, 11)
    if exp == "B_chuva":
        return [(e, "alta", "parcial", "false", c, 60.0) for e in ("combinado", "alagamento") for c in (0.0, 60.0, 120.0, 240.0, 780.0)], range(1, 11)
    if exp == "C_horario":
        return [(e, "alta", "parcial", "false", c, i) for e in ("combinado", "alagamento") for i in (30.0, 270.0, 630.0) for c in (60.0, 780.0)], range(1, 11)
    if exp == "D_persistente":
        return cenarios_a(780.0), range(1, 6)
    raise ValueError(exp)


EXPS = ["A_principal", "B_chuva", "C_horario", "D_persistente"]
TOTAL = {"A_principal": 550, "B_chuva": 100, "C_horario": 120, "D_persistente": 275}


def ler(exp):
    """Le os arquivos de uma execucao. Retorna (df, problemas, linhas_brutas)."""
    pasta = RAIZ / "runs" / exp
    prob, brutas = [], {}
    regs = []
    for f in sorted(pasta.glob("*.csv")):
        linhas = [l for l in f.read_text(encoding="utf8").splitlines() if l.strip()]
        if len(linhas) != 1:
            prob.append(f"{f.name}: {len(linhas)} linhas (esperava 1)")
            continue
        campos = linhas[0].split(",")
        if len(campos) != 69:
            prob.append(f"{f.name}: {len(campos)} campos (esperava 69)")
            continue
        brutas[f.name] = linhas[0]
        regs.append(campos)
    df = pd.DataFrame(regs, columns=CABECALHO)
    txt = {"tipo_evento", "severidade", "info_nivel", "rede_energizada", "usar_picos"}
    for c in CABECALHO:
        if c not in txt:
            df[c] = pd.to_numeric(df[c], errors="coerce")  # "NaN" vira NaN
    df["_arquivo"] = list(brutas.keys())
    return df, prob, brutas


def validar(exp):
    df, prob, brutas = ler(exp)
    cen, sem = esperado(exp)
    n_esp = TOTAL[exp]
    rel = [f"== {exp}: {len(df)} linhas lidas (esperado {n_esp}) =="]
    rel += [f"PROBLEMA arquivo: {p}" for p in prob]
    ok = not prob
    rel.append(f"colunas: {len(CABECALHO)} (cabecalho do repo) | campos por linha conferidos: {'ok' if not prob else 'ver acima'}")
    # duplicatas
    chave = CHAVE + ["seed"]
    dup = df[df.duplicated(chave, keep=False)]
    rel.append(f"duplicatas (cenario+semente): {len(dup)}")
    ok &= len(dup) == 0
    # linhas esperadas x obtidas
    esp = {c + (float(s),) for c in cen for s in sem}
    df["_k"] = [(r.tipo_evento, r.severidade, r.info_nivel, str(r.rede_energizada).lower(), float(r.duracao_chuva_min),
                 float(r.inicio_evento_min), float(r.seed)) for r in df.itertuples()]
    obt = set(df["_k"])
    falta, extra = esp - obt, obt - esp
    rel.append(f"cenario x semente: esperados {len(esp)}, obtidos {len(obt)}, faltando {len(falta)}, a mais {len(extra)}")
    for k in sorted(falta)[:10]:
        rel.append(f"   falta: {k}")
    for k in sorted(extra)[:10]:
        rel.append(f"   a mais: {k}")
    ok &= (not falta and not extra and len(df) == n_esp)
    # NaN inesperado
    nan_cols = {c: int(df[c].isna().sum()) for c in CABECALHO if df[c].isna().any()}
    rel.append(f"colunas com NaN: {nan_cols if nan_cols else 'nenhuma'}")
    ok &= not nan_cols
    # grupo abrigo presente (nao NaN)
    ab = [c for c in CABECALHO if "abrigo" in c]
    rel.append(f"colunas do abrigo ({len(ab)}) sem NaN: {all(df[c].notna().all() for c in ab) if len(df) else 'n/a'}")
    # chuva / inicio
    rel.append(f"duracao_chuva_min encontrados: {sorted(df.duracao_chuva_min.unique().tolist())}")
    rel.append(f"inicio_evento_min encontrados: {sorted(df.inicio_evento_min.unique().tolist())}")
    rel.append(f"sementes encontradas: {sorted(df.seed.unique().tolist())}")
    rel.append(f"usar_picos: {sorted(df.usar_picos.unique().tolist())} | frac_pico: {sorted(df.frac_pico.unique().tolist())}")
    # valores impossiveis
    pcols = [c for c in CABECALHO if c.startswith("pct_") or c.startswith("sem_acesso_")]
    fora = int(((df[pcols] < -1e-9) | (df[pcols] > 100 + 1e-9)).sum().sum())
    rel.append(f"percentuais fora de [0,100]: {fora}")
    ok &= fora == 0
    for m in ("carro", "moto", "pedestre"):
        s = df[[f"pct_{k}_{m}" for k in ("concluiu", "voltou", "desistiu", "preso", "em_andamento")]].sum(axis=1)
        bad = int(((s - 100).abs() > 1e-6).sum())
        rel.append(f"soma dos desfechos != 100 ({m}): {bad} linhas")
        ok &= bad == 0
    rel.append(f"RESULTADO {exp}: {'VALIDO' if ok else 'COM PROBLEMAS'}")
    return df, brutas, rel, ok


def main():
    saida = RAIZ / "consolidados"
    saida.mkdir(exist_ok=True)
    todos, ok_geral, relatorio = {}, True, []
    for exp in EXPS:
        if not (RAIZ / "runs" / exp).exists():
            relatorio.append(f"== {exp}: pasta inexistente ==")
            ok_geral = False
            continue
        df, brutas, rel, ok = validar(exp)
        relatorio += rel + [""]
        ok_geral &= ok
        todos[exp] = (df, brutas)
        # consolidado do experimento: cabecalho + linhas brutas (texto do GAMA, sem reformatar), ordenadas pelo nome
        with open(saida / f"{exp}.csv", "w", encoding="utf8", newline="\n") as f:
            f.write(",".join(CABECALHO) + "\n")
            for nome in sorted(brutas):
                f.write(brutas[nome] + "\n")
    # reprodutibilidade: celulas repetidas entre experimentos (mesmo cenario e semente) devem ser identicas
    rep = {}
    for exp, (df, brutas) in todos.items():
        for nome, linha in brutas.items():
            k = tuple(linha.split(",")[i] for i in (0, 1, 2, 3, 7, 68, 10))
            k = (k[0], k[1], k[2], k[3], float(k[4]), float(k[5]), float(k[6]))
            rep.setdefault(k, []).append((exp, linha))
    repetidas = {k: v for k, v in rep.items() if len({e for e, _ in v}) > 1}
    difer = [k for k, v in repetidas.items() if len({l for _, l in v}) > 1]
    relatorio.append(f"== Reprodutibilidade: {len(repetidas)} celulas (cenario+semente) aparecem em mais de um experimento; "
                     f"{len(repetidas) - len(difer)} identicas byte a byte, {len(difer)} diferentes ==")
    for k in difer[:10]:
        relatorio.append(f"   DIFERENTE: {k}")
    unicas = {}
    for k, v in rep.items():
        unicas[k] = v[0][1]
    relatorio.append(f"linhas unicas no conjunto final: {len(unicas)} (soma dos experimentos: {sum(len(v[1]) for v in todos.values())})")
    txt = "\n".join(relatorio)
    (saida / "validacao.txt").write_text(txt + "\n", encoding="utf8")
    print(txt)
    if a.final:
        if not ok_geral or len(todos) != 4:
            print("\nNAO gravei includes/resultados_gama_dc.csv: algum experimento esta incompleto/invalido.")
            sys.exit(2)
        destino = REPO / "includes" / "resultados_gama_dc.csv"
        with open(destino, "w", encoding="utf8", newline="\n") as f:
            f.write(",".join(CABECALHO) + "\n")
            for k in sorted(unicas, key=lambda t: (t[6], t)):
                f.write(unicas[k] + "\n")
        print(f"\nGravado {destino} com {len(unicas)} linhas + cabecalho.")


main()
