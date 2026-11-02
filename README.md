# Simulação de tráfego em Ibirama sob eventos adversos: guia rápido

Disciplina 5OPMSA (UDESC/CEAVI). Agentes: carros, motos e pedestres. Eventos: alagamento, deslizamento e erosão, a partir das 49 áreas de risco da Defesa Civil. 

## Estado atual
| Parte | Estado |
|---|---|
| Mapa de risco (KMZ → shapefile) | Pronto |
| Simulador Python | Pronto e testado |
| Análise estatística | Pronta e testada |
| Modelo GAMA (`modelo/ibirama.gaml`) | Carrega e mostra a rede real. **Execução completa (play) ainda não confirmada** |
| Pontos críticos | **Reais** (hospital, bombeiros, Defesa Civil), em `dados/pontos_criticos.csv`. **Falta o abrigo**; o semáforo está em `dados/semaforos.csv` (só aparece no mapa interativo) |
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

**3. Pontos críticos.** Já existe `dados/pontos_criticos.csv` com hospital, bombeiros e Defesa Civil; rode o comando abaixo para gerar o `.shp` (e acrescente os abrigos quando tiver as coordenadas). Formato do CSV: `dados/pontos_criticos.csv` com as colunas `tipo,nome,lat,lon` (tipo: `hospital`, `bombeiros` ou `abrigo`; pelo menos um de cada; coordenadas pelo Google Maps, botão direito no local). Depois:
```
python scripts/04_pontos_criticos_para_shapefile.py
```
Tipos aceitos: `hospital`, `bombeiros`, `defesa_civil`, `abrigo` (hospital e bombeiros são obrigatórios). Sem abrigo, as métricas de acesso a abrigo ficam vazias.

**4. Rodar no GAMA.**
1. *File → New → GAMA Project*, nome `Ibirama`.
2. `modelo/ibirama.gaml` vai para `models/`; a pasta `dados/` inteira vai para `includes/` (fica `includes/dados/...`).
3. No topo do `ibirama.gaml`, ajuste:
   ```
   arquivo_vias   <- "vias.shp";
   arquivo_pontos <- "pontos_criticos.shp";
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

## População e tráfego (valores atuais)
- **Amostra de ~10% da frota** (Senatran, dez/2025): 1.270 carros (de 12.733 carros-equivalentes) e 420 motos (de 4.203); pedestres 250 (hipótese, sem fonte oficial).
- **Origens ponderadas pelo tipo de via** (`od_ponderada`): vias principais recebem mais origens (primary 8, secondary 6, tertiary 4, residential 1,5...). São pesos hipotéticos; o ideal é calibrar com contagens de tráfego.
- **Lentidão por fila** (já existia, agora com `fracao_amostra`): a capacidade de cada via considera que cada agente representa 1/0,10 veículos reais, e a lentidão tem piso de 10x. Com partidas espalhadas em 3 h quase não há fila; para testar horário de pico, reduza a *Janela de partida* (ex.: 60 ou 30 min).
- No Python, o resultado traz `cong_entradas_r50_pct`, `cong_fator_medio` e `cong_ocupacao_max` para medir o congestionamento.

## Cores do mapa no GAMA
Cinza escuro: rua normal. Laranja: rua a até 40 m de área de risco. Azul: rua alagada. Vermelho: rua fechada para carros. Triângulos: pontos críticos (vermelho hospital, laranja-avermelhado bombeiros, roxo Defesa Civil, verde abrigo).

## Pastas
`dados/` (shapefiles) · `scripts/` (00 a 06) · `python/` (simulador e testes) · `modelo/` (GAML) · `resultados/` (saídas)

## Se der erro
Copie a mensagem **inteira** (e a linha apontada) e mande de volta. Erros comuns: `python` não encontrado (reinstale marcando PATH ou use `py`), arquivo não encontrado no GAMA (confira `includes/dados/`) e rodar o script fora da pasta do projeto.

## O que falta
1. Coordenadas reais dos pontos críticos.
2. Respostas da Defesa Civil para calibrar os parâmetros (hipóteses listadas no `README.md`, seção 6).
