# Por que o lote principal tem 550 execuções e não 900

O experimento `Lote` do GAML combina 5 eventos × 3 severidades × 3 níveis de informação × 2 valores de
`rede_energizada` × 10 sementes = **900 execuções**. O relatório anterior mostrou que esse produto repete valores.
Os resultados finais usam **550 execuções** (item A), que cobrem as mesmas situações distintas.

## Motivo

| Evento | O que o fator não faz | Como foi reduzido | Execuções por semente |
|---|---|---|---|
| nenhum | Sem evento, severidade e informação não têm o que alterar. `rede_energizada` só vale para deslizamento | 1 cenário (baixa / local / falso) | 1 |
| alagamento | `rede_energizada` só altera a duração do deslizamento | rede = falso, 3 × 3 | 9 |
| erosão | idem | rede = falso, 3 × 3 | 9 |
| deslizamento | os quatro fatores atuam | 3 × 3 × 2 | 18 |
| combinado | idem (inclui deslizamento) | 3 × 3 × 2 | 18 |
| **Total por semente** | | | **55** (× 10 sementes = **550**) |

Os 900 do Lote completo têm 90 linhas por semente. As 35 que saem são cópias.

## Conferido por execução (GAMA, semente explícita)

Foram rodadas 8 execuções extras (experimento `V_equivalencia`, sementes 1 e 2) com fatores que, pela lógica acima,
não deveriam mudar nada. Cada uma foi comparada com o cenário de base, mesma semente, nas 65 colunas de resultado
(todas menos as 4 que identificam o cenário):

| Execução extra | Comparada com | Resultado |
|---|---|---|
| nenhum / alta / amplo / rede falso | nenhum / baixa / local | idênticas nas 65 colunas (2 de 2 sementes) |
| nenhum / média / parcial / rede verdadeiro | nenhum / baixa / local | idênticas (2 de 2) |
| alagamento / média / parcial / rede verdadeiro | mesmo cenário, rede falso | idênticas (2 de 2) |
| erosão / alta / amplo / rede verdadeiro | mesmo cenário, rede falso | idênticas (2 de 2) |

Isso confirma, por execução, que severidade e informação não mudam o cenário "nenhum", e que `rede_energizada` não
muda alagamento nem erosão. A amostra é pequena (8 execuções, 2 sementes), então vale como prova de que a redução
não perdeu informação nos casos testados, não como prova para todas as combinações. Os arquivos ficam em
`C:\Temp\ibirama_final\runs\V_equivalencia\` (fora do repositório) e não entram no CSV final.

## Efeito colateral a ter em mente

Em deslizamento e combinado, `rede_energizada` **altera o sorteio dos polígonos ativados** (só 13 % dos pares
rede falso / verdadeiro, mesma semente e mesmo cenário, têm o mesmo número de polígonos ativos no lote A). Então a
comparação entre rede energizada ou não mistura o efeito da duração com outra realização do sorteio.
Ver "Anomalias" em `docs/resultados_para_artigo.md`.
