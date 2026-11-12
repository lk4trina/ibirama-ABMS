# Resultados para o artigo (5OPMSA) - texto-base

Simulação baseada em agentes do tráfego de Ibirama sob alagamento, deslizamento e erosão. Cliente: Defesa Civil.
Todos os números vêm do **GAMA 2025.06.4 (rede real)**, 1.015 execuções únicas (1.045 rodadas; 30 repetidas entre
experimentos e idênticas byte a byte). Arquivo: `includes/resultados_gama_dc.csv`. Tabelas em `docs/tabelas/`,
figuras em `docs/figuras/`. O Python serve só de verificação cruzada.

## 0. O que foi verificado e como

**(a) Verificado por execução**
- 1.045 execuções no GAMA headless, um processo por simulação, semente explícita, 5 em paralelo, 0 falhas, 0 repetições
  (`falhas.log` não foi criado). Sementes 1 a 10 em A, B e C; 1 a 5 em D.
- Cada experimento passou na validação: 69 colunas, sem duplicatas, nº de linhas esperado, sem NaN, grupo abrigo
  presente, `duracao_chuva_min` e `inicio_evento_min` corretos, desfechos somando 100 % (`docs/tabelas/validacao_consolidacao.txt`).
- Reprodutibilidade: as 30 células que aparecem em mais de um experimento saíram idênticas byte a byte.
- Os 4 destinos de grupo único (hospital, bombeiros, Defesa Civil, abrigo) têm "sem acesso" igual em 100 % das 1.015 linhas.
- Lote de 550 no lugar de 900: 8 execuções extras de fatores "redundantes" saíram idênticas às de base (`docs/lote_principal_equivalencia.md`).
- Um modelo com gravação por agente (cópia só em `C:\Temp`, regras iguais) gerou linhas **idênticas** nas 69 colunas às do lote;
  dele vem a Figura E (1 execução por cenário).
- Verificação cruzada Python x GAMA: `LoteChuva`, rede real, 30 repetições no Python (`tabelas/verificacao_cruzada_gama_python.csv`).
- `python/testes_logica.py` passou ("TODOS OS TESTES PASSARAM"); `scripts/03_analise.py` rodou de verdade no CSV final.

**(b) Por leitura (não rodado para esse fim)**
- O `until: (time > horizonte_min * 60.0)` está nos três experimentos em lote (linhas 992, 1004 e 1015). Os resultados
  não usaram o `batch` do GAMA: cada simulação rodou o experimento `Interativo` com `finalStep=4682` (a linha só é gravada
  quando `time >= 46800`, o ciclo 4680), e a linha de cada execução foi conferida.
- A explicação de por que os 4 destinos de grupo único dão o mesmo "sem acesso" (seção 5, anomalia 2).

**(c) Não verificado**
- Que a chuva de 60 ou 780 min cause os alagamentos modelados (inferência, ver limitações).
- A causa dos 2 a 3 % de "sem acesso" no cenário sem evento (anomalia 3).
- Por que mais informação não aumenta a conclusão (seção 2, T2): só há hipótese.
- Qualquer resultado para outras sementes, para a frota completa ou para outro dia.

## 1. Parâmetros que são HIPÓTESE (sem fonte)

Picos de saída com **pesos iguais** (os três horários 7-8, 11-12 e 17-18 h vêm da Defesa Civil; a proporção não);
**`frac_pico` = 0,6**; **início do evento** em 07:00 (60 min) no padrão e 06:30, 10:30 e 16:30 no `LoteHorario`;
**250 pedestres**; **duração da erosão** (780 min); probabilidade de colapso da erosão (0,3); níveis de cobertura da
informação (0 / 0,5 / 0,9) e atraso do aviso (10 min); paciência de espera por perfil; limites de lâmina d'água; probabilidade
de ativação por grau; profundidades de pico. Chuvas de 0, 120 e 240 min são sensibilidade. **Têm fonte**: chuva de 60 min
e de 780 min (matérias GCD 12/09/2026 e ND Mais 11/09/2026), frota (Senatran, dez/2025), duração do alagamento e do
deslizamento (Defesa Civil), vias e áreas de risco.

## 2. Tabelas

