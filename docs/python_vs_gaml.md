# Python × GAML — equivalência e diferenças

A **fonte da verdade é o modelo GAMA** (`models/ibirama.gaml`). O simulador em Python
(`python/simulador.py`) reproduz as **mesmas regras**, mas é **mesoscópico** (o agente leva um tempo
para atravessar cada trecho, calculado na entrada dele), enquanto o GAMA move o agente **passo a passo**
no mapa. Por isso os números não são idênticos — compare **distribuições**, não uma execução.

Os parâmetros do Python usam os **mesmos nomes** do GAML e trazem, no topo de `simulador.py`, um bloco
"PARAMETROS ESPELHADOS DO GAML" com o nome e a linha de cada um, para ressincronizar fácil quando o
`.gaml` mudar (ex.: duração da chuva).

## 1. Regras / parâmetros (estado após o alinhamento)

| Regra / parâmetro | GAML (linha) | Python | Igual? |
|---|---|---|---|
| Duração/perfil do alagamento (subida 1/3, platô 1/6, recessão) | 57, 77-78, 474-484 | `FRAC_RAMPA/FRAC_PLATO`, `np.interp` em `Eventos` | ✅ |
| Deslizamento: duração e **reabertura** | 58, 461-463, 492 | janela `[t0, t0+dur)` em `Eventos` | ✅ |
| `rede_energizada` (60–90 min, uniforme) | 59-61, 461-463 | `Params.rede_energizada` + sorteio | ✅ |
| Erosão: duração, colapso (P_COLAPSO), reabertura | 62, 79, 468-469, 493 | janela + `P_COLAPSO_EROSAO` | ✅ |
| Início do evento + `rnd(1200)` por família | 51, 447-467 | `inicio*60 + uniform(0,1200)` | ✅ (regra) |
| Ativação por grau×severidade (BASE_ATIV, SEV) | 72-73, 446 | `BASE_ATIVACAO`, `SEVERIDADE` | ✅ |
| Profundidade de pico por grau (PROF_PICO) | 74, 454-455 | `PROF_PICO` | ✅ |
| Limites por modal / ousadia / vel. água / erosão | 69-71, 386-398 | `LIMITE_PROF`, `FATOR_ARRISCAR`, `VEL_ARRISCAR`, `FATOR_EROSAO` | ✅ |
| Atualização do estado das vias (5 min) | `cycle mod 30=0` (232) | `GRID=300` s | ✅ |
| Pontos críticos: `pontos_criticos.geojson`, por **grupo** | 24, 27, 141 | lê o geojson, reprojeta 4326→31982, agrupa por `grupo` | ✅ |
| Nó da rede de cada ponto (`no_rede`) | 183 | nó mais próximo entre `nos_veic` | ✅ |
| 6 grupos de acesso + **NaN** no abrigo | 68, 268-272 | `GRUPOS_ACESSO`, NaN se grupo vazio | ✅ |
| Medição do acesso: `inicio+25 min`, 150 nós, carro+pedestre | 265-293 | idem, em `Simulacao.acessibilidade` | ✅ |
| Origem/destino ponderados (PESO_VIA) | 88, 170-196 | `PESO_VIA`, `p_origem` | ✅ (regra) |
| Velocidades por tipo / lentidão por densidade | 86, 89, 678-680 | `VEL_KMH`, `LENT_MIN`, expoente por modal | ✅ |
| Perfis/espera/desfechos/aviso/visão/janela | 80-84, 52, 55, 50 | iguais | ✅ |
| Duração da chuva (HIPÓTESE) + perfil do alagamento com chuva longa | 65, 483-503 | `Params.duracao_chuva_min`, `np.interp` em `Eventos` | ✅ |
| Início do deslizamento sorteado na chuva | 468 | `rng.uniform(0, chuva)` em `Eventos` | ✅ |
| Momento da medição de acesso (`medicao_acesso_min`) | 68, 271 | `Params.medicao_acesso_min` | ✅ |
| CSV de saída: 54 colunas, mesma ordem | 307-345 | `CABECALHO` (teste T10 confere) | ✅ |

## 2. Diferenças **intencionais** (não dá para igualar)

1. **Tipo de movimento.** Python mesoscópico (um salto por trecho); GAMA passo a passo. Afeta
   principalmente quem **desiste/fica preso** no meio do caminho: no GAMA alguns agentes esgotam a
   paciência andando; no Python quase todos completam. (Diferença observada ~2 pontos.)
2. **Passo de tempo.** O estado das vias muda a cada 5 min nos dois; o movimento no GAMA é contínuo no
   passo de 10 s, no Python é por trecho.
3. **Geração de números aleatórios.** Engines diferentes (GAML vs NumPy). Mesmo com as mesmas regras e
   semente, os sorteios (quais polígonos ativam, quando, pico) **não coincidem** — por isso comparamos
   médias/desvios, não execuções.
4. **Construção do grafo (verificado — NÃO é fonte de divergência).** A hipótese antiga (o Python funde
   trechos paralelos e arredonda coordenadas, amplificando as diferenças de acesso) foi **testada por
   execução e descartada**:
   - Arredondar as coordenadas de 0,1 m até 1 m dá **exatamente o mesmo grafo** (1166 arestas, 1014 nós):
     os extremos das vias do shapefile já são coincidentes nos cruzamentos, então o arredondamento não
     funde nem separa nenhum cruzamento (só a 10 m começa a mudar).
   - Dos 1182 trechos, o Python descarta 13 "paralelos" (mesmo par de nós) e 3 de comprimento zero.
     Num **teste de réplica** (fechamentos, amostra e nó do hospital **exportados do GAMA** e recarregados
     no Python), **manter ou não as paralelas dá o mesmo resultado** — elas ligam pares de nós já ligados.
   - Associação via↔polígono (**buffer de 40 m**) e limiar de profundidade (0,30 m carro) são **idênticos**
     nas duas ferramentas.
