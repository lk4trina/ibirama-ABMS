"""
Simulador em Python do trafego em Ibirama sob eventos adversos (alagamento, deslizamento e erosao).

A FONTE DA VERDADE e o modelo GAMA (models/ibirama.gaml). Este Python reproduz as MESMAS REGRAS,
mas roda mais rapido. A diferenca de projeto e o movimento: aqui o agente leva um tempo para atravessar
cada trecho (mesoscopico), calculado na entrada dele; no GAMA ele anda passo a passo no mapa. Por isso
os numeros nao sao identicos (compare distribuicoes, nao uma execucao). Ver docs/python_vs_gaml.md.

======================================================================================================
PARAMETROS ESPELHADOS DO GAML  (nome :: linha em models/ibirama.gaml)   -- para ressincronizar facil
------------------------------------------------------------------------------------------------------
  tipo_evento ........... 45        severidade ............ 46        info_nivel ............ 47
  n_carro ............... 49        n_moto ................ 50        n_pedestre ............ 51
  fracao_amostra ........ 52        od_ponderada .......... 53
  usar_picos (HIPOTESE) . 58        frac_pico (HIPOTESE) .. 59        janela_partida_min .... 60
  inicio_evento_min (HIP) 62        atraso_aviso_min ...... 63        horizonte_min ......... 66
  buffer_m .............. 67        raio_visao ............ 68
  duracao_alagamento_min  70        duracao_deslizamento_min 71      rede_energizada ....... 72
  duracao_desl_energ_min  73        duracao_desl_energ_max  74       duracao_erosao_min .... 78
  duracao_chuva_min ..... 87        medicao_acesso_min .... 89        medicao_acesso_plato_min 92
  PICOS_MIN / PESO_PICOS  99-100    HORA_BASE_MIN ......... 101       GRUPOS_ACESSO ......... 103
  LIMITE_PROF ........... 104       FATOR_ARRISCAR ........ 105       VEL_ARRISCAR .......... 106
  BASE_ATIV ............. 107       SEV ................... 108       PROF_PICO ............. 109
  FRAC_RAMPA ............ 112       FRAC_PLATO ............ 113       P_COLAPSO ............. 114
  BETA .................. 115       OUSADIA ............... 116       ESPERA_MAX ............ 117
  PERFIL_MODO ........... 118       COBERTURA ............. 119       VEL_MODO .............. 120
  VEL_CLASSE_KMH ........ 121       PESO_VIA .............. 123       LENT_MIN .............. 124
  VEL_PED ............... 125       COMP_VEICULO .......... 126       hora_do_dia ........... 151
  atualizacao do estado das vias: cycle mod 30 = 0 (5 min) -> GRID=300 s (reflex atualizar_eventos, 296)
  medicao de acesso: reflex medir_acesso (336, inicio+25 min, path_between) e medir_acesso_plato (341,
      inicio+60 min, componentes conexas); amostra de 150 nos (a mesma nas duas); action medir_acesso_agora (346)
  sorteio dos eventos (sortear, 564) e perfil do alagamento (profundidade, 596); CSV de saida: reflex finalizar (411)
  t_partida: sorteado na init (usar_picos -> com prob. frac_pico num dos PICOS_MIN; senao uniforme no horizonte)
======================================================================================================

Os valores marcados HIPOTESE ainda nao foram calibrados.
"""
from __future__ import annotations

import heapq
import itertools
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from shapely import STRtree

RAIZ = Path(__file__).resolve().parent.parent
CRS_METROS = "EPSG:31982"
MODOS = ["carro", "moto", "pedestre"]
PERFIS = ["cauteloso", "normal", "arrojado"]
GRUPOS_ACESSO = ["hospital", "bombeiros", "defesa_civil", "educacao", "ubs", "abrigo"]  # GAML
GRID = 300.0  # s - estado das vias atualizado a cada 5 min (GAML: cycle mod 30 = 0, linha 232)

# ------------------------------------------------------------ PARAMETROS (HIPOTESES, espelham o GAML) ---
VEL_KMH = {"motorway": 80, "trunk": 60, "primary": 50, "secondary": 50, "tertiary": 40, "unclassified": 30,
           "residential": 30, "living_street": 20, "service": 20, "track": 20}   # VEL_CLASSE_KMH, GAML
