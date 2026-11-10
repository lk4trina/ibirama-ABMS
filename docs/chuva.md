# Dia útil, picos de saída e duração da chuva

> Tudo que é **HIPÓTESE** está marcado assim no código (`models/ibirama.gaml`, `python/simulador.py`), na
> interface do experimento Interativo e aqui. O que **não** vem da Defesa Civil nem das matérias é hipótese.

## 1. O dia simulado
- A simulação cobre o **dia útil, 06:00 → 19:00 (780 min)**. Tempo 0 = 06:00. `horizonte_min = 780`.
- Os `until` dos experimentos em lote (`Lote`, `LoteChuva`, `LoteHorario`) usam `horizonte_min`
  (`until: (time > horizonte_min * 60.0)`), então não ficam mais fora de sincronia com o horizonte.
  **Atenção:** é `>` e não `>=`. Com `>=` o lote para *antes* do reflex que grava a linha do CSV
  (`finalizar`, que dispara em `time >= horizonte`) e **nenhuma linha é gravada**. Isso foi **verificado por
  execução** (e a `versao-final`, com `28800`, tem o mesmo defeito).
- O overlay do mapa mostra o horário (`HH:MM = 06:00 + tempo`) e o gráfico mostra o horário de início do
  evento no rótulo; **o eixo X continua em minutos** (0 até o horizonte, marcas a cada 60).
- **`duracao_erosao_min = 780`** (era 480). Decisão: a erosão é "dura a simulação toda" (HIPÓTESE, a Defesa
  Civil não informou). Com o horizonte novo, manter 480 faria a erosão "reabrir" às 14:00 sem motivo; o
  coerente é igualar ao horizonte. Se o horizonte mudar, esse valor deve mudar junto.

## 2. Demanda em três ondas (HIPÓTESE)
Cada agente continua fazendo **uma viagem no dia**. O que muda é a hora de saída (`t_partida`):

- `usar_picos = true` (padrão): com probabilidade `frac_pico` (**0,6**, HIPÓTESE) a saída cai uniformemente
  em **um** dos três picos — 7–8 h (min 60–120), 11–12 h (300–360) e 17–18 h (660–720) —, com **pesos
  iguais** (HIPÓTESE: a Defesa Civil informou *quais* são os picos, não a proporção). Caso contrário, é
  uniforme em todo o horizonte (06–19 h).
- `usar_picos = false`: janela única (`janela_partida_min`, 180 min), como na versão anterior.
- Sexta e segunda foram citadas como mais intensas; **não são modeladas** (o dia simulado é um só).

Histograma conferido por execução (semente 7, 1940 agentes): [`hist_saidas.svg`](hist_saidas.svg) —
GAMA e Python mostram três picos; fração dentro dos picos 0,704 (GAMA) e 0,682 (Python), esperado 0,692;
por pico (GAMA) 458 / 428 / 480.

**Quem não termina.** Quem sai perto das 19:00 pode não chegar a tempo; aparece em `pct_em_andamento_*`.
Medido no GAMA (combinado, alta, parcial, padrões novos, 10 sementes): carro **0,14 %** (máx. 0,39),
moto **0,07 %** (máx. 0,24), pedestre **1,28 %** (máx. 2,8; pedestres levam ~20 min por viagem).

## 3. Duração da chuva (`duracao_chuva_min`)
**Padrão: 60 min.** Ancorada nas matérias, não em palpite:

- **GCD, 12/09/2026:** Ibirama decretou emergência; ~80 mm em 24 h e >120 mm em ~48 h; ~30 mm em 1 h no pico
  (sexta, 11/09).
- **ND Mais, 11/09/2026:** Rua Tiradentes alagada pela chuva forte da manhã; Defesa Civil: ~33 mm em
  apenas 1 h.

Elas dão **dois valores documentados**: a **fase intensa de ~1 h (60 min)** e o **episódio persistente de
24–48 h**, que no dia de 13 h equivale a **"a chuva não para" (780 min)**.

> **Limite importante.** As matérias **não informam por quanto tempo as ruas ficaram alagadas.** O vínculo
> *chuva → alagamento* (a água sobe em 10 min, fica no pico **enquanto chove** e desce em
> `duracao_alagamento_min` = 30 min depois que a chuva para) continua uma **inferência (HIPÓTESE)**. O "30 min"
> da Defesa Civil descreve a descida após a chuva parar, não a duração do evento.