Convenção: média ± desvio padrão **entre sementes**. Quando uma linha junta níveis de informação e rede energizada,
primeiro tira-se a média por semente. Chuva 60 usa 10 sementes. Chuva 780 usa as sementes 1 a 5 (n=5).
Testes: Kruskal-Wallis e Mann-Whitney (não paramétricos) com correção de Holm dentro de cada família de testes (definida em `scripts/11_tabelas.py`); efeito A12 (0,5 = sem efeito;
0,56/0,64/0,71 = pequeno/médio/grande) e epsilon² para Kruskal-Wallis. Shapiro-Wilk em 866 células testáveis: 27 % rejeitam
normalidade; 286 células são constantes. Com n=10 o teste tem pouco poder, as variáveis são limitadas a [0,100] e
muitas têm zeros, então se usou o teste não paramétrico em todas. As tabelas completas estão em `docs/tabelas/` (CSV e LaTeX)
e em `docs/tabelas/tabelas_texto.md`. Em total, 1.104 testes foram calculados (`testes_estatisticos.csv`).

### T1. Desfechos por modal, evento e severidade (`T1_desfechos.csv`, `T1_chuva*_*.tex`)
Com chuva de 60 min, os cenários ficam **parecidos**: o carro conclui 97,6 % sem evento, 95,8 % no alagamento alto e
94,8 % no combinado alto (sd entre sementes 1,5 a 1,9). O contraste mais forte, combinado alto contra sem evento,
tem p Holm = 0,027 (A12 = 0,15, "grande"), mas é uma diferença de **2,8 pontos percentuais**. Para o carro, só 1 dos 12
cenários com evento se distingue do cenário sem evento depois da correção (a família de Holm são as 3 severidades de um mesmo evento);
para a moto, 3 de 12; para o pedestre, a conclusão não muda em nenhum, mas a desistência muda em 5 de 12.
Com chuva de 780 min o quadro muda: alagamento e combinado de severidade média e alta ficam entre **78,6 e 85,0 %** de
conclusão no carro (p Holm = 0,024, o menor valor possível com n=5). Deslizamento continua igual ao cenário sem evento (97,7 %).
**Erosão é indistinguível do cenário sem evento** em todas as severidades e chuvas (p = 1,0; 97,6 %), ver anomalia 1.
O "atraso" (tempo médio de quem concluiu, menos o do cenário sem evento na mesma semente) é de **0,1 a 0,8 min** no carro,
chuva 60: quem chega, chega quase no mesmo tempo. O efeito está em quem **não** chega.
Não mostra: a causa de cada desistência, nem o que acontece com quem não sai de casa.

### T2. Nível de informação (`T2_informacao.csv`, `T2_*.tex`)
Mais informação **não aumentou** a fração que conclui. Na média dos 12 cenários com evento, o carro conclui 96,9 % (local),
96,7 % (parcial) e 96,5 % (amplo); Kruskal-Wallis p = 0,53 (carro), 0,50 (moto), 0,93 (pedestre); em nenhum dos 12 estratos
o p Holm fica abaixo de 0,05. A informação **muda o comportamento**: replanejamentos por 100 agentes (carro) caem de 5,0
(local) para 2,6 (parcial) e 0,6 (amplo), A12 = 1,0 nas três comparações (p Holm = 0,0005).
No teste de sensibilidade pareado por semente (Wilcoxon), o carro conclui um pouco **menos** com mais informação, nas 10
sementes (p Holm = 0,006), uma diferença de cerca de 0,4 ponto. A explicação possível é que quem sabe do fechamento desde o
início passa a evitar ou desistir mais cedo, mas isso **não foi testado**. Com a informação de 0 / 0,5 / 0,9 hipotética,
o resultado vale para esse desenho e não diz que a informação é inútil na prática.

### T3. Duração da chuva (`T3_duracao_chuva.csv`, `T3.tex`)
Combinado, alta, informação parcial: o carro conclui 97,6 % (0 min), 95,5 % (60), 94,1 % (120), 93,0 % (240) e **79,8 % (780)**.
Kruskal-Wallis p < 0,001 (epsilon² = 0,78). A queda de 0 a 240 min é gradual (1 a 2 pontos por degrau);
a de 240 para 780 min é de 13 pontos. De 60 para 120 min a diferença **não** passa na correção (p Holm = 0,18 no combinado,
0,057 no alagamento). O alagamento sozinho e o combinado ficam quase iguais em todas as durações (79,2 e 79,8 % em 780 min):
com chuva longa, o alagamento domina. A chuva de 780 min é uma aproximação do episódio de 24 a 48 h e a relação chuva → alagamento é inferência.
Não mostra: durações entre 240 e 780 min.

