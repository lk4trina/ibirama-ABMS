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

A pasta `python/` traz um protótipo do modelo em Python (`simulador.py`), além de testes e utilitários.

> **Atenção:** o código em `python/` está **dessincronizado** do modelo GAMA. As durações novas (alagamento/deslizamento de ~30 min), os grupos de acesso ampliados, o parâmetro `rede_energizada`, os pontos críticos ampliados e o esquema de 53 colunas do CSV **ainda não** acompanham a versão GAML atual. O simulador em Python serve apenas para prototipagem e testes rápidos e **não gera resultados válidos para o artigo**. Os resultados do trabalho vêm do modelo GAMA (`models/ibirama.gaml`).

## Arquivos de teste (fictícios)

Os arquivos com `_TESTE` ou `_SINTETICO` no nome (por exemplo `vias_teste_SINTETICO.shp`, `pontos_criticos_TESTE.csv`) são **dados fictícios**, usados só para experimentar os scripts e o modelo sem a rede real. **Não produzem resultado válido** e não devem ser usados nas análises.

## Fontes dos dados

- Frota de veículos: **Senatran — Frota de veículos por município e tipo** (dez/2025).
- População e domicílios: **IBGE — Censo Demográfico 2022**.
- Áreas de risco, pontos críticos, interdições e tempos de interdição: **Defesa Civil de Ibirama** (reunião do projeto); detalhes e demais fontes em [`docs/dados_defesa_civil.md`](docs/dados_defesa_civil.md).
- Rede viária: **OpenStreetMap**.