`LoteChuva`: `duracao_chuva_min ∈ {0, 60, 120, 240, 780}`, `combinado` e `alagamento`, severidade alta, info
parcial, 10 repetições.

| valor | status |
|---|---|
| **60** | ancorado nas matérias (fase intensa) — **padrão** |
| **780** | ancorado nas matérias (episódio de 24–48 h ≈ "não para" no dia) |
| 0 | comportamento antigo (perfil de 30 min) — referência |
| 120, 240 | **sensibilidade (hipótese)** |

A chuva de 24–48 h só é **aproximada** pelo nível 780 (o dia simulado acaba às 19:00).

**O padrão não foi escolhido pelo efeito.** Pelo que se viu antes (versão anterior), com chuva curta os
cenários se diferenciam pouco (~94–98 % concluem); se isso se repetir com 60 min nos resultados novos, será
**reportado como está**, e 780 e os demais níveis ficam como resultado de sensibilidade. Os números novos
só saem quando os lotes forem rodados (**ainda não rodados**).

## 4. Horário do evento (HIPÓTESE) — `LoteHorario`
`inicio_evento_min`, padrão **60** (07:00, começo do pico da manhã; HIPÓTESE). O experimento `LoteHorario`
roda `combinado` e `alagamento` (alta, parcial) com chuva **60 e 780** e início em **30 (06:30), 270 (10:30) e
630 (16:30)**, 10 repetições, para mostrar o efeito de *quando* chove em relação a cada pico. A coluna
`inicio_evento_min` do CSV identifica cada linha.

Limitação: com chuva longa e início tardio (ex.: 630 + 780), parte dos deslizamentos sorteados "dentro da chuva"
caem depois das 19:00 e **não chegam a acontecer** no dia simulado.

## 5. Medição de acessibilidade em dois momentos
- Original (colunas `sem_acesso_*_pct`): `inicio_evento_min + 25 min` (**pontual**), como antes.
- **Nova** (colunas `sem_acesso_*_plato_pct`): `inicio_evento_min + 60 min` (`medicao_acesso_plato_min`),
  no platô da chuva. Mesma amostra de 150 nós da primeira.
- A medição nova usa **componentes conexas** em vez de `path_between`. Motivo (verificado por execução): chamar
  `path_between` uma 2ª vez no meio da simulação **altera a viagem dos agentes** e as colunas antigas deixariam
  de ser idênticas. Existir caminho ⇔ mesmo componente (o grafo é não direcionado; é o mesmo critério do Python).

## 6. Esquema do CSV: 69 colunas
As 54 originais; `usar_picos` e `frac_pico` logo depois de `duracao_chuva_min` (56); **mais 12 colunas
`sem_acesso_{grupo}_{carro|pedestre}_plato_pct` e `inicio_evento_min` no fim (69)**. Esses 13 extras vão além
das 56 pedidas: o platô foi uma decisão da Etapa 3 e `inicio_evento_min` é necessária para distinguir as linhas
do `LoteHorario`. Python e `03_analise.py` seguem o mesmo esquema (teste T10 confere o cabeçalho).

## 7. Limitações
1. Uma viagem por agente no dia (não há ida e volta nem viagens repetidas).
2. Pesos dos picos e fração nos picos são hipotéticos.
3. Chuva de 24–48 h só aproximada pelo nível 780; relação chuva → alagamento é inferência.
4. Sexta/segunda mais intensas não modeladas.
5. O Python é mesoscópico: ver [`python_vs_gaml.md`](python_vs_gaml.md).

---

## Anexo — resultados da **versão anterior** (NÃO valem para a configuração atual)
Eram: horizonte 480 min, janela única de 180 min, evento aos 45 min, rede real, severidade alta, info parcial.
Mantidos só como histórico; serão substituídos quando os lotes novos forem rodados.

| chuva (min) | GAMA concluiu (carro) | Python concluiu | GAMA desistiu | Python desistiu |
|---|---|---|---|---|
| 0   | 97,6 | 99,7 | 2,3 | 0,2 |
| 60  | 94,8 | 94,0 | 4,5 | 3,7 |
| 120 | 89,7 | 85,5 | 8,4 | 9,7 |
| 240 | 87,5 | 82,1 | 10,3 | 12,1 |

O acesso medido em +25 min **caiu** com chuva longa porque os deslizamentos se espalham pela chuva e há menos
trechos fechados naquele instante (efeito do momento da medição, não de menos risco) — motivo da segunda
medição no platô.
