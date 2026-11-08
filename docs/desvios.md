# Desvios (rotas alternativas) para trechos fechados

A Defesa Civil de Ibirama sugeriu que o mapa indicasse uma **rota alternativa** nas áreas de fechamento,
como faz o **Alerta Blu** de Blumenau. Este material pré-calcula esses desvios para **planejamento**.

> **Ressalva (vale para tudo):** isto **não é um alerta em tempo real**. São desvios **pré-calculados**,
> sobre a rede do **OpenStreetMap**, **sem sentido único** e **sem semáforo**, pelo **caminho mais rápido
> em fluxo livre** (sem congestionamento). Os arquivos `*_TESTE`/`*_SINTETICO` são fictícios e não entram.

Gere tudo com: `python scripts/08_desvios.py`

## Método
1. **Rede e roteamento.** Monto o grafo a partir de `includes/dados/vias.shp` (1.182 trechos, EPSG:31982;
   o `id` do trecho é o índice da linha). Uso **Dijkstra sobre grafo esparso**, como em `python/simulador.py`,
   com o **tempo livre** de cada trecho = comprimento ÷ velocidade. Velocidades por tipo de via
   (`VEL_CLASSE_KMH`) e a pé (1,3 m/s), o campo `carro`/`pedest` e o buffer de 40 m vêm do modelo
   (`models/ibirama.gaml` linhas 86, 90, 139, 54; `python/simulador.py` linhas 42-46).
2. **Cenários de fechamento** (A1): cada **rua interditada** (7) e cada **via principal** (5) em duas
   versões — (a) a **rua inteira** (limite superior) e (b) só os **trechos a ≤ 40 m de um polígono de
   risco** (mais realista); cada **polígono de risco** (49) pelos trechos no buffer de 40 m; e a
   **BR-470 / ponte** (trechos `trunk` com ref BR-470), marcada `pendente_geometria` (o vão exato não tem
   geometria — não inventei).
3. **Desvio** (A2): origens-destino de referência = **29 pontos críticos** como destinos e **200 nós de
   origem** sorteados com semente fixa (42), ponderados por `PESO_VIA`. Considero só os **pares realmente
   afetados** (cujo caminho mais rápido sem fechamento passa por um trecho fechado). Para cada par afetado
   recalculo o caminho **com o fechamento**; registro se há alternativa, o **acréscimo de distância (m) e
   de tempo (min)** e os **nomes das ruas do desvio** (de `vias_nomes.csv`, descartando nomes vazios).

## Parâmetros
- semente fixa: **42**; nº de origens: **200**; buffer: **40 m**; velocidades e regras: as do modelo.
- Para não reconstruir caminhos demais, a mediana/p90 de **distância** e as ruas do desvio usam uma
  amostra de até **400** pares afetados por cenário; **% sem alternativa** e o acréscimo de **tempo** usam
  **todos** os pares afetados.

## Saídas
- `includes/dados/desvios_sugeridos.csv` — 1 linha por cenário × modal (carro/pedestre).
- `resultados/desvios_exemplos.geojson` — para 25 cenários, as geometrias do trecho fechado, do caminho
  original e do desvio de exemplo (o de acréscimo mediano), em EPSG:4326.
- `resultados/mapa_desvios.html` — mapa folium: áreas de risco, ruas interditadas (vermelho, com popup do
  desvio de carro), desvio sugerido (verde), caminho original (cinza tracejado), pontos críticos, legenda
  e a ressalva.
- `resultados/fig_desvios.png` — acréscimo mediano de distância (carro) por rua interditada (versão ≤40 m),
  laranja quando há pares sem alternativa.

## Limitações (importante para interpretar)
- **Rede do OSM**, não auditada em campo; **sem sentido único** (todo trecho é bidirecional) e **sem
  semáforo** → o desvio pode ser otimista.
- Desvio pelo **caminho mais rápido em fluxo livre**, **sem congestionamento** (o congestionamento é da
  simulação no GAMA, não deste cálculo).
- **Nomes do OSM incompletos**: só **~62%** dos trechos têm `name` (ver `vias_nomes.csv`); por isso um
  desvio pode citar poucas ruas ou nomes com grafia do OSM (ex.: "Rua João Aurcih").
- A **ponte Ibirama-Apiúna (BR-470 km 111)** não tem geometria do vão: tratada como fechamento dos trechos
  `trunk` da BR-470 e marcada `pendente_geometria`. A Defesa Civil informou que **não há alternativa
  próxima** (a saída é longa, pela Serra da Guaricana, via Ascurra e Sellin).
- As versões "**rua inteira**" são um **limite superior** (fecham mais do que o realista); prefira a versão
  "**≤ 40 m do risco**" para leitura.

## Como ler
`% sem alternativa` alta significa que fechar aquele trecho **isola** parte da cidade dos pontos críticos.
No teste, isso aparece forte na **BR-470/ponte (~52%)**, na **Rua Marquês do Herval (~58%)** e na
**SC-340 (~31%)** — coerente com a rede limitada de Ibirama. Os números são para **planejamento
comparativo**, não valores exatos de trânsito.