5. **Medição de acesso.** Python usa componentes conexos (alcance não-direcionado); GAMA usa
   `path_between` sobre `as_edge_graph`. São **equivalentes** (existir caminho ⟺ mesmo componente). No
   teste de réplica, com os **mesmos fechamentos**, o Python reproduziu o `sem_acesso` do GAMA dentro de
   ~4 pontos numa semente (dentro do desvio por semente). A divergência de acesso que sobra vem da
   **realização aleatória dos fechamentos** (engines de RNG diferentes) e do **tamanho da amostra**
   (10 sementes no GAMA, desvio ~12), **não** do grafo.

## 3. Comparação cruzada (Tarefa 6)

GAMA (experimento Interativo em headless, `finalStep=2881`, população padrão, 10 sementes) × Python
(30 sementes), nos mesmos cenários. Médias (desvio padrão) — `<<` marca diferença de média > 5 pontos.

### alagamento / alta / parcial
| métrica | GAMA | Python | dif |
|---|---|---|---|
| % concluiu carro | 97,8 (1,1) | 100,0 (0,0) | +2,2 |
| % desistiu carro | 2,2 (1,1) | 0,0 (0,0) | −2,2 |
| % concluiu moto | 98,0 (1,3) | 99,8 (0,2) | +1,8 |
| % concluiu pedestre | 100,0 | 100,0 | 0,0 |
| gini_fluxo | 0,79 | 0,83 | +0,04 |
| nº polígonos com evento | 7,9 (1,5) | 8,5 (1,4) | +0,6 |
| sem acesso hospital carro % | 14,9 (4,2) | 16,2 (5,1) | +1,4 |
| sem acesso hospital pedestre % | 4,4 (3,6) | 9,9 (3,7) | +5,5 `<<` |

### deslizamento / alta / parcial
| métrica | GAMA | Python | dif |
|---|---|---|---|
| % concluiu carro | 97,8 (1,0) | 99,9 (0,1) | +2,1 |
| % desistiu carro | 2,2 (1,1) | 0,1 (0,1) | −2,2 |
| % concluiu moto | 97,9 (1,2) | 99,7 (0,4) | +1,8 |
| gini_fluxo | 0,79 | 0,83 | +0,04 |
| nº polígonos com evento | 20,1 (2,3) | 21,7 (2,2) | +1,6 |
| sem acesso hospital carro % | 11,3 (8,6) | 15,0 (8,1) | +3,6 |
| sem acesso hospital pedestre % | 8,1 (8,4) | 14,7 (8,1) | +6,5 `<<` |
| sem acesso educacao pedestre % | 0,7 (1,0) | 5,3 (2,0) | +4,6 |

### combinado / alta / local
| métrica | GAMA | Python | dif |
|---|---|---|---|
| % concluiu carro | 97,8 (1,1) | 99,7 (0,3) | +1,9 |
| % desistiu carro | 2,2 (1,1) | 0,1 (0,2) | −2,1 |
| % concluiu pedestre | 100,0 | 99,7 (0,6) | −0,3 |
| gini_fluxo | 0,79 | 0,83 | +0,04 |
| nº polígonos com evento | 28,7 (2,7) | 29,6 (3,1) | +0,9 |
| sem acesso hospital carro % | 24,7 (10,2) | 34,8 (6,4) | +10,1 `<<` |
| sem acesso hospital pedestre % | 14,3 (7,9) | 30,0 (7,5) | +15,6 `<<` |
| sem acesso ubs carro % | 20,6 (10,0) | 29,6 (5,7) | +9,0 `<<` |
| sem acesso ubs pedestre % | 11,6 (6,3) | 24,2 (6,6) | +12,6 `<<` |

### Leitura dos resultados
- **Desfechos (concluiu/voltou/desistiu/preso), Gini e nº de polígonos: equivalência boa** (diferenças
  ~2 pontos ou menos). As regras de evento, ativação, duração/reabertura, `rede_energizada` e desfecho
  reproduzem bem. A pequena sobra de **desistência** no GAMA vem do movimento passo a passo (item 2.1).
- **Acessibilidade: diferenças menores do que se pensava.** Repetindo a comparação no modelo atual
  (combinado/alta, chuva 0, 10 sementes no GAMA × 30 no Python): `sem_acesso_hospital_carro`
  **GAMA 30,0 × Python 34,8** (≈ 5 pontos) e **a pé 21,1 × 30,0** (≈ 9 pontos). O número antigo do GAMA
  (24,7) era um **outlier de 10 sementes** (desvio ~12). A causa **não** é o grafo (item 2.4/2.5, testado
  por execução): é a **realização aleatória dos fechamentos** entre os dois RNGs. Além disso, note que com
  **chuva longa** o `sem_acesso` medido em +25 min **cai** (os deslizamentos espalham-se pela chuva e há
  menos trechos fechados nesse instante) — medir no platô (`medicao_acesso_min` maior) seria mais
  representativo. Portanto, **leia o acesso qualitativamente** (o padrão — pior no combinado, pior a pé —
  é o mesmo nas duas ferramentas); os **números do artigo saem do GAMA**.

## 4. Conclusão
O Python **reproduz as regras** do GAML e serve como **verificação cruzada** e para rodar **muitas
repetições rápido**. Os **resultados do artigo vêm do GAMA**. As diferenças conhecidas estão na seção 2;
a acessibilidade a pé/combinado é a mais sensível e deve ser lida como tendência, não valor exato.