VEL_PADRAO_KMH = 30
VEL_FATOR_MODO = {"carro": 1.0, "moto": 1.1}      # VEL_MODO, GAML (moto um pouco mais rapida)
VEL_PEDESTRE = 1.3                                  # VEL_PED, GAML (m/s)
LIMITE_PROF = {"carro": 0.30, "moto": 0.20, "pedestre": 0.40}   # GAML (m de lamina d'agua)
FATOR_ARRISCAR = 1.5            # GAML
VEL_ARRISCAR = 0.20            # GAML
BASE_ATIVACAO = {1: 0.25, 2: 0.50, 3: 0.80}         # BASE_ATIV, GAML
SEVERIDADE = {"baixa": 0.4, "media": 0.7, "alta": 1.0}   # SEV, GAML
PROF_PICO = {1: (0.2, 0.4), 2: (0.3, 0.7), 3: (0.5, 1.2)}        # GAML
FRAC_RAMPA = 1.0 / 3.0         # GAML (subida do alagamento)
FRAC_PLATO = 1.0 / 6.0         # GAML (pico do alagamento)
P_COLAPSO_EROSAO = 0.30        # P_COLAPSO, GAML
FATOR_EROSAO = {"carro": 0.5, "moto": 0.5, "pedestre": 0.8}      # GAML
RISCO_GRAU = {0: 0.0, 1: 0.33, 2: 0.66, 3: 1.0}                  # GAML
BETA = {"cauteloso": 2.0, "normal": 1.0, "arrojado": 0.3}        # GAML
OUSADIA = {"cauteloso": 0.0, "normal": 0.15, "arrojado": 0.70}   # GAML
ESPERA_MAX_S = {"cauteloso": 3600, "normal": 2400, "arrojado": 1200}   # ESPERA_MAX, GAML
PERFIL_POR_MODO = {                                              # PERFIL_MODO, GAML
    "carro": (0.30, 0.55, 0.15),
    "moto": (0.15, 0.50, 0.35),
    "pedestre": (0.45, 0.45, 0.10),
}
COBERTURA_AVISO = {"local": 0.0, "parcial": 0.5, "amplo": 0.9}   # COBERTURA, GAML
COMP_VEICULO_M = 8.0           # COMP_VEICULO, GAML
PESO_VIA = {"motorway": 10, "trunk": 10, "primary": 8, "secondary": 6, "tertiary": 4,     # GAML
            "unclassified": 1.5, "residential": 1.5, "living_street": 1.0, "service": 0.5, "track": 0.2}
PESO_VIA_PADRAO = 1.0
LENT_MIN = 0.10                # GAML

# Demanda ao longo do dia (HIPOTESE: a Defesa Civil informou QUAIS sao os picos, nao a proporcao). Espelha o GAML.
# Picos em min apos as 06:00: 7-8 h, 11-12 h, 17-18 h. Sexta e segunda foram citadas como mais intensas (nao modelado).
PICOS_MIN = [(60.0, 120.0), (300.0, 360.0), (660.0, 720.0)]   # GAML PICOS_MIN
PESO_PICOS = [1.0, 1.0, 1.0]                                  # HIPOTESE: pesos iguais (GAML PESO_PICOS)
HORA_BASE_MIN = 360.0                                         # tempo 0 = 06:00 (GAML HORA_BASE_MIN)


