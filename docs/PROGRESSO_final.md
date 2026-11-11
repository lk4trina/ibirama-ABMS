# Progresso dos resultados finais (artigo 5OPMSA)

Entrega: 12/11/2026. Branch: `dia-completo`. Sem push. Atualizado em 11/11/2026, ~16:30.

## Status

<!-- STATUS:INICIO -->
Atualizado em: 2026-11-11 15:47:14  |  estado: CONCLUIDO

| Experimento | Feitas (arquivo valido) | Esperado | Falta |
|---|---|---|---|
| A_principal | 550 | 550 | 0 |
| B_chuva | 100 | 100 | 0 |
| C_horario | 120 | 120 | 0 |
| D_persistente | 275 | 275 | 0 |
| **Total** | **1045** | **1045** | **0** |

Falhas: 0 (nao existe `falhas.log`). Verificacao extra `V_equivalencia`: 8 de 8.
<!-- STATUS:FIM -->

## Etapas

- [x] Etapa 0: conferência, ambiente Python (numpy 2.3.5, matplotlib 3.11.2), `testes_logica.py`, `until` nos 3 experimentos.
- [x] Etapa 1: lotes A, B, C e D no GAMA headless; consolidação e validação; CSV final em `includes/resultados_gama_dc.csv` (1015 linhas únicas).
- [x] Etapa 2: tabelas T1-T6 (CSV e LaTeX) e testes em `docs/tabelas/`; verificação cruzada com o Python.
- [x] Etapa 3: figuras A-F em `docs/figuras/`.
- [x] Etapa 4: `docs/resultados_para_artigo.md` e `docs/lote_principal_equivalencia.md`.

## Como refazer / retomar (PowerShell, na raiz do repositório)

```powershell
# lotes (pula o que já tem arquivo válido; crie C:\Temp\ibirama_final\PARAR para parar com segurança)
powershell -ExecutionPolicy Bypass -File scripts\rodar_final.ps1
```

Python (ambiente fora do repositório, `numpy<2.4`):

```bash
python scripts/10_consolidar.py --final     # valida os 4 experimentos e grava includes/resultados_gama_dc.csv
python scripts/11_tabelas.py                # docs/tabelas/
python scripts/12_figuras.py                # docs/figuras/ (a E precisa de C:\Temp\ibirama_final\diag\agentes_*_s1.csv)
python scripts/03_analise.py resultados/resultados_gama_dc.csv   # copie o CSV para resultados/ antes: a saída vai para resultados/analise/ (ignorado pelo Git)
```

## Onde fica cada coisa (fora do repositório)

- GAMA 2025.06.4: `C:\Temp\ibirama_final\GAMA` (instalado em silêncio a partir do instalador em Downloads; `Gama.ini` com `-Xms512m`
  e sem `AlwaysPreTouch` por falta de memória; original em `Gama.ini.original`).
- Cópias do projeto: `...\slots\s1..s5`. Linhas: `...\runs\<experimento>\<cenario>_<semente>.csv`. Consolidados: `...\consolidados\`.
- Diagnóstico da Figura E: `...\diag\`. Verificação cruzada: `...\xcheck\py_lotechuva_real.csv`.
- SHA-256 do modelo: `...\runs\modelo_sha256.txt` (F1320D4F...). `models/ibirama.gaml` não foi alterado.

## (a) Verificado por execução
Ver seção 0 de `docs/resultados_para_artigo.md`.

## (b) Por leitura
`until` com `>` nos três experimentos; explicação da anomalia dos destinos iguais (hospital, bombeiros, Defesa Civil, abrigo).

## (c) Não verificado
Relação chuva → alagamento; causa do "sem acesso" > 0 sem evento; mecanismo pelo qual mais informação não melhora a conclusão.
