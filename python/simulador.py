"""
SIMULADOR (versão Python) - Tráfego e dispersão em Ibirama sob eventos adversos
===============================================================================

Para que serve
  * Plano B / verificador do modelo GAMA: aplica as MESMAS regras (mesmos agentes, eventos,
    parâmetros e métricas) e roda em segundos, sem instalar nada além do Python.
  * Diferença técnica: aqui o movimento é "mesoscópico" (o agente leva um tempo para atravessar
    cada trecho, calculado na entrada do trecho). No GAMA o agente se move passo a passo no mapa.
    As regras de decisão são as mesmas; os números absolutos de tempo podem diferir um pouco.

Como o modelo funciona (resumo)
  1. Cada agente (carro, moto ou pedestre) tem origem, destino, horário de partida e um PERFIL de
     risco (cauteloso / normal / arrojado) que define: quanto evita áreas de risco ao escolher a
     rota, quanto tempo espera quando fica sem rota e se aceita atravessar um trecho perigoso.
  2. Os polígonos do mapa de risco viram EVENTOS: cada polígono do tipo escolhido é ativado com
     probabilidade que depende do grau (Médio/Alto/Muito Alto) e da severidade do cenário. As ruas
     a até 40 m do polígono são afetadas:
        alagamento : lâmina d'água sobe, fica e desce; acima de um limite por modal o trecho fecha
        deslizamento: trecho bloqueado até o fim da simulação
        erosão      : trecho degradado (mais lento) ou, com probabilidade, interrompido
  3. Agentes NÃO sabem do bloqueio de antemão. Eles descobrem (a) vendo o trecho bloqueado à frente
     ou (b) recebendo o aviso da Defesa Civil (fração do cenário "info"). Quem descobre refaz a rota.
  4. Sem rota possível: espera; esgotada a paciência, volta para a origem. Quem nunca saiu de casa
     "desiste" da viagem; quem parou no meio do caminho e não consegue nem voltar fica "preso".

*** TODOS os valores marcados como HIPÓTESE abaixo são pontos de partida, NÃO medidos. ***
*** Devem ser calibrados com a Defesa Civil e a pesquisa com moradores.               ***
"""
from __future__ import annotations

import heapq
import itertools
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from shapely import STRtree

RAIZ = Path(__file__).resolve().parent.parent
MODOS = ["carro", "moto", "pedestre"]
PERFIS = ["cauteloso", "normal", "arrojado"]
GRID = 300.0  # s: o estado do mundo é recalculado a cada 5 min

# ------------------------------------------------------------------ PARÂMETROS (HIPÓTESES) ---
VEL_KMH = {"primary": 50, "secondary": 50, "tertiary": 40, "residential": 30, "service": 20, "track": 20}
VEL_PADRAO_KMH = 30
VEL_FATOR_MODO = {"carro": 1.0, "moto": 1.1}      # moto um pouco mais rápida no fluxo livre (HIPÓTESE)
VEL_PEDESTRE = 1.3                                  # m/s
LIMITE_PROF = {"carro": 0.30, "moto": 0.20, "pedestre": 0.40}   # m de lâmina d'água (HIPÓTESE)
FATOR_ARRISCAR = 1.5            # passa por trecho "fechado" se prof <= 1,5 x limite (só quem arrisca)
VEL_ARRISCAR = 0.20             # fração da velocidade ao atravessar trecho perigoso
BASE_ATIVACAO = {1: 0.25, 2: 0.50, 3: 0.80}         # prob. de ativação por grau (HIPÓTESE)
SEVERIDADE = {"baixa": 0.4, "media": 0.7, "alta": 1.0}
PROF_PICO = {1: (0.2, 0.4), 2: (0.3, 0.7), 3: (0.5, 1.2)}        # m, sorteio por grau (HIPÓTESE)
RAMPA_S, PLATO_S, RECESSO_S = 3600, 3600, 7200
P_COLAPSO_EROSAO = 0.30
FATOR_EROSAO = {"carro": 0.5, "moto": 0.5, "pedestre": 0.8}
RISCO_GRAU = {0: 0.0, 1: 0.33, 2: 0.66, 3: 1.0}
BETA = {"cauteloso": 2.0, "normal": 1.0, "arrojado": 0.3}        # peso do risco na escolha da rota
OUSADIA = {"cauteloso": 0.0, "normal": 0.15, "arrojado": 0.70}   # prob. de aceitar atravessar
ESPERA_MAX_S = {"cauteloso": 3600, "normal": 2400, "arrojado": 1200}
PERFIL_POR_MODO = {                                              # (caut, normal, arrojado) HIPÓTESE
    "carro": (0.30, 0.55, 0.15),
    "moto": (0.15, 0.50, 0.35),
    "pedestre": (0.45, 0.45, 0.10),
}
COBERTURA_AVISO = {"local": 0.0, "parcial": 0.5, "amplo": 0.9}
COMP_VEICULO_M = 8.0            # espaço por veículo na via (capacidade = comprimento / 8)


