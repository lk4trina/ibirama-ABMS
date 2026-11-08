# ibirama-ABMS

Simulação baseada em agentes de tráfego e dispersão de fluxos em Ibirama sob alagamentos, deslizamentos e erosão de margem.

O modelo compara cenários. Ele não prevê chuva, nível do rio nem eventos reais.

## Execução

Abra `models/ibirama.gaml` no GAMA e execute:

- `Interativo`, para configurar e observar uma simulação;
- `Lote`, para executar combinações de evento, severidade, informação e presença de rede energizada.

Os resultados novos são acrescentados a `includes/resultados_gama_dc.csv`, que já contém o cabeçalho compatível com os indicadores ampliados. O arquivo `includes/resultados_gama.csv` foi preservado como histórico do modelo anterior.

## Dados principais

- `includes/dados/vias.shp`: rede viária;
- `includes/dados/riscos.shp`: 49 polígonos de risco;
- `includes/dados/pontos_criticos.geojson`: destinos críticos ampliados;
- `includes/dados/pontos_criticos_cadastro.csv`: cadastro e qualidade das coordenadas;
- `includes/dados/interdicoes_defesa_civil.csv`: ruas com interdições relatadas;
- `includes/dados/vias_principais_defesa_civil.csv`: vias principais e ponte crítica.

Consulte [`docs/dados_defesa_civil.md`](docs/dados_defesa_civil.md) para ver as fontes, hipóteses, limitações e alterações derivadas da reunião com a Defesa Civil.

## Scripts e simulador em Python

A pasta `python/` traz uma versão do modelo em Python (`simulador.py`), além de testes e utilitários.

O simulador em Python **reproduz as regras** do modelo GAMA (`models/ibirama.gaml`): perfil e duração do
alagamento (subida 1/3, platô 1/6, recessão), deslizamento com reabertura e `rede_energizada` (60–90 min),
erosão com colapso e reabertura, ativação por grau×severidade, pontos críticos do `pontos_criticos.geojson`
agrupados por grupo, os 6 grupos de acesso (com NaN no abrigo), a medição de acesso em `início + 25 min` e
o CSV com as **mesmas 53 colunas** do GAMA (um teste automático confere o cabeçalho).

> **Atenção:** o Python é **mesoscópico** (o agente atravessa cada trecho de uma vez) e o GAMA move o
> agente **passo a passo**, com geração de números aleatórios diferente. Então os números **não são
> idênticos**. Uma verificação cruzada (ver [`docs/python_vs_gaml.md`](docs/python_vs_gaml.md)) mostrou
> **boa equivalência nos desfechos** (% que conclui/volta/desiste/fica preso, Gini) e **diferenças maiores
> na acessibilidade** (sobretudo a pé e no cenário combinado, por ser um indicador topológico). Por isso,
> **os resultados do artigo vêm do GAMA**; o Python serve como **verificação cruzada** e para rodar muitas
> repetições rápido. Rode `python python/testes_logica.py` e, para os cenários, `python python/rodar_experimentos.py --rede real` (grava em `resultados/`, nunca em `includes/resultados_gama_dc.csv`).

## Desvios (rotas alternativas)

A pedido da Defesa Civil (ideia parecida com o **Alerta Blu** de Blumenau), `scripts/08_desvios.py`
pré-calcula **rotas alternativas** para trechos fechados e gera `includes/dados/desvios_sugeridos.csv`,
`resultados/mapa_desvios.html` (mapa), `resultados/desvios_exemplos.geojson` e `resultados/fig_desvios.png`.
**Não é alerta em tempo real** — são desvios para planejamento, sobre a rede do OSM, sem sentido único e
sem semáforo. Detalhes e limitações em [`docs/desvios.md`](docs/desvios.md).

## Arquivos de teste (fictícios)

Os arquivos com `_TESTE` ou `_SINTETICO` no nome (por exemplo `vias_teste_SINTETICO.shp`, `pontos_criticos_TESTE.csv`) são **dados fictícios**, usados só para experimentar os scripts e o modelo sem a rede real. **Não produzem resultado válido** e não devem ser usados nas análises.

## Fontes dos dados

- Frota de veículos: **Senatran — Frota de veículos por município e tipo** (dez/2025).
- População e domicílios: **IBGE — Censo Demográfico 2022**.
- Áreas de risco, pontos críticos, interdições e tempos de interdição: **Defesa Civil de Ibirama** (reunião do projeto); detalhes e demais fontes em [`docs/dados_defesa_civil.md`](docs/dados_defesa_civil.md).
- Rede viária: **OpenStreetMap**.
