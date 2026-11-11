# Progresso dos resultados finais (artigo 5OPMSA)

Arquivo mantido durante o trabalho. Entrega: 12/11/2026. Branch: `dia-completo`. Sem push.

## Status das execuções no GAMA

<!-- STATUS:INICIO -->
Atualizado em: 2026-11-11 13:18:16  |  estado: RODANDO

| Experimento | Feitas (arquivo valido) | Esperado | Falta |
|---|---|---|---|
| A_principal | 550 | 550 | 0 |
| B_chuva | 100 | 100 | 0 |
| C_horario | 69 | 120 | 51 |
| D_persistente | 0 | 275 | 275 |
| **Total** | **719** | **1045** | **326** |

Linhas em falhas.log: 0 (desistidos nesta sessao: 0).
Tempo medio por execucao (ultimas 50): 130 s; com 5 em paralelo, faltam ~2,4 h.
<!-- STATUS:FIM -->

## Como retomar (PowerShell, na raiz do repositório)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\rodar_final.ps1
```

- O script pula as execuções que já têm arquivo válido em `C:\Temp\ibirama_final\runs\<experimento>\`.
- Para parar com segurança: crie o arquivo `C:\Temp\ibirama_final\PARAR` (ele termina as execuções em curso e não inicia outras).
- Falhas ficam em `C:\Temp\ibirama_final\falhas.log` (cada execução é repetida até 2 vezes).

## Onde fica cada coisa

- GAMA instalado só para este trabalho: `C:\Temp\ibirama_final\GAMA` (instalador de `Downloads`, instalação silenciosa).
- Cópias do projeto (uma por processo): `C:\Temp\ibirama_final\slots\s1..s5`. O `models\ibirama.gaml` é cópia exata do repositório (SHA-256 em `runs\modelo_sha256.txt`).
- Resultados: `C:\Temp\ibirama_final\runs\<experimento>\<cenario>_<semente>.csv` (fora do repositório).

## Feito

### (a) Verificado por execução
- Etapa 0 (parcial): ver seção abaixo, preenchida durante o trabalho.

### (b) Por leitura
- `until: (time > horizonte_min * 60.0)` nos três experimentos em lote (linhas 992, 1004 e 1015 de `models/ibirama.gaml`).

### (c) Não verificado
- (a preencher)

## Falta
- Lotes A, B, C e D (1045 execuções), consolidação e validação, análise, figuras e texto-base.
