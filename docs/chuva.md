# Duração da chuva (HIPÓTESE) e análise de sensibilidade

## Por que existe este parâmetro
Os números de duração da Defesa Civil ("cerca de 30 min; basta a chuva cessar que a água baixa rápido")
descrevem o **tempo de descida depois que a chuva para**, não a duração total do evento. A chuva em si
pode durar horas, e a rua fica alagada **enquanto chove**. Com o perfil antigo (evento inteiro em 30 min),
~98% dos agentes concluíam a viagem em qualquer cenário e os cenários quase não se diferenciavam.

`duracao_chuva_min` é uma **HIPÓTESE** (não informada pela Defesa Civil). Está marcada como hipótese no
código (`models/ibirama.gaml` linha 65, `python/simulador.py` `Params`), na interface (categoria "Evento")
e aqui. **O padrão é 0** (reproduz exatamente o comportamento anterior) até se decidir o valor final.

## O que muda com `duracao_chuva_min > 0`
- **Alagamento:** a água sobe em 10 min (a mesma subida de antes), fica no **pico enquanto chove**
  (`duracao_chuva_min − 10`, mínimo 0) e **desce em `duracao_alagamento_min` (30 min) depois que a chuva
  para**. A profundidade de pico por grau não muda.
- **Deslizamento:** o instante de início de cada polígono é sorteado **dentro da duração da chuva**
  (não só nos primeiros 20 min). A obstrução dura `duracao_deslizamento_min` (30 min), ou 60–90 min com
  `rede_energizada`, como antes.
- **Erosão:** não muda.
- **`medicao_acesso_min`** (padrão 25): momento da medição de acessibilidade, em min após o início.
  Com chuva longa, medir mais tarde (no platô) é mais representativo — **o padrão não foi alterado**.

`duracao_chuva_min = 0` reproduz o perfil de 30 min. Isso foi **verificado por execução** (regressão no
GAMA: com chuva 0, as 53 colunas antigas são idênticas às da versão anterior, mesmas 10 sementes).

## Sensibilidade (severidade alta, info parcial, rede não energizada)
GAMA: 10 sementes (experimento `LoteChuva` / headless). Python: 30 sementes. Rede **real**.
Média das 30/10 execuções.

### combinado — `% que conclui (carro)` e `% desiste (carro)`
| chuva (min) | GAMA concluiu | Python concluiu | GAMA desistiu | Python desistiu |
|---|---|---|---|---|
| 0   | 97,6 | 99,7 | 2,3 | 0,2 |
| 60  | 94,8 | 94,0 | 4,5 | 3,7 |
| 120 | 89,7 | 85,5 | 8,4 | 9,7 |
| 240 | 87,5 | 82,1 | 10,3 | 12,1 |

### alagamento — `% que conclui (carro)`
| chuva (min) | GAMA | Python |
|---|---|---|
| 0   | 97,7 | 100,0 |
| 60  | 94,6 | 95,5 |
| 120 | 88,8 | 87,8 |
| 240 | 86,1 | 84,2 |

### Acesso ao hospital (`sem acesso %`, combinado) — cai com chuva longa
| chuva (min) | GAMA carro | Python carro | GAMA a pé | Python a pé |
|---|---|---|---|---|
| 0   | 30,0 | 34,8 | 21,1 | 30,0 |
| 60  | 22,3 | 28,4 | 14,3 | 23,4 |
| 120 | 18,4 | 21,5 | 10,0 | 16,5 |
| 240 | 15,9 | 19,6 |  8,4 | 14,2 |

> O acesso **cai** com chuva mais longa porque ele é medido em **+25 min**: com a chuva espalhando os
> inícios dos deslizamentos ao longo de horas, há **menos trechos fechados nesse instante**. Isso é um
> efeito do **momento da medição**, não de "menos risco". Para chuva longa, medir no platô
> (`medicao_acesso_min` maior) é mais representativo.

### Nível de informação (combinado, chuva 120)
A informação quase não muda **quantos concluem**; muda a divisão entre **voltar** e **desistir**:
com informação ampla as pessoas **desistem** mais cedo; com informação local elas **voltam** mais.
(Ex. Python: voltou carro local 8,3% × amplo 1,6%; desistiu carro local 5,7% × amplo 12,8%.)

## Leitura e recomendação (a decisão é sua)
- **A chuva diferencia os cenários**, que era o objetivo. Com chuva 0 o modelo volta ao problema dos ~98%
  concluindo; a partir de ~120 min os cenários se separam de forma clara e as duas ferramentas concordam
  na tendência.
- **Prós/contras de cada valor:**
  - **60 min** — efeito modesto (~94% concluem); diferencia pouco.
  - **120 min** — efeito claro (~86–90% concluem); separa cenários sem ser extremo; chuva de ~2 h é
    plausível para os eventos da região. É um meio-termo.
  - **240 min** — efeito forte (~82–87% concluem); pressupõe chuva de 4 h, mais agressivo.
- **Recomendação:** tratar **120 min como ponto de calibração para discussão** e rodar 60 e 240 como
  limites, **sem** fixar o padrão. O valor padrão no código **segue 0** até sua decisão.
- **Dúvidas em aberto:** (1) a duração real típica da chuva nos eventos de Ibirama (pedir à Defesa Civil);
  (2) se convém medir o acesso no platô da chuva (`medicao_acesso_min`) em vez de +25 min.

Os **números do artigo saem do GAMA**; o Python serve de verificação cruzada e para rodar muitas
repetições rápido. Ver `docs/python_vs_gaml.md` para as diferenças entre as duas ferramentas.