### T4. Acessibilidade (`T4_acessibilidade.csv`, `T4_*.tex`)
Medida como % dos 150 nós amostrados que não alcançam o destino. No combinado alto (chuva 60) o hospital fica sem acesso para
**24,8 %** (carro) e **16,7 %** (a pé) em +25 min, e 30,6 % e 24,3 % no platô (+60 min). O alagamento alto dá 16,0 % (carro);
o deslizamento alto, 7,9 % com desvio padrão de 8; a erosão, 2,7 % (igual ao sem evento). A severidade importa no combinado
(13 dos 96 testes de severidade passam na correção, todos no combinado). Com chuva 780, o combinado alto dá **16,9 %** em +25 min,
menos que com chuva 60: os deslizamentos se espalham ao longo de 13 h e, naquele instante, há menos trechos fechados; é efeito
do **momento da medição**, não de menor risco (o platô dá 20,0 %). O platô é maior que +25 min nas 10 sementes no alagamento alto (Wilcoxon, p = 0,002 nos 12 testes); no combinado alto o p vai de 0,002 a 0,049
e no deslizamento alto de 0,002 a 0,56. Nenhum passa na correção de Holm para 36 testes (o menor p Holm possível com n=10 é 0,07). Hospital, bombeiros, Defesa Civil e abrigo dão o mesmo
valor (anomalia 2); educação e UBS têm vários pontos e diferem.

### T5. Gini e fluxo nas 10 vias mais usadas (`T5_concentracao.csv`, `T5.tex`)
O Gini do fluxo fica entre 0,789 e 0,805 e a fatia das 10 vias mais usadas entre 22 e 25 % em todos os cenários. Nenhum cenário
se distingue do sem evento depois da correção (menor p Holm = 0,055, combinado alto, Gini, chuva 60). A diferença visível é pequena:
o Gini cai de 0,796 (sem evento) para 0,789 no combinado alto. Neste modelo, o evento **não concentra nem dispersa**
o fluxo de modo mensurável. Não mostra: se o fluxo se desloca para vias específicas (a métrica é global).

### T6. Horário do evento (`T6_horario.csv`, `T6.tex`)
Com chuva de 60 min, o horário **não importa**: o carro conclui entre 95,5 e 96,3 % em qualquer início (p Holm = 1,0), mesmo
com a chuva sobre o pico da manhã (07:00, 23 % das saídas expostas à chuva). Com chuva de 780 min, importa: início às 16:30
(só 28 % das saídas expostas) dá 92,0 % contra 78,0 a 79,8 % às 06:30 e 07:00 (p Holm = 0,004; A12 = 0). O que pesa é quanto da
demanda sai durante a chuva, não o horário em si. A coluna "saídas na chuva" usa a distribuição de saídas do modelo (hipótese).

## 3. Figuras (PNG, 300 dpi, `docs/figuras/`)

- **A** `A_conclusao_por_evento_severidade.png`: % que conclui por evento e severidade, chuva 60 e 780, três modais. Os eixos verticais
  não começam em zero e cada painel tem escala própria. Mostra que, em 60 min, as barras de erro se sobrepõem em quase todos os pares.
- **B** `B_conclusao_por_duracao_chuva.png`: % que conclui contra a duração da chuva (T3). Símbolos cheios são os valores ancorados nas matérias.
- **C** `C_efeito_da_informacao.png`: efeito da informação por modal (% que conclui e replanejamentos). Mostra linhas planas em cima e queda embaixo.
- **D** `D_efeito_do_horario.png`: horário do evento, com os três picos sombreados. Mostra o efeito só na chuva de 780 min.
- **E** `E_saidas_e_viagens_no_dia.png`: histograma das saídas de 1 execução (semente 1; três picos) e agentes em viagem ao longo do
  dia, sem evento e combinado alto. O pico das 8 h passa de cerca de 34 agentes (sem evento) para cerca de 84 (combinado); a curva inclui agentes parados esperando rota.
  É 1 execução por cenário, vinda do modelo com gravação por agente.
- **F** `F_mapa_desvios.png`: mapa de 4 trechos fechados com o desvio sugerido (Santa Cruz, Duque de Caxias, Marquês do Herval e Ponte
  Ibirama-Apiúna). **Não é resultado do GAMA**: são desvios pré-calculados (`scripts/08_desvios.py`) para planejamento. O arquivo
  `resultados/fig_desvios.png` que já existia não é um mapa (é um gráfico de barras sem acentos e com nomes de rua repetidos), por isso foi refeito.

## 4. Limitações

