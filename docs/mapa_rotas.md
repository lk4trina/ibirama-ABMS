# Mapa interativo de rotas e desvios (`mapa_rotas.html`)

Ferramenta de **apoio e demonstração**, a pedido da Defesa Civil de Ibirama (ideia do *Alerta Blu* de
Blumenau): o usuário diz **de onde** e **para onde** quer ir; o mapa mostra o caminho e, se houver
fechamento no caminho, o **desvio**. **Não altera o modelo GAMA nem a simulação.**

Gerado por `scripts/09_mapa_rotas.py`. Saída: `resultados/mapa_rotas.html`.

## Aviso (sempre visível na interface)
**NÃO é alerta em tempo real.** Desvios **pré-calculados** sobre a rede do **OpenStreetMap**,
**sem sentido único**, **sem semáforos**, pelo caminho mais rápido em **fluxo livre** (sem
congestionamento). Fechamentos vêm de `interdicoes_defesa_civil.csv`, `vias_principais_defesa_civil.csv`
(informados pela Defesa Civil) e dos polígonos de risco. Trechos marcados `pendente/parcial` aparecem
como **hipótese** na lista.

## Como abrir
Duplo clique no `resultados/mapa_rotas.html`. **O roteamento funciona offline** (grafo embutido em JSON,
Dijkstra em JavaScript no navegador). Só o **fundo** (satélite Esri / OSM) depende de internet; o Leaflet
vem por CDN com **versão fixa** (1.9.4). Se abrir sem internet, o mapa-base fica cinza mas as rotas e os
fechamentos continuam sendo calculados e desenhados.

## O que dá para fazer
- **Origem e destino:** clicando no mapa (associa ao **nó da rede mais próximo** e mostra a distância de
  associação) ou **digitando** — autocompletar com nomes de rua (`vias_nomes.csv`, 242 ruas) e os
  **29 pontos críticos** (`pontos_criticos.geojson`, inclui o abrigo *Ginásio João Moretti*).
- **Modal:** carro, moto e a pé — mesmas velocidades do GAML (`VEL_CLASSE_KMH`; moto 1,1×; a pé 1,3 m/s).
- **Rota normal** (cinza tracejado) e **rota com desvio** (verde) quando um fechamento está no caminho;
  mostra distância, tempo em fluxo livre e o **acréscimo**. Se não houver alternativa, diz
  **"SEM ROTA ALTERNATIVA na rede OSM"** e **não desenha linha reta**.
- **Fechamentos:** caixas de seleção das interdições/vias principais da Defesa Civil; opção
  **"só os trechos a ≤40 m dos polígonos de risco"** (como no modelo) ou **"rua inteira"**; dá para
  **clicar num trecho** no mapa (camada *rede clicável*) para fechar/abrir à mão. Trechos fechados em
  **vermelho**, com a geometria real da rua (sem retas atravessando o mapa).
- **Atalhos:** "ir ao abrigo mais próximo" e "ir ao hospital" a partir da origem, com e sem os fechamentos.
- **Camadas:** satélite (Esri, Maxar, Earthstar Geographics), OSM, áreas de risco, pontos críticos.

## Igual ao modelo (fonte da verdade)
Rede, nós (extremos arredondados a 0,1 m), pesos e velocidades são os mesmos de `08_desvios.py` /
`python/simulador.py` / `models/ibirama.gaml`. Custo por trecho (tempo, s): carro `comp/vel`,
moto `comp/(vel·1,1)`, a pé `comp/1,3`. Distância = soma dos comprimentos reais dos trechos do caminho.

## Verificação
- **JS × Python** (`scripts/verif_rotas.py`): 20 pares origem-destino sorteados, com e sem fechamentos
  (40 casos). As distâncias **coincidem exatamente (máx. 0,000 m)**. O mesmo roteador JS
  (`resultados/mapa_rotas_router.js`) roda no Node e no HTML. O custo do Dijkstra-Python bate com
  `scipy.dijkstra` (algoritmo do script 08) a 0 s **quando os 12 pares de trechos paralelos são tratados
  por mínimo** — como um Dijkstra correto faz (o `csr_matrix` do scipy *soma* arestas paralelas, o que
  infla o custo; o roteador JS usa o menor, que é o certo).
- **Playwright headless** (`scripts/playwright_rotas.py`): abre o HTML, **sem erros no console**; busca e
  clique funcionam; a rota é desenhada; e no caso conhecido da **ponte Ibirama-Apiúna fechada** (nó 128 →
  nó 3) exibe "SEM ROTA ALTERNATIVA" **sem** desenhar o desvio.

## Limitações (ser honesto)
- **OSM sem sentido único e sem semáforo:** a rede é não-direcionada; rotas podem usar um sentido que na
  via real é proibido, e o tempo ignora paradas.
- **Associação a nó:** origem/destino são "puxados" para o nó mais próximo da rede; a distância de
  associação é mostrada, mas em locais fora de via pode ser grande.
- **Conectividade da rede** pode gerar **falso "sem alternativa"**: alguns trechos do OSM não se conectam
  por arredondamento dos extremos; nesses casos o "sem rota" pode ser artefato da rede, não da realidade.
- **Tempo em fluxo livre:** não há congestionamento; é um limite inferior do tempo de viagem.
- **Fechamentos são hipóteses de planejamento**, não o estado atual das vias.
