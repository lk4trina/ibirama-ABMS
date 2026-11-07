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