@dataclass
class Params:
    evento: str = "alagamento"      # nenhum | alagamento | deslizamento | erosao | combinado
    severidade: str = "media"       # baixa | media | alta
    info: str = "parcial"           # local | parcial | amplo
    n_carro: int = 800
    n_moto: int = 450
    n_pedestre: int = 250
    janela_partida_min: float = 180.0
    inicio_evento_min: float = 45.0
    atraso_aviso_min: float = 10.0
    horizonte_min: float = 480.0
    buffer_m: float = 40.0
    n_destinos: int = 30


# ------------------------------------------------------------------------------------ MUNDO ---
class Mundo:
    """Rede viária + polígonos de risco + pontos críticos (carregados uma vez só)."""

    def __init__(self, vias_shp, riscos_shp, pontos_csv, buffer_m=40.0, seed_mundo=1):
        vias = gpd.read_file(vias_shp)
        self.riscos = gpd.read_file(riscos_shp).to_crs(vias.crs)
        pts = pd.read_csv(pontos_csv)

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
                continue  # trecho paralelo mais longo: descarta
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
        self.tempo = {                                  # tempo de percurso livre de cada trecho (s)
            "carro": self.comp / vel,
            "moto": self.comp / (vel * VEL_FATOR_MODO["moto"]),
            "pedestre": self.comp / VEL_PEDESTRE,
        }
        self.capac = np.maximum(1.0, self.comp / COMP_VEICULO_M)

        from scipy.sparse.csgraph import connected_components
        uu, vv = self.u[self.veic_ok], self.v[self.veic_ok]
        gv = csr_matrix((np.ones(2 * len(uu)), (np.r_[uu, vv], np.r_[vv, uu])), shape=(self.n, self.n))
        _, lab = connected_components(gv, directed=False)
        grande = np.argmax(np.bincount(lab[np.unique(np.r_[uu, vv])]))
        self.nos_veic = np.where(lab == grande)[0]

        # polígono -> trechos a até buffer_m
        arvore = STRtree(geoms)
        self.edges_poli, self.risco_edge = [], np.zeros(self.E)
        for _, r in self.riscos.iterrows():
            idx = arvore.query(r.geometry.buffer(buffer_m), predicate="intersects")
            self.edges_poli.append(np.array(idx, dtype=int))
            self.risco_edge[idx] = np.maximum(self.risco_edge[idx], RISCO_GRAU[int(r.grau_num)])
        self.grau = self.riscos.grau_num.astype(int).values

        # pontos críticos -> nó mais próximo
        self.criticos = {}
        from pyproj import Transformer
        px, py = Transformer.from_crs("EPSG:4326", str(vias.crs), always_xy=True).transform(pts.lon.values, pts.lat.values)
        pts["x"], pts["y"] = px, py
        for _, r in pts.iterrows():
            d = np.hypot(self.xy[:, 0] - r.x, self.xy[:, 1] - r.y)
            d[~np.isin(np.arange(self.n), self.nos_veic)] = np.inf
            self.criticos.setdefault(r.tipo, []).append(int(np.argmin(d)))

        # destinos: pontos críticos + centralidades (mais próximas do centro dos alagamentos) + aleatórios
        rng = np.random.default_rng(seed_mundo)
        cx, cy = self.riscos[self.riscos.alaga == 1].geometry.centroid.x.mean(), \
            self.riscos[self.riscos.alaga == 1].geometry.centroid.y.mean()
        d_centro = np.hypot(self.xy[:, 0] - cx, self.xy[:, 1] - cy)
        d_centro[~np.isin(np.arange(self.n), self.nos_veic)] = np.inf
        self.centro_nos = np.argsort(d_centro)[:300]
        self.pool_destinos = [n for lst in self.criticos.values() for n in lst]
        self.rng_destinos = rng

    def destinos(self, k):
        rng = np.random.default_rng(99)
        base = list(self.pool_destinos)
        base += list(rng.choice(self.centro_nos, size=max(0, k // 2), replace=False))
        base += list(rng.choice(self.nos_veic, size=max(0, k - len(base)), replace=False))
        return sorted(set(int(x) for x in base))


# ---------------------------------------------------------------------------------- EVENTOS ---
class Eventos:
    """Sorteia quais polígonos ativam e calcula, a cada 5 min, o estado de cada trecho por modal."""

    def __init__(self, mundo: Mundo, p: Params, rng):
        self.m, self.p = mundo, p
        self.K = int(p.horizonte_min * 60 / GRID) + 2
        K, E = self.K, mundo.E
        H = np.zeros((K, E), np.float32)            # lâmina d'água
        desl = np.zeros((K, E), bool)               # deslizamento (bloqueio)
        eros_deg = np.zeros((K, E), bool)           # erosão: degradação
        eros_col = np.zeros((K, E), bool)           # erosão: colapso (bloqueio)
        self.ativos = []
        fam = {"nenhum": [], "alagamento": ["alaga"], "deslizamento": ["desl"],
               "erosao": ["eros"], "combinado": ["alaga", "eros", "desl"]}[p.evento]
        mult = SEVERIDADE[p.severidade]
        t_ks = np.arange(K) * GRID
        for i, r in mundo.riscos.iterrows():
            ed = mundo.edges_poli[i]
            if len(ed) == 0:
                continue
            for f in fam:
                if not r[f]:
                    continue
                if rng.random() >= min(1.0, BASE_ATIVACAO[int(r.grau_num)] * mult):
                    continue
                t0 = p.inicio_evento_min * 60 + rng.uniform(0, 1200)
                self.ativos.append((i, f, t0))
                if f == "alaga":
                    lo, hi = PROF_PICO[int(r.grau_num)]
                    pico = rng.uniform(lo, hi)
                    d = np.interp(t_ks, [t0, t0 + RAMPA_S, t0 + RAMPA_S + PLATO_S, t0 + RAMPA_S + PLATO_S + RECESSO_S],
                                  [0, pico, pico, 0], left=0, right=0)
                    H[:, ed] = np.maximum(H[:, ed], d[:, None].astype(np.float32))
                elif f == "desl":
                    desl[np.ix_(t_ks >= t0, ed)] = True
                else:
                    if rng.random() < P_COLAPSO_EROSAO:
                        eros_col[np.ix_(t_ks >= t0, ed)] = True
                    else:
                        eros_deg[np.ix_(t_ks >= t0, ed)] = True
        self.H = H
        # estado por modal: fator de velocidade, bloqueado?, atravessável por quem arrisca?
        self.f, self.blk, self.cruza = {}, {}, {}
        for m in MODOS:
            th = LIMITE_PROF[m]
            f = np.where(H <= th, 1 - 0.7 * H / th, 0.0).astype(np.float32)
            blk_flood = H > th
            cruz_flood = blk_flood & (H <= FATOR_ARRISCAR * th)
            ped = m == "pedestre"
            f = np.where(eros_deg, f * FATOR_EROSAO[m], f)
            blk = blk_flood | desl | eros_col
            # só enchente rasa (e, a pé, deslizamento/colapso) pode ser atravessada por quem arrisca
            nao_cruza = (blk_flood & ~cruz_flood)
            if not ped:
                nao_cruza = nao_cruza | desl | eros_col
            self.f[m] = np.where(blk, 0.0, f)
            self.blk[m] = blk
            self.cruza[m] = blk & ~nao_cruza
        self._versionar()

    def _versionar(self):
        """Versões do "mapa de bloqueios": só mudam quando o conjunto de trechos fechados muda."""
        K = self.K
        self.ver_de_k = np.zeros(K, int)
        self.mask_ver = [{m: (self.blk[m][0].copy(), self.cruza[m][0].copy()) for m in MODOS}]
        for k in range(1, K):
            if any(not (np.array_equal(self.blk[m][k], self.mask_ver[-1][m][0]) and
                        np.array_equal(self.cruza[m][k], self.mask_ver[-1][m][1])) for m in MODOS):
                self.mask_ver.append({m: (self.blk[m][k].copy(), self.cruza[m][k].copy()) for m in MODOS})
            self.ver_de_k[k] = len(self.mask_ver) - 1

    def forcar_bloqueio(self, trechos, t_ini_s, atravessavel=False):
        """Fecha trechos específicos (ex.: ruas que a Defesa Civil confirma que fecham) a partir de t_ini_s."""
        k0 = self.k(t_ini_s)
        trechos = np.array(trechos, dtype=int)
        for m in MODOS:
            self.blk[m][k0:, trechos] = True
            self.f[m][k0:, trechos] = 0.0
            self.cruza[m][k0:, trechos] = atravessavel
        self._versionar()

    def k(self, t):
        return min(int(t // GRID), self.K - 1)


# ---------------------------------------------------------------------------------- SIMULAÇÃO ---
class Agente:
    __slots__ = ("id", "modo", "perfil", "cruza", "origem", "destino", "dest_ini", "t_part", "u_aviso",
                 "kv", "vigilante", "no", "t_espera", "voltando", "resultado", "t_fim", "dist", "arriscou",
                 "replan", "aresta", "grupo")


def gerar_populacao(mundo: Mundo, p: Params, seed: int, destinos):
    """A população depende só da SEMENTE (não do evento) -> permite comparar cenário x linha de base."""
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
            if modo == "pedestre":   # pedestre faz viagens curtas: origem a até 1,5 km do destino
                d = np.hypot(centro[:, 0] - centro[a.destino, 0], centro[:, 1] - centro[a.destino, 1])
                cand = np.where((d < 1500) & (d > 100))[0]
                a.origem = int(rng.choice(cand)) if len(cand) else int(rng.integers(mundo.n))
            else:
                a.origem = int(rng.choice(mundo.nos_veic))
                while a.origem == a.destino:
                    a.origem = int(rng.choice(mundo.nos_veic))
            a.dest_ini = a.destino
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
        self.destinos = mundo.destinos(p.n_destinos)
        self.ags = gerar_populacao(mundo, p, seed, self.destinos)
        self.cov = COBERTURA_AVISO[p.info]
        self.t_aviso = (p.inicio_evento_min + p.atraso_aviso_min) * 60
        self._csr, self._arv = {}, {}
        self.ocup = np.zeros(mundo.E)
        self.passagens = np.zeros(mundo.E)
        self.log = None            # se for uma lista, registra (t, trecho, agente, atravessou_fechado)

    # --- planejamento de rota: árvore de caminhos mínimos a partir do destino -----------------
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
        """Próximo nó no caminho do agente segundo o MAPA QUE ELE CONHECE (versão a.kv)."""
        chave = (a.kv, a.modo, a.perfil, a.cruza, a.destino)
        if chave not in self._arv:
            g = self._grafo(a.kv, a.modo, a.perfil, a.cruza)
            self._arv[chave] = dijkstra(g, indices=a.destino, return_predecessors=True)
        dist, pred = self._arv[chave]
        if not np.isfinite(dist[a.no]):
            return None
        return int(pred[a.no])

    # --- laço principal (por eventos) --------------------------------------------------------
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
            # aviso oficial: quem é alcançado atualiza o mapa
            if t >= self.t_aviso and a.u_aviso < self.cov:
                a.kv = vig_atual
            if a.vigilante:
                a.kv = vig_atual
            prox = self._prox(a)
            if prox is not None:
                e = m.edge_id[(a.no, prox)]
                if ev.blk[a.modo][k][e] and not (a.cruza and ev.cruza[a.modo][k][e]):
                    # vê o trecho fechado: aprende, refaz a rota com o mapa atual
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
                    else:   # nunca saiu de casa -> desistiu (seguro); parou no meio do caminho -> preso
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
                r = self.ocup[e] / m.capac[e]
                expoente = 0.5 if a.modo == "moto" else 1.0      # moto sofre menos com fila (HIPÓTESE)
                v = v / (1 + expoente * 0.15 * r ** 4)
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

    # --- acessibilidade a pontos críticos no pico do evento ----------------------------------
    def acessibilidade(self):
        m, ev = self.m, self.ev
        k = ev.k((self.p.inicio_evento_min + 90) * 60)
        out = {}
        for modo in ("carro", "pedestre"):
            ok = ~ev.blk[modo][k]
            if modo != "pedestre":
                ok = ok & m.veic_ok
            g = csr_matrix((np.r_[m.tempo[modo][ok], m.tempo[modo][ok]], (np.r_[m.u[ok], m.v[ok]], np.r_[m.v[ok], m.u[ok]])),
                           shape=(m.n, m.n))
            for tipo, nos in m.criticos.items():
                d = dijkstra(g, indices=nos, min_only=True)
                fin = np.isfinite(d)
                out[f"acc_{tipo}_{modo}_sem_acesso_pct"] = round(100 * (1 - fin.mean()), 2)
                out[f"acc_{tipo}_{modo}_tempo_medio_min"] = round(float(d[fin].mean() / 60), 2) if fin.any() else np.nan
        return out

    # --- métricas ----------------------------------------------------------------------------
    def metricas(self, ref=None):
        ags = self.ags
        row = dict(asdict(self.p), seed=self.seed, polig_ativos=len(self.ev.ativos),
                   trechos_fechados_pico_carro=int(self.ev.blk["carro"][self.ev.k((self.p.inicio_evento_min + 90) * 60)].sum()))
        tempos = {}
        for modo in MODOS:
            s = [a for a in ags if a.modo == modo]
            c = [a for a in s if a.resultado == "concluiu"]
            row[f"{modo}_n"] = len(s)
            row[f"{modo}_concluiu_pct"] = round(100 * len(c) / len(s), 2) if s else np.nan
            row[f"{modo}_voltou_pct"] = round(100 * sum(a.resultado == "voltou" for a in s) / len(s), 2) if s else np.nan
            row[f"{modo}_desistiu_pct"] = round(100 * sum(a.resultado == "desistiu" for a in s) / len(s), 2) if s else np.nan
            row[f"{modo}_preso_pct"] = round(100 * sum(a.resultado == "preso" for a in s) / len(s), 2) if s else np.nan
            row[f"{modo}_emviagem_pct"] = round(100 * sum(a.resultado == "em_viagem" for a in s) / len(s), 2) if s else np.nan
            row[f"{modo}_tempo_medio_min"] = round(float(np.mean([(a.t_fim - a.t_part) / 60 for a in c])), 3) if c else np.nan
            row[f"{modo}_dist_media_m"] = round(float(np.mean([a.dist for a in c])), 1) if c else np.nan
            row[f"{modo}_travessias_arriscadas"] = int(sum(a.arriscou for a in s))
            row[f"{modo}_replanejamentos"] = int(sum(a.replan for a in s))
            for a in c:
                tempos[a.id] = (a.t_fim - a.t_part) / 60, a.dist
            if ref is not None and c:
                dif = [((a.t_fim - a.t_part) / 60 - ref[a.id][0]) for a in c if a.id in ref]
                dd = [(a.dist - ref[a.id][1]) for a in c if a.id in ref]
                row[f"{modo}_atraso_pareado_min"] = round(float(np.mean(dif)), 3) if dif else np.nan
                row[f"{modo}_dist_extra_m"] = round(float(np.mean(dd)), 1) if dd else np.nan
        pas = np.sort(self.passagens)
        tot = pas.sum()
        if tot > 0:
            n = len(pas)
            gini = (2 * np.sum((np.arange(1, n + 1)) * pas) / (n * tot)) - (n + 1) / n
            row["fluxo_gini"] = round(float(gini), 4)
            row["fluxo_top10_pct"] = round(float(100 * pas[-10:].sum() / tot), 2)
        row.update(self.acessibilidade())
        return row, tempos


_MUNDO_CACHE = {}


def carregar_mundo(rede="teste", buffer_m=40.0):
    if rede in _MUNDO_CACHE:
        return _MUNDO_CACHE[rede]
    d = RAIZ / "dados"
    vias = d / ("vias_teste_SINTETICO.shp" if rede == "teste" else "vias.shp")
    pts = d / ("pontos_criticos_TESTE.csv" if rede == "teste" else "pontos_criticos.csv")
    _MUNDO_CACHE[rede] = Mundo(vias, d / "riscos.shp", pts, buffer_m)
    return _MUNDO_CACHE[rede]


def rodar_um(p: Params, seed: int, rede="teste", ref=None):
    s = Simulacao(carregar_mundo(rede, p.buffer_m), p, seed).rodar()
    return s.metricas(ref)


if __name__ == "__main__":
    import argparse
    import time
    ap = argparse.ArgumentParser(description="Roda UMA simulação e mostra o resumo")
    ap.add_argument("--evento", default="alagamento")
    ap.add_argument("--severidade", default="media")
    ap.add_argument("--info", default="parcial")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rede", default="teste", choices=["teste", "real"])
    a = ap.parse_args()
    t0 = time.time()
    base, tb = rodar_um(Params(evento="nenhum", info=a.info), a.seed, a.rede)
    row, _ = rodar_um(Params(evento=a.evento, severidade=a.severidade, info=a.info), a.seed, a.rede, ref=tb)
    for k, v in row.items():
        print(f"{k:38s} {v}")
    print(f"\n({time.time()-t0:.1f} s)")
