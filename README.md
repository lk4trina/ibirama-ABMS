# Simulação de tráfego em Ibirama sob eventos adversos: guia rápido

Disciplina 5OPMSA (UDESC/CEAVI). Agentes: carros, motos e pedestres. Eventos: alagamento, deslizamento e erosão, a partir das 49 áreas de risco da Defesa Civil.

## Estado atual
| Parte | Estado |
|---|---|
| Mapa de risco (KMZ → shapefile) | Pronto |
| Simulador Python | Pronto e testado |
| Análise estatística | Pronta e testada |
| Modelo GAMA (`modelo/ibirama.gaml`) | Carrega e mostra a rede real. **Execução completa (play) ainda não confirmada** |
| Pontos críticos (hospital, bombeiros, abrigo) | **Fictícios (`_TESTE`)**: faltam as coordenadas reais |
| Parâmetros do modelo | **Hipóteses**: a Defesa Civil ainda não respondeu |

Nenhum número gerado com arquivos `_TESTE` ou `_SINTETICO` pode ir para o artigo.

## Como rodar

**1. Preparar (uma vez).** Instale o Python 3.11+ (python.org, marcando "Add Python to PATH"). Extraia o zip, abra o PowerShell **dentro da pasta do projeto** e rode:
```
pip install -r requirements.txt
```

**2. Gerar os dados reais** (internet; o 02 é obrigatório, os outros são opcionais):
```
python scripts/02_baixar_rede_osm.py          # ruas reais -> dados/vias.shp
python scripts/02b_baixar_camadas_mapa.py     # prédios, rios, verde (visual)
python scripts/05_gerar_fundo_mapa.py         # imagem de fundo (--fonte satelite / relevo / claro)
python scripts/06_mapa_interativo.py          # mapa com zoom -> resultados/mapa_interativo.html
```

**3. Pontos críticos reais.** Crie `dados/pontos_criticos.csv` com as colunas `tipo,nome,lat,lon` (tipo: `hospital`, `bombeiros` ou `abrigo`; pelo menos um de cada; coordenadas pelo Google Maps, botão direito no local). Depois:
```
python scripts/04_pontos_criticos_para_shapefile.py
```

**4. Rodar no GAMA.**
1. *File → New → GAMA Project*, nome `Ibirama`.
2. `modelo/ibirama.gaml` vai para `models/`; a pasta `dados/` inteira vai para `includes/` (fica `includes/dados/...`).
3. No topo do `ibirama.gaml`, ajuste:
   ```
   arquivo_vias   <- "vias.shp";
   arquivo_pontos <- "pontos_criticos.shp";   // "pontos_criticos_TESTE.shp" enquanto não tiver os reais
   usar_camadas_mapa <- true;                  // se usou o 02b
   usar_fundo_imagem <- false;                 // true se usou o 05 (nesse caso deixe a de cima em false)
   ```
   Use só um dos dois visuais.
4. Experimento **Interativo**: mapa, parâmetros e gráficos. Experimento **Lote**: todos os cenários, grava `includes/resultados_gama.csv`.

**5. Alternativa: simulador Python** (mesmas regras do modelo):
```
python python/testes_logica.py                                   # deve terminar com "TODOS OS TESTES PASSARAM"
python python/simulador.py --evento alagamento --severidade alta --info local --rede real
python python/rodar_experimentos.py --reps 30 --rede real        # todos os cenários
```

**6. Estatística e gráficos:**
```
python scripts/03_analise.py resultados/resultados_python_real.csv
```
Saída em `resultados/analise/`: média e desvio padrão, Kruskal-Wallis, Mann-Whitney (Bonferroni) e A12.

## Cores do mapa no GAMA
Cinza escuro: rua normal. Laranja: rua a até 40 m de área de risco. Azul: rua alagada. Vermelho: rua fechada para carros. Triângulos: pontos críticos.

## Pastas
`dados/` (shapefiles) · `scripts/` (00 a 06) · `python/` (simulador e testes) · `modelo/` (GAML) · `resultados/` (saídas)

## Se der erro
Copie a mensagem **inteira** (e a linha apontada) e mande de volta. Erros comuns: `python` não encontrado (reinstale marcando PATH ou use `py`), arquivo não encontrado no GAMA (confira `includes/dados/`) e rodar o script fora da pasta do projeto.