def hora_do_dia(t_seg):
    """HH:MM = 06:00 + tempo (GAML hora_do_dia)."""
    m = (int(t_seg / 60.0) + int(HORA_BASE_MIN)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


# Cabecalho de saida: MESMAS 69 colunas, na mesma ordem, que includes/resultados_gama_dc.csv (GAML, reflex finalizar).
# 54 originais + usar_picos e frac_pico (logo apos duracao_chuva_min) + 12 colunas *_plato_pct + inicio_evento_min (no fim).
CABECALHO = ["tipo_evento", "severidade", "info_nivel", "rede_energizada",
             "duracao_alagamento_min", "duracao_deslizamento_min", "duracao_erosao_min",
             "duracao_chuva_min", "usar_picos", "frac_pico", "seed", "n_poligonos_com_evento"]
for _m in MODOS:
    CABECALHO += [f"n_{_m}", f"pct_concluiu_{_m}", f"pct_voltou_{_m}", f"pct_desistiu_{_m}", f"pct_preso_{_m}",
                  f"pct_em_andamento_{_m}", f"tempo_medio_{_m}_min", f"distancia_media_{_m}_m",
                  f"travessias_perigosas_{_m}", f"replanejamentos_{_m}"]
CABECALHO += ["gini_fluxo", "pct_fluxo_top10_vias"]
for _g in GRUPOS_ACESSO:
    CABECALHO += [f"sem_acesso_{_g}_carro_pct", f"sem_acesso_{_g}_pedestre_pct"]
for _g in GRUPOS_ACESSO:    # segunda medicao (plato da chuva)
    CABECALHO += [f"sem_acesso_{_g}_carro_plato_pct", f"sem_acesso_{_g}_pedestre_plato_pct"]
CABECALHO += ["inicio_evento_min"]
assert len(CABECALHO) == 69, len(CABECALHO)


@dataclass
class Params:
    """Mesmos nomes dos parametros do GAML (ver bloco 'PARAMETROS ESPELHADOS' no topo)."""
    tipo_evento: str = "alagamento"     # nenhum | alagamento | deslizamento | erosao | combinado  (GAML)
    severidade: str = "media"           # baixa | media | alta                                       (GAML)
    info_nivel: str = "parcial"         # local | parcial | amplo                                    (GAML)
    n_carro: int = 1270                 # GAML
    n_moto: int = 420                   # GAML
    n_pedestre: int = 250               # GAML (HIPOTESE)
    fracao_amostra: float = 0.10        # GAML
    od_ponderada: bool = True           # GAML
    usar_picos: bool = True             # HIPOTESE: saidas em 3 picos (False = janela unica, versao anterior)
    frac_pico: float = 0.6              # HIPOTESE: fracao das viagens que saem nos picos
    janela_partida_min: float = 180.0   # so vale com usar_picos=False
    inicio_evento_min: float = 60.0     # HIPOTESE: 07:00 (inicio do pico da manha)
    atraso_aviso_min: float = 10.0
    horizonte_min: float = 780.0        # 0 = 06:00, 780 = 19:00
    buffer_m: float = 40.0              # GAML
    # --- eventos (Defesa Civil) ---
    duracao_alagamento_min: float = 30.0    # GAML
    duracao_deslizamento_min: float = 30.0  # GAML
    rede_energizada: bool = False           # GAML (deslizamento leva 60-90 min)
    duracao_desl_energ_min: float = 60.0    # GAML
    duracao_desl_energ_max: float = 90.0    # GAML
    duracao_erosao_min: float = 780.0       # HIPOTESE: = horizonte (a erosao dura o dia todo)
    # Chuva: 60 (fase intensa de ~1 h) e 780 (episodio de 24-48 h = chuva o dia todo) sao ancorados nas materias
    # GCD 12/09/2026 e ND Mais 11/09/2026; 0 (perfil antigo de 30 min), 120 e 240 sao sensibilidade (hipotese).
    # O vinculo chuva -> alagamento e INFERENCIA (as materias nao dizem por quanto tempo as ruas alagaram).
    duracao_chuva_min: float = 60.0
    medicao_acesso_min: float = 25.0        # medicao original (pontual)
    medicao_acesso_plato_min: float = 60.0  # segunda medicao, no plato da chuva (colunas *_plato_pct)
    # --- especifico do Python (nao existe no GAML) ---
    n_destinos: int = 30                # quantos destinos sortear (o GAML usa pontos criticos + 20 extra)


# ------------------------------------------------------------------------------------ MUNDO ---
class Mundo:
    """Rede viaria, poligonos de risco e pontos criticos (agrupados por GRUPO, como no GAML)."""

    def __init__(self, vias_shp, riscos_shp, pontos_arq, buffer_m=40.0, seed_mundo=1):
        vias = gpd.read_file(vias_shp)
        self.riscos = gpd.read_file(riscos_shp).to_crs(vias.crs)

        ids, u, v, comp, hw, geoms = {}, [], [], [], [], []
        escolhido = {}
        carro_col = vias["carro"].astype(int).values if "carro" in vias.columns else np.ones(len(vias), int)
        for g, h, cflag in zip(vias.geometry, vias["highway"], carro_col):
            if g is None or g.is_empty:
                continue
            c = list(g.coords)
            a = (round(c[0][0], 1), round(c[0][1], 1))
            b = (round(c[-1][0], 1), round(c[-1][1], 1))
            if a == b:
                continue
            chave = (min(a, b), max(a, b))
            if chave in escolhido and escolhido[chave][0] <= g.length:
                continue  # descarta o trecho paralelo mais longo
            escolhido[chave] = (g.length, h, g, a, b, int(cflag))
        veic = []
        for (lg, h, g, a, b, cflag) in escolhido.values():
            for p in (a, b):
                ids.setdefault(p, len(ids))
            u.append(ids[a]); v.append(ids[b]); comp.append(lg); hw.append(str(h).split(",")[0].strip("[]' "))
            geoms.append(g)
            veic.append(cflag)
        self.n = len(ids)
        self.xy = np.zeros((self.n, 2))
        for p, i in ids.items():
            self.xy[i] = p
        self.u, self.v = np.array(u), np.array(v)
        self.comp = np.array(comp)
        self.veic_ok = np.array(veic, dtype=bool)      # vias permitidas a carro/moto
        self.E = len(u)
        self.hw = hw
        self.edge_id = {}
        for e, (a, b) in enumerate(zip(self.u, self.v)):
            self.edge_id[(a, b)] = e
            self.edge_id[(b, a)] = e
        vel = np.array([VEL_KMH.get(h, VEL_PADRAO_KMH) for h in hw]) / 3.6
        self.vel_via = vel
        self.tempo = {                                  # tempo livre de cada trecho (s)
            "carro": self.comp / vel,
            "moto": self.comp / (vel * VEL_FATOR_MODO["moto"]),
            "pedestre": self.comp / VEL_PEDESTRE,
        }
        self.peso_via = np.array([PESO_VIA.get(h, PESO_VIA_PADRAO) for h in hw], float)

        uu, vv = self.u[self.veic_ok], self.v[self.veic_ok]
        gv = csr_matrix((np.ones(2 * len(uu)), (np.r_[uu, vv], np.r_[vv, uu])), shape=(self.n, self.n))
        _, lab = connected_components(gv, directed=False)
        grande = np.argmax(np.bincount(lab[np.unique(np.r_[uu, vv])]))
        self.nos_veic = np.where(lab == grande)[0]
        # peso do no = maior peso das vias de carro que chegam nele
        peso_no = np.zeros(self.n)
        np.maximum.at(peso_no, uu, self.peso_via[self.veic_ok])
        np.maximum.at(peso_no, vv, self.peso_via[self.veic_ok])
        self.peso_no = peso_no
        w = peso_no[self.nos_veic]
        self.p_origem = w / w.sum()

        # trechos a ate buffer_m de cada poligono
        arvore = STRtree(geoms)
        self.edges_poli, self.risco_edge = [], np.zeros(self.E)
        for _, r in self.riscos.iterrows():
            idx = arvore.query(r.geometry.buffer(buffer_m), predicate="intersects")
            self.edges_poli.append(np.array(idx, dtype=int))
            self.risco_edge[idx] = np.maximum(self.risco_edge[idx], RISCO_GRAU[int(r.grau_num)])
        self.grau = self.riscos.grau_num.astype(int).values

        # Pontos criticos: le o GEOJSON (28 pontos, WGS84) e agrupa por GRUPO, como o GAML (linha 141).
        # Cada ponto vira o no da rede mais proximo entre os nos_veic (GAML: no_rede = nos_veic closest_to, 183).
        pts = self._ler_pontos(pontos_arq, vias.crs)
        self.criticos_grupo = {}       # grupo -> lista de ids de no
        set_veic = set(int(x) for x in self.nos_veic)
        for _, r in pts.iterrows():
            d = np.hypot(self.xy[:, 0] - r.x, self.xy[:, 1] - r.y)
            d[~np.isin(np.arange(self.n), self.nos_veic)] = np.inf   # so nos_veic sao candidatos
            self.criticos_grupo.setdefault(r.grupo, []).append(int(np.argmin(d)))

        # destinos: pontos criticos, nos perto do centro dos alagamentos e nos aleatorios
        rng = np.random.default_rng(seed_mundo)
        cx, cy = self.riscos[self.riscos.alaga == 1].geometry.centroid.x.mean(), \
            self.riscos[self.riscos.alaga == 1].geometry.centroid.y.mean()
        d_centro = np.hypot(self.xy[:, 0] - cx, self.xy[:, 1] - cy)
        d_centro[~np.isin(np.arange(self.n), self.nos_veic)] = np.inf
        self.centro_nos = np.argsort(d_centro)[:300]
        self.pool_destinos = [n for lst in self.criticos_grupo.values() for n in lst]
        self.rng_destinos = rng

    def _ler_pontos(self, pontos_arq, crs_vias):
        """Le pontos criticos. .geojson (real): campos tipo/grupo/nome/precisao em WGS84.
        .csv (TESTE): campos tipo/nome/lat/lon (sem grupo -> usa o tipo como grupo)."""
        pontos_arq = Path(pontos_arq)
        if pontos_arq.suffix.lower() == ".geojson":
            g = gpd.read_file(pontos_arq)                 # WGS84 (EPSG:4326)
            g = g.to_crs(crs_vias)                        # reprojeta para EPSG:31982 (como o GAML, linha 27)
            out = pd.DataFrame({
                "grupo": g["grupo"].astype(str) if "grupo" in g.columns else g.get("tipo", "x").astype(str),
                "x": g.geometry.x.values, "y": g.geometry.y.values,
            })
        else:
            from pyproj import Transformer
            d = pd.read_csv(pontos_arq)
            px, py = Transformer.from_crs("EPSG:4326", str(crs_vias), always_xy=True).transform(d.lon.values, d.lat.values)
            grupo = d["grupo"].astype(str) if "grupo" in d.columns else d["tipo"].astype(str)
            out = pd.DataFrame({"grupo": grupo.values, "x": px, "y": py})
        return out

    def destinos(self, k, ponderada=True):
        rng = np.random.default_rng(99)
        base = list(self.pool_destinos)
        base += list(rng.choice(self.centro_nos, size=max(0, k // 2), replace=False))
        base += list(rng.choice(self.nos_veic, size=max(0, k - len(base)), replace=False,
                                p=self.p_origem if ponderada else None))
        return sorted(set(int(x) for x in base))


# ---------------------------------------------------------------------------------- EVENTOS ---
class Eventos:
    """Sorteia os poligonos ativados e calcula o estado de cada trecho por modal, com inicio E FIM
    (reabertura) de cada bloqueio, como no GAML (zona_risco.sortear / aplicar, linhas 444-506)."""

    def __init__(self, mundo: Mundo, p: Params, rng):
        self.m, self.p = mundo, p
        self.K = int(p.horizonte_min * 60 / GRID) + 2
        K, E = self.K, mundo.E
        H = np.zeros((K, E), np.float32)            # lamina d'agua
        desl = np.zeros((K, E), bool)               # deslizamento (bloqueio temporario)
        eros_deg = np.zeros((K, E), bool)           # erosao: degradacao
        eros_col = np.zeros((K, E), bool)           # erosao: colapso (bloqueio temporario)
        self.ativos = []
        self.dur_desl = []     # duracoes de deslizamento sorteadas (para testes de rede_energizada)
        self.dur_eros = []
        # ordem das familias igual a do GAML (alaga, desl, eros; ver if's em sortear)
        fam = {"nenhum": [], "alagamento": ["alaga"], "deslizamento": ["desl"],
               "erosao": ["eros"], "combinado": ["alaga", "desl", "eros"]}[p.tipo_evento]
        mult = SEVERIDADE[p.severidade]
        t_ks = np.arange(K) * GRID
        # perfil temporal do alagamento (GAML profundidade, 474-491); rampa = subida (= 10 min quando dur=30)
        dur_al = p.duracao_alagamento_min * 60.0
        rampa = dur_al * FRAC_RAMPA
        for i, r in mundo.riscos.iterrows():
            ed = mundo.edges_poli[i]
            if len(ed) == 0:
                continue
            for f in fam:
                if not r[f]:
                    continue
                if rng.random() >= min(1.0, BASE_ATIVACAO[int(r.grau_num)] * mult):
                    continue
                # deslizamento com chuva longa comeca em qualquer momento dela; alaga/eros (e tudo com chuva=0)
                # nos 1os 20 min -> com chuva=0 a chamada de rnd e identica a de antes (mesmo resultado).
                if f == "desl" and p.duracao_chuva_min > 0.0:
                    t0 = p.inicio_evento_min * 60 + rng.uniform(0, p.duracao_chuva_min * 60.0)
                else:
                    t0 = p.inicio_evento_min * 60 + rng.uniform(0, 1200)
                self.ativos.append((i, f, t0))
                if f == "alaga":
                    lo, hi = PROF_PICO[int(r.grau_num)]
                    pico = rng.uniform(lo, hi)
                    if p.duracao_chuva_min > 0.0:   # chuva longa: pico enquanto chove, desce em duracao_alagamento_min
                        plato = max(0.0, p.duracao_chuva_min * 60.0 - rampa)
                        recesso = dur_al
                    else:                           # perfil atual de 30 min (10 sobe / 5 pico / 15 desce)
                        plato = dur_al * FRAC_PLATO
                        recesso = dur_al - rampa - plato
                    knots = [t0, t0 + rampa, t0 + rampa + plato, t0 + rampa + plato + recesso]
                    d = np.interp(t_ks, knots, [0, pico, pico, 0], left=0, right=0)   # 0 apos o fim -> reabre
                    H[:, ed] = np.maximum(H[:, ed], d[:, None].astype(np.float32))
                elif f == "desl":
                    # 30 min, ou 60-90 min (uniforme) se rede_energizada (GAML); depois reabre
                    dur = ((p.duracao_desl_energ_min
                            + rng.uniform(0, p.duracao_desl_energ_max - p.duracao_desl_energ_min)) * 60.0
                           if p.rede_energizada else p.duracao_deslizamento_min * 60.0)
                    self.dur_desl.append(dur)
                    jan = (t_ks >= t0) & (t_ks < t0 + dur)
                    desl[np.ix_(jan, ed)] = True
                else:  # eros
                    dur = p.duracao_erosao_min * 60.0           # GAML
                    self.dur_eros.append(dur)
                    jan = (t_ks >= t0) & (t_ks < t0 + dur)
                    if rng.random() < P_COLAPSO_EROSAO:         # GAML: colapso <- flip(P_COLAPSO)
                        eros_col[np.ix_(jan, ed)] = True
                    else:
                        eros_deg[np.ix_(jan, ed)] = True
        self.H = H
        # estado por modal: fator de velocidade, bloqueio e se da para atravessar (GAML recalcular, 384-405)
        self.f, self.blk, self.cruza = {}, {}, {}
        for m in MODOS:
            th = LIMITE_PROF[m]
            f = np.where(H <= th, 1 - 0.7 * H / th, 0.0).astype(np.float32)
            blk_flood = H > th
            cruz_flood = blk_flood & (H <= FATOR_ARRISCAR * th)
            ped = m == "pedestre"
            f = np.where(eros_deg, f * FATOR_EROSAO[m], f)
            blk = blk_flood | desl | eros_col
            nao_cruza = (blk_flood & ~cruz_flood)
            if not ped:
                nao_cruza = nao_cruza | desl | eros_col
            self.f[m] = np.where(blk, 0.0, f)
            self.blk[m] = blk
            self.cruza[m] = blk & ~nao_cruza
        self._versionar()

    def _versionar(self):
        """Numera os mapas de bloqueio: a versao muda quando o conjunto de trechos fechados muda
        (agora pode mudar tambem na REABERTURA, nao so no fechamento)."""
        K = self.K
        self.ver_de_k = np.zeros(K, int)
        self.mask_ver = [{m: (self.blk[m][0].copy(), self.cruza[m][0].copy()) for m in MODOS}]
        for k in range(1, K):
            if any(not (np.array_equal(self.blk[m][k], self.mask_ver[-1][m][0]) and
                        np.array_equal(self.cruza[m][k], self.mask_ver[-1][m][1])) for m in MODOS):
                self.mask_ver.append({m: (self.blk[m][k].copy(), self.cruza[m][k].copy()) for m in MODOS})
            self.ver_de_k[k] = len(self.mask_ver) - 1

    def forcar_bloqueio(self, trechos, t_ini_s, atravessavel=False):
        """Fecha trechos especificos a partir de t_ini_s ate o fim (usado nos testes)."""
        k0 = self.k(t_ini_s)
        trechos = np.array(trechos, dtype=int)
        for m in MODOS:
            self.blk[m][k0:, trechos] = True
            self.f[m][k0:, trechos] = 0.0
            self.cruza[m][k0:, trechos] = atravessavel
        self._versionar()

    def k(self, t):
        return min(int(t // GRID), self.K - 1)


# ---------------------------------------------------------------------------------- SIMULACAO ---
class Agente:
    __slots__ = ("id", "modo", "perfil", "cruza", "origem", "destino", "dest_ini", "t_part", "u_aviso",
                 "kv", "vigilante", "no", "t_espera", "voltando", "resultado", "t_fim", "dist", "arriscou",
                 "replan", "aresta", "grupo")


def gerar_populacao(mundo: Mundo, p: Params, seed: int, destinos):
    """A populacao depende so da semente, para poder comparar com a linha de base."""
    rng = np.random.default_rng(seed)
    ags = []
    cont = itertools.count()
    centro = mundo.xy
    for modo, n in (("carro", p.n_carro), ("moto", p.n_moto), ("pedestre", p.n_pedestre)):
        for _ in range(n):
            a = Agente()
            a.id = next(cont)
            a.modo = modo
            a.perfil = PERFIS[rng.choice(3, p=PERFIL_POR_MODO[modo])]
            a.cruza = bool(rng.random() < OUSADIA[a.perfil])
            a.destino = int(rng.choice(destinos))
            if modo == "pedestre":   # pedestre: origem a ate 1,5 km do destino
                d = np.hypot(centro[:, 0] - centro[a.destino, 0], centro[:, 1] - centro[a.destino, 1])
                cand = np.where((d < 1500) & (d > 100))[0]
                a.origem = int(rng.choice(cand)) if len(cand) else int(rng.integers(mundo.n))
            else:
                pp = mundo.p_origem if p.od_ponderada else None
                a.origem = int(rng.choice(mundo.nos_veic, p=pp))
                while a.origem == a.destino:
                    a.origem = int(rng.choice(mundo.nos_veic, p=pp))
            a.dest_ini = a.destino
            if p.usar_picos:   # HIPOTESE: com prob. frac_pico cai num dos 3 picos; senao uniforme no horizonte
                if rng.random() < p.frac_pico:
                    lo, hi = PICOS_MIN[int(rng.choice(len(PICOS_MIN), p=np.array(PESO_PICOS) / sum(PESO_PICOS)))]
                    a.t_part = float(rng.uniform(lo, hi) * 60)
                else:
                    a.t_part = float(rng.uniform(0, p.horizonte_min * 60))
            else:              # janela unica (versao anterior): mesma chamada de antes
                a.t_part = float(rng.uniform(0, p.janela_partida_min * 60))
            a.u_aviso = float(rng.random())
            a.kv, a.vigilante, a.no = 0, False, a.origem
            a.t_espera, a.voltando, a.resultado, a.t_fim = 0.0, False, None, None
            a.dist, a.arriscou, a.replan, a.aresta = 0.0, 0, 0, -1
            a.grupo = 0 if modo != "pedestre" else 1
            ags.append(a)
    return ags


class Simulacao:
    def __init__(self, mundo: Mundo, p: Params, seed: int):
        self.m, self.p, self.seed = mundo, p, seed
        self.ev = Eventos(mundo, p, np.random.default_rng(seed + 10_000))
        self.destinos = mundo.destinos(p.n_destinos, p.od_ponderada)
        self.ags = gerar_populacao(mundo, p, seed, self.destinos)
        self.cov = COBERTURA_AVISO[p.info_nivel]
        self.t_aviso = (p.inicio_evento_min + p.atraso_aviso_min) * 60
        self._csr, self._arv = {}, {}
        self.ocup = np.zeros(mundo.E)
        self.passagens = np.zeros(mundo.E)
        self.capac = np.maximum(1.0, mundo.comp / COMP_VEICULO_M * p.fracao_amostra)
        self.cong_n = 0
        self.cong_r50 = 0
        self.cong_fator = 0.0
        self.r_max = 0.0
        self.log = None

    # --- planejamento de rota (caminhos minimos a partir do destino) ---
    def _grafo(self, ver, modo, perfil, cruza):
        chave = (ver, modo, perfil, cruza)
        if chave in self._csr:
            return self._csr[chave]
        m = self.m
        blk, cr = self.ev.mask_ver[ver][modo]
        w = m.tempo[modo] * (1 + BETA[perfil] * m.risco_edge)
        if cruza:
            w = np.where(blk & cr, m.tempo[modo] / VEL_ARRISCAR, w)
            ok = ~blk | cr
        else:
            ok = ~blk
        if modo != "pedestre":
            ok = ok & m.veic_ok
        u, v, w = m.u[ok], m.v[ok], w[ok]
        g = csr_matrix((np.r_[w, w], (np.r_[u, v], np.r_[v, u])), shape=(m.n, m.n))
        self._csr[chave] = g
        return g

    def _prox(self, a: Agente):
        chave = (a.kv, a.modo, a.perfil, a.cruza, a.destino)
        if chave not in self._arv:
            g = self._grafo(a.kv, a.modo, a.perfil, a.cruza)
            self._arv[chave] = dijkstra(g, indices=a.destino, return_predecessors=True)
        dist, pred = self._arv[chave]
        if not np.isfinite(dist[a.no]):
            return None
        return int(pred[a.no])

    # --- laco principal ---
    def rodar(self):
        m, p, ev = self.m, self.p, self.ev
        fila, cont = [], itertools.count()
        for a in self.ags:
            heapq.heappush(fila, (a.t_part, next(cont), "decide", a))
        t_fim = p.horizonte_min * 60
        while fila:
            t, _, tipo, a = heapq.heappop(fila)
            if t > t_fim:
                break
            if tipo == "chega":
                if a.aresta >= 0 and a.grupo == 0:
                    self.ocup[a.aresta] -= 1
                a.aresta = -1
            if a.no == a.destino:
                a.resultado = "voltou" if a.voltando else "concluiu"
                a.t_fim = t
                continue
            k = ev.k(t)
            vig_atual = ev.ver_de_k[k]
            if t >= self.t_aviso and a.u_aviso < self.cov:
                a.kv = vig_atual
            if a.vigilante:
                a.kv = vig_atual
            prox = self._prox(a)
            if prox is not None:
                e = m.edge_id[(a.no, prox)]
                if ev.blk[a.modo][k][e] and not (a.cruza and ev.cruza[a.modo][k][e]):
                    if a.kv != vig_atual or not a.vigilante:
                        a.kv, a.vigilante = vig_atual, True
                        a.replan += 1
                        prox = self._prox(a)
                        if prox is not None:
                            e = m.edge_id[(a.no, prox)]
                            if ev.blk[a.modo][k][e] and not (a.cruza and ev.cruza[a.modo][k][e]):
                                prox = None
                    else:
                        prox = None
            if prox is None:                      # sem rota: espera / volta / fica preso
                a.vigilante, a.kv = True, vig_atual
                a.t_espera += 300
                if a.t_espera > ESPERA_MAX_S[a.perfil]:
                    if not a.voltando and a.no != a.origem:
                        a.voltando, a.destino, a.t_espera = True, a.origem, 0.0
                    else:
                        a.resultado, a.t_fim = ("desistiu" if a.dist == 0 else "preso"), t
                        continue
                heapq.heappush(fila, (t + 300, next(cont), "decide", a))
                continue
            # atravessa o trecho
            bloqueado = ev.blk[a.modo][k][e]
            if bloqueado:
                fator = VEL_ARRISCAR
                a.arriscou += 1
            else:
                fator = float(ev.f[a.modo][k][e])
            if a.modo == "pedestre":
                v = VEL_PEDESTRE * fator
            else:
                v = m.vel_via[e] * (VEL_FATOR_MODO[a.modo]) * fator
                r = self.ocup[e] / self.capac[e]
                expoente = 0.5 if a.modo == "moto" else 1.0
                lent = max(LENT_MIN, 1 / (1 + expoente * 0.15 * r ** 4))
                v = v * lent
                self.cong_n += 1
                self.cong_r50 += r >= 0.5
                self.cong_fator += lent
                self.r_max = max(self.r_max, r)
                self.ocup[e] += 1
                self.passagens[e] += 1
                a.aresta = e
            if self.log is not None:
                self.log.append((t, e, a.id, bool(bloqueado)))
            a.dist += m.comp[e]
            a.no = prox
            heapq.heappush(fila, (t + m.comp[e] / max(v, 0.05), next(cont), "chega", a))
        for a in self.ags:
            if a.resultado is None:
                a.resultado = "em_viagem"
        return self

    # --- acessibilidade: duas medicoes (inicio+medicao_acesso_min e inicio+medicao_acesso_plato_min), amostra
    # de 150 nos (a MESMA nas duas), carro+pedestre (GAML medir_acesso_agora) ---
    def acessibilidade(self):
        m, ev, p = self.m, self.ev, self.p
        rng = np.random.default_rng(self.seed + 20_000)
        if len(m.nos_veic) <= 150:
            amostra = np.asarray(m.nos_veic)
        else:
            amostra = rng.choice(m.nos_veic, size=150, replace=False)
        out = {}
        for sufixo, minutos in (("_pct", p.medicao_acesso_min), ("_plato_pct", p.medicao_acesso_plato_min)):
            k = ev.k((p.inicio_evento_min + minutos) * 60.0)
            for grupo in GRUPOS_ACESSO:
                nos = m.criticos_grupo.get(grupo, [])
                for modo in ("carro", "pedestre"):
                    col = f"sem_acesso_{grupo}_{modo}{sufixo}"
                    if not nos:                    # grupo sem pontos -> NaN
                        out[col] = np.nan
                        continue
                    ok = ~ev.blk[modo][k]
                    if modo != "pedestre":
                        ok = ok & m.veic_ok
                    uu, vv = m.u[ok], m.v[ok]
                    adj = csr_matrix((np.ones(2 * len(uu)), (np.r_[uu, vv], np.r_[vv, uu])), shape=(m.n, m.n))
                    _, lab = connected_components(adj, directed=False)
                    rotulos = set(lab[np.array(nos, dtype=int)])
                    sem = int(sum(1 for nd in amostra if lab[nd] not in rotulos))
                    out[col] = round(100.0 * sem / len(amostra), 2)
        return out

    # --- metricas: linha com as MESMAS 69 colunas do CSV do GAMA, na mesma ordem ---
    def metricas(self, ref=None):
        ags, p = self.ags, self.p
        n_poli = len({i for (i, f, t0) in self.ev.ativos})
        row = {
            "tipo_evento": p.tipo_evento, "severidade": p.severidade, "info_nivel": p.info_nivel,
            "rede_energizada": "true" if p.rede_energizada else "false",   # GAML grava string(rede_energizada)
            "duracao_alagamento_min": p.duracao_alagamento_min,
            "duracao_deslizamento_min": p.duracao_deslizamento_min,
            "duracao_erosao_min": p.duracao_erosao_min, "duracao_chuva_min": p.duracao_chuva_min,
            "usar_picos": "true" if p.usar_picos else "false",   # GAML grava string(usar_picos)
            "frac_pico": p.frac_pico, "inicio_evento_min": p.inicio_evento_min,
            "seed": self.seed, "n_poligonos_com_evento": n_poli,
        }
        tempos = {}
        for modo in MODOS:
            s = [a for a in ags if a.modo == modo]
            c = [a for a in s if a.resultado == "concluiu"]
            ns = len(s)
            row[f"n_{modo}"] = ns
            row[f"pct_concluiu_{modo}"] = round(100 * len(c) / ns, 2) if ns else 0.0
            row[f"pct_voltou_{modo}"] = round(100 * sum(a.resultado == "voltou" for a in s) / ns, 2) if ns else 0.0
            row[f"pct_desistiu_{modo}"] = round(100 * sum(a.resultado == "desistiu" for a in s) / ns, 2) if ns else 0.0
            row[f"pct_preso_{modo}"] = round(100 * sum(a.resultado == "preso" for a in s) / ns, 2) if ns else 0.0
            row[f"pct_em_andamento_{modo}"] = round(100 * sum(a.resultado == "em_viagem" for a in s) / ns, 2) if ns else 0.0
            row[f"tempo_medio_{modo}_min"] = round(float(np.mean([(a.t_fim - a.t_part) / 60 for a in c])), 3) if c else 0.0
            row[f"distancia_media_{modo}_m"] = round(float(np.mean([a.dist for a in c])), 1) if c else 0.0
            row[f"travessias_perigosas_{modo}"] = int(sum(a.arriscou for a in s))
            row[f"replanejamentos_{modo}"] = int(sum(a.replan for a in s))
            for a in c:
                tempos[a.id] = ((a.t_fim - a.t_part) / 60, a.dist)
        # concentracao do fluxo (Gini e % das 10 vias mais usadas) - GAML
        pas = np.sort(self.passagens)
        tot = pas.sum()
        if tot > 0:
            nn = len(pas)
            gini = (2 * np.sum(np.arange(1, nn + 1) * pas) / (nn * tot)) - (nn + 1) / nn
            row["gini_fluxo"] = round(float(gini), 4)
            row["pct_fluxo_top10_vias"] = round(float(100 * pas[-10:].sum() / tot), 2)
        else:
            row["gini_fluxo"] = 0.0
            row["pct_fluxo_top10_vias"] = 0.0
        row.update(self.acessibilidade())
        row = {k: row[k] for k in CABECALHO}   # garante ordem e nomes exatos das 69 colunas
        return row, tempos


_MUNDO_CACHE = {}


def carregar_mundo(rede="teste", buffer_m=40.0):
    if rede in _MUNDO_CACHE:
        return _MUNDO_CACHE[rede]
    d = RAIZ / "includes" / "dados"
    if rede == "teste":
        print(">> ATENCAO: usando a rede *_TESTE/_SINTETICO (ficticia). Resultados NAO valem para o artigo.")
        vias = d / "vias_teste_SINTETICO.shp"
        pontos = d / "pontos_criticos_TESTE.csv"
    else:
        vias = d / "vias.shp"
        pontos = d / "pontos_criticos.geojson"     # 28 pontos reais (o simulador usa o geojson, nao o CSV antigo)
    _MUNDO_CACHE[rede] = Mundo(vias, d / "riscos.shp", pontos, buffer_m)
    return _MUNDO_CACHE[rede]


def rodar_um(p: Params, seed: int, rede="teste", ref=None):
    s = Simulacao(carregar_mundo(rede, p.buffer_m), p, seed).rodar()
    return s.metricas(ref)


if __name__ == "__main__":
    import argparse
    import time
    ap = argparse.ArgumentParser(description="Roda uma simulacao e mostra o resumo (69 colunas do GAMA)")
    ap.add_argument("--evento", default="alagamento")
    ap.add_argument("--severidade", default="media")
    ap.add_argument("--info", default="parcial")
    ap.add_argument("--rede_energizada", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--sem_picos", action="store_true", help="janela unica de saida (versao anterior)")
    ap.add_argument("--chuva", type=float, default=60.0, help="duracao_chuva_min")
    ap.add_argument("--inicio", type=float, default=60.0, help="inicio_evento_min")
    ap.add_argument("--rede", default="teste", choices=["teste", "real"])
    a = ap.parse_args()
    t0 = time.time()
    row, _ = rodar_um(Params(tipo_evento=a.evento, severidade=a.severidade, info_nivel=a.info,
                             rede_energizada=a.rede_energizada, usar_picos=not a.sem_picos,
                             duracao_chuva_min=a.chuva, inicio_evento_min=a.inicio), a.seed, a.rede)
    for k in CABECALHO:
        print(f"{k:34s} {row[k]}")
    print(f"\n({time.time()-t0:.1f} s)")
