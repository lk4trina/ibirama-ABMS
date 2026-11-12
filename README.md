# ibirama-ABMS

Simulação baseada em agentes do tráfego de Ibirama em situações de alagamento, deslizamento e erosão de margem.

O modelo compara cenários para apoiar estudos e planejamento. Ele não prevê chuva, nível do rio ou acontecimentos reais.

## Como abrir e rodar no GAMA

O projeto entregue já contém a rede de ruas, as áreas de risco, os pontos críticos, os ícones e a imagem de fundo. Portanto, **não é necessário executar os scripts Python para abrir e rodar esta versão no GAMA**. Os scripts são opcionais e só servem para quem quiser refazer ou modificar os dados e os recursos visuais (veja a seção [Scripts Python (opcionais)](#scripts-python-opcionais)).

1. Baixe e extraia o ZIP da branch `versao-final`.
2. Instale e abra o **GAMA 2025.06.4**.
3. Abra o arquivo `models/ibirama.gaml`.
4. Escolha um dos experimentos e clique em executar:
   - `Interativo`: permite configurar e acompanhar uma simulação no mapa;
   - `Lote`: executa automaticamente as combinações de evento, severidade, informação e rede energizada, sem mapa;
   - `LoteChuva`: executa automaticamente as chuvas de 0, 60, 120, 240 e 780 minutos, sem mapa;
   - `LoteHorario`: executa automaticamente os horários de 06:30, 10:30 e 16:30, sem mapa.

> **Sobre os experimentos em lote:** `Lote`, `LoteChuva` e `LoteHorario` não têm mapa. Ao executá-los, o GAMA mostra uma tela vazia (preta), e isso é normal. Os resultados são acrescentados em `includes/resultados_gama_dc.csv`. Para ver o mapa e os agentes, use o experimento `Interativo`.

A imagem `includes/dados/fundo_mapa_leve.jpg` já está no projeto. O GAMA encontra e usa essa imagem automaticamente. Se o arquivo for removido, o GAMA usa um fundo vetorial simples e a simulação continua funcionando normalmente.

> **Atenção:** para preservar o arquivo final entregue, faça uma cópia de `includes/resultados_gama_dc.csv` antes de executar uma simulação completa. O GAMA acrescenta novos resultados nesse arquivo.

Em execuções em lote, use somente uma simulação por processo do GAMA. Várias simulações concorrentes dentro do mesmo processo apresentaram erros esporádicos durante os testes.

## Scripts Python (opcionais)

**Nenhum script Python é obrigatório para rodar a simulação no GAMA.** Use-os somente se quiser **recriar ou modificar os dados e os recursos visuais**. Quem apenas quer abrir e rodar o modelo pode ignorar esta seção.

Para usar os scripts, instale o Python 3.11 ou mais recente. Abra o terminal na pasta principal do projeto e execute:

```bash
pip install -r requirements.txt
```

### Recriar as áreas de risco

Opcional. Use este comando se o arquivo KMZ das áreas de risco for alterado. Ele lê `includes/dados/AREAS_DE_RISCO_IBIRAMA.kmz` e recria os arquivos de risco usados pelo GAMA:

```bash
python scripts/01_kmz_para_shapefile.py
```

### Recriar a rede de ruas

Opcional. Use este comando se quiser baixar novamente as ruas do OpenStreetMap. Ele precisa de internet e usa as áreas de risco para definir a região que será baixada:

```bash
python scripts/02_baixar_rede_osm.py
```

> Para reproduzir os resultados apresentados no projeto, prefira os arquivos que já estão na branch. Baixar novamente o OpenStreetMap no futuro pode gerar uma rede diferente.

### Recriar a imagem de fundo do GAMA

Opcional. A imagem `includes/dados/fundo_mapa_leve.jpg` já vem pronta no projeto. Use este comando somente se quiser gerá-la de novo ou trocar o fundo. Ele precisa que `includes/dados/vias.shp` exista e gera `includes/dados/fundo_mapa_leve.jpg`:

```bash
python scripts/05_gerar_fundo_mapa.py
```

Também é possível escolher outro fundo, trocando `claro` por `relevo` ou `satelite`:

```bash
python scripts/05_gerar_fundo_mapa.py --fonte claro
```

A imagem muda somente a aparência do mapa. Ela não altera as regras nem os resultados da simulação.

### Camadas vetoriais opcionais

O comando abaixo baixa prédios, rios, água e áreas verdes:

```bash
python scripts/02b_baixar_camadas_mapa.py
```

Essas camadas são apenas visuais. Para usá-las no GAMA, altere no início de `models/ibirama.gaml`:

```gaml
bool usar_camadas_mapa <- true;
```

A versão entregue usa a imagem de fundo e mantém essa opção como `false`.

### Mapa interativo separado do GAMA

Opcional. O comando abaixo cria `resultados/mapa_interativo.html`, um mapa com zoom e seleção de camadas. Ele abre no navegador e é uma ferramenta separada da simulação no GAMA:

```bash
python scripts/06_mapa_interativo.py
```

## Como a simulação funciona

Cada execução representa um dia útil, das **06:00 às 19:00**, totalizando 780 minutos. Cada agente faz uma viagem no dia.

As saídas são distribuídas principalmente em três horários de pico:

- 07:00–08:00;
- 11:00–12:00;
- 17:00–18:00.

Os horários foram informados pela Defesa Civil. A proporção de viagens em cada pico é uma hipótese do modelo.

Os cenários incluem:

- nenhum evento;
- alagamento;
- deslizamento;
- erosão;
- combinação dos três eventos.

Também são comparados diferentes níveis de severidade, informação, duração da chuva, horário do evento e presença de fiação elétrica energizada.

## Dados principais

- `includes/dados/vias.shp`: rede viária;
- `includes/dados/riscos.shp`: 49 polígonos de risco;
- `includes/dados/pontos_criticos.geojson`: hospital, bombeiros, Defesa Civil, escolas, unidades de saúde e abrigo;
- `includes/dados/pontos_criticos_cadastro.csv`: origem e qualidade das coordenadas;
- `includes/dados/interdicoes_defesa_civil.csv`: ruas com interdições relatadas;
- `includes/dados/vias_principais_defesa_civil.csv`: vias principais e ponte crítica;
- `includes/dados/fundo_mapa_leve.jpg`: imagem usada automaticamente no fundo do GAMA.

As fontes, hipóteses e limitações estão detalhadas em [`docs/dados_defesa_civil.md`](docs/dados_defesa_civil.md).

## Simulador e testes em Python

A pasta `python/` contém uma versão das regras do modelo para testes e comparação com o GAMA. Ela também é opcional para rodar o GAMA.

Para executar os testes de lógica:

```bash
python python/testes_logica.py
```

Para executar cenários na rede real:

```bash
python python/rodar_experimentos.py --rede real
```

O Python e o GAMA não produzem números exatamente iguais. O Python move cada agente por trecho completo, enquanto o GAMA move o agente passo a passo. Os dois programas também usam geradores de números aleatórios diferentes.

A comparação mostrou boa semelhança nos resultados de conclusão, retorno, desistência e agentes presos. Os resultados oficiais do trabalho são os do GAMA. Mais detalhes estão em [`docs/python_vs_gaml.md`](docs/python_vs_gaml.md).

## Duração da chuva

O parâmetro `duracao_chuva_min` controla por quanto tempo os efeitos da chuva permanecem no cenário.

- 60 minutos representa a fase intensa de aproximadamente uma hora;
- 780 minutos representa chuva durante todo o dia simulado;
- 0, 120 e 240 minutos são valores usados para testar a sensibilidade do modelo.

Os valores de 60 e 780 minutos usam como referência matérias do GCD e ND Mais, de setembro de 2026. A relação entre duração da chuva e duração do alagamento continua sendo uma hipótese.

Mais detalhes estão em [`docs/chuva.md`](docs/chuva.md).

## Desvios e mapas de rotas

Opcional. O script abaixo calcula rotas alternativas para planejamento:

```bash
python scripts/08_desvios.py
```

O mapa de rotas pode ser recriado com:

```bash
python scripts/09_mapa_rotas.py
```

Os desvios não funcionam como alerta em tempo real. Eles usam a rede do OpenStreetMap sem sentido único e sem semáforos. As limitações estão em [`docs/desvios.md`](docs/desvios.md) e [`docs/mapa_rotas.md`](docs/mapa_rotas.md).

## Tabelas, figuras e resultados finais

Os resultados oficiais estão em `includes/resultados_gama_dc.csv`.

Para recriar as tabelas e os testes estatísticos (opcional):

```bash
python scripts/11_tabelas.py
```

Para recriar as figuras (opcional):

```bash
python scripts/12_figuras.py
```

A Figura E precisa dos arquivos detalhados por agente que foram gerados durante a execução final e ficaram fora do repositório. As outras figuras usam os arquivos já incluídos no projeto.

O processo final foi:

1. executar os lotes no GAMA com `scripts/rodar_final.ps1`;
2. validar e consolidar as saídas com `scripts/10_consolidar.py`;
3. gerar análises, tabelas e figuras com `scripts/03_analise.py`, `scripts/11_tabelas.py` e `scripts/12_figuras.py`.

Foram feitas 1.045 execuções oficiais. Depois da retirada de 30 resultados repetidos entre os lotes, o arquivo final ficou com 1.015 resultados únicos.

## Arquivos de teste

Os arquivos com `_TESTE` ou `_SINTETICO` no nome são fictícios e servem somente para testar o código. Eles não devem ser usados para produzir resultados ou conclusões sobre Ibirama.

## Fontes dos dados

- Frota de veículos: Senatran, dezembro de 2025;
- população e domicílios: IBGE, Censo 2022;
- áreas de risco, pontos críticos, interdições e tempos: Defesa Civil de Ibirama;
- rede viária: OpenStreetMap;
- duração da chuva: GCD e ND Mais, setembro de 2026.