- A relação chuva → alagamento é **inferência**: as matérias fixam a chuva (60 e 780 min), não por quanto tempo as ruas alagaram.
- Picos (pesos iguais), `frac_pico` e início do evento são hipóteses; o dia é um só (sexta e segunda, mais intensas, não entram).
- **Uma viagem por agente**, sem ida e volta.
- **Amostra de 10 %** da frota (1.270 carros, 420 motos, 250 pedestres); a capacidade das vias é ajustada, mas é uma amostra.
- Frota estimada por Senatran/IBGE; pedestres são hipótese.
- Acessibilidade **medida em um instante** (+25 min e +60 min), sobre 150 nós; a escolha do instante muda o número (T4).
- Rede OSM **sem sentido único e sem semáforo**.
- Poucas sementes: n=10 (chuva 60) e n=5 (chuva 780, exceto os cenários do LoteChuva/LoteHorario, com n=10). Com n=5 o menor p do
  Mann-Whitney é 0,0079. Valores de p só dizem que o resultado não parece acaso nestas sementes; com mais repetições qualquer diferença pequena viraria "significativa".
- O Python é mesoscópico e usa outro gerador de números aleatórios: serve de validação, não de resultado. Na verificação (combinado e alagamento, alta, parcial, 30 repetições
  contra 10 do GAMA) a maior diferença na % que conclui (carro) foi de **3,9 pontos** (combinado, chuva 780: 75,9 contra 79,8) e de 1,7 a 1,9 sem chuva (99,3 e 99,6 contra 97,6);
  a ordem dos efeitos (0 > 60 > 120 > 240 > 780) é a mesma. O Python subestima a desistência sem chuva (0,2 contra 2,3 %).
  No acesso ao hospital as diferenças vão de 0,1 a 5,8 pontos e 13 de 40 comparações têm p < 0,05 (a pé o Python dá 3 a 4 pontos a mais de "sem acesso"; sem chuva ele não reproduz os
  cerca de 3,5 % do GAMA, anomalia 3). Ou seja, a validação é boa para os desfechos e fraca para o acesso.
- Os resultados não são previsão de chuva, de nível de rio nem de eventos reais; comparam cenários.

## 5. Anomalias nos dados (o modelo não foi corrigido)

1. **Erosão ≡ sem evento.** Em 100 % das sementes a % que conclui (carro e moto) e a desistência (carro) da erosão são **idênticas** às do
   cenário sem evento (97,65 %, 2,21 %); o pedestre difere em 2 % das linhas. Só o Gini muda um pouco. A erosão ativa em média 0,8 a 1,9 dos 49
   polígonos (alagamento alto: 8,8; deslizamento alto: 21,9; combinado alto: 29,4). Este modelo não distingue erosão de um dia normal.
2. **Hospital = bombeiros = Defesa Civil = abrigo.** Os quatro dão o mesmo "sem acesso" nas 1.015 linhas, nas quatro medidas, embora os pontos fiquem em nós diferentes. Leitura Causa não investigada. A hipótese de que a medida só detectaria nós isolados não se sustenta:
   verificamos que a rede é uma única componente conexa. A medida não separa esses quatro destinos;
   só educação e UBS (vários pontos) diferem.
3. **Sem evento, já há 1,3 a 3,3 % de carros sem acesso** em +25 min (2,0 a 4,7 % no platô) e 0 % a pé. O Python dá 0,0 % neste cenário (3 sementes).
   Sem evento as duas medidas deveriam ser iguais e zero. Causa não investigada. Isso desloca todos os valores de acesso do carro em cerca de 3 pontos.
4. **Cerca de 2 % dos carros e motos "desistem" mesmo sem evento** (2,2 e 2,1 %), e 1,3 % dos pedestres ainda estão em andamento às 19:00 (saem tarde e levam ~20 min). A linha de base não é 100 %.
5. **Cenários próximos com chuva de 60 min** (pedido do enunciado de reportar): ver T1. Deslizamento (qualquer severidade) e erosão não se distinguem do sem evento no carro; só combinado alto o faz.
6. **`rede_energizada` troca a realização do sorteio.** Em deslizamento e combinado, só 13 % dos pares (rede falso e verdadeiro, mesma semente e cenário) têm o mesmo nº de polígonos ativos,
   então a comparação não é limpa. Nenhum dos 18 testes carro (concluiu, desistiu, acesso ao hospital) dá p < 0,2 (`EXTRA-rede` em `testes_estatisticos.csv`).
7. **Informação não ajuda o desfecho** (T2): resultado contraintuitivo, a investigar antes de usar como recomendação.
8. Os cenários de chuva 780 x deslizamento ficam muito perto do sem evento (97,7 %), enquanto alagamento chega a 78,6 %: o deslizamento aparece nos dados como pouco relevante nesse desenho,
   porque (por leitura de `docs/chuva.md`) ele só é sorteado dentro da janela de chuva e fecha por 30 a 90 min.
9. Efeito de medição: o acesso em +25 min cai quando a chuva é mais longa (T4).