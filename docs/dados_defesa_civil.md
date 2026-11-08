# Incorporação das respostas da Defesa Civil de Ibirama

## Escopo

Este documento registra os dados recebidos durante a reunião do projeto e separa dados informados, dados geocodificados e hipóteses do modelo. A simulação compara cenários; ela não prevê chuva, nível do rio nem a ocorrência de um desastre real.

## Dados informados pela Defesa Civil

### Tempos de interdição

- Alagamento: aproximadamente 30 minutos; a água baixa rapidamente após a chuva cessar.
- Deslizamento sem rede energizada: aproximadamente 30 minutos.
- Deslizamento com rede energizada: entre 60 e 90 minutos.
- Erosão: duração não informada. O modelo conserva 480 minutos como hipótese ajustável.

### Classificação de risco

A nomenclatura foi explicitada no modelo sem confundir risco territorial com severidade do cenário:

| Grau da camada | Código |
|---|---|
| Baixo | R1 |
| Médio | R2 |
| Alto | R3 |
| Muito Alto | R4 |

A camada disponível contém R2, R3 e R4. Não há polígono R1.

### Ruas com registros de interdição

A relação recebida está em `includes/dados/interdicoes_defesa_civil.csv`. O mapa indicado pela equipe contém 49 polígonos de áreas de risco, mas seu KML não possui linhas nomeadas representando os trechos interditados. A rede `vias.shp` também não possui nome de rua ou identificador estável. Por isso, a associação continua sendo espacial: o modelo afeta as vias que interceptam cada polígono acrescido do `buffer_m`.

Não foi criada uma falsa correspondência por nome. A interdição determinística das sete ruas e da ponte depende de uma rede enriquecida com nomes/IDs ou de linhas desenhadas especificamente para esses trechos.

### Vias principais e ponte

A relação está em `includes/dados/vias_principais_defesa_civil.csv`. A ponte entre Ibirama e Apiúna, na BR-470 km 111, foi cadastrada como item pendente de geometria. A alternativa mencionada passa pela Serra da Guaricana, com acesso por Ascurra e saída no bairro Sellin.

## Pontos críticos

O arquivo operacional `includes/dados/pontos_criticos.geojson` reúne:

- hospital, bombeiros e Defesa Civil;
- escolas estaduais, municipais e particulares informadas;
- CEIs;
- IFC e UDESC/CEAVI;
- UBSs e ESFs informadas;
- abrigo municipal (Ginásio de Esportes João Moretti, Centro).

O cadastro rastreável, com endereço, coordenadas, precisão, fonte do cadastro e fonte da coordenada, está em `includes/dados/pontos_criticos_cadastro.csv`.

As precisões significam:

- `informada_equipe`: coordenada já existente no projeto;
- `ponto_endereco`: resultado correspondente ao número do endereço;
- `endereco_interpolado`: posição estimada ao longo da rua;
- `poi`: estabelecimento encontrado por nome;
- `centro_da_via`: endereço sem número localizado, representado por um ponto da via;
- `centro_do_bairro`: localização provisória, inadequada para conclusões em escala de quadra;
- `poi_baixa_confianca`: resultado possível que precisa de confirmação local.

Antes dos resultados finais, a Defesa Civil ou a equipe deve validar especialmente ESF Areado, PSF Serra São Miguel e PSF Progresso.

**Abrigo municipal (cadastrado em nov/2025):** o **Ginásio de Esportes João Moretti** (Centro de Ibirama) foi cadastrado como abrigo em caso de enchentes e temporais, com coordenada `informada_equipe` (precisão alta; fica a ~8 m de um nó da rede e dentro da área das vias). Fonte: **equipe do projeto — a confirmar com a Defesa Civil**. Com isso, o indicador de acesso ao abrigo **deixa de ser `NaN`** (antes não havia endereço oficial). O modelo **GAMA lê o `includes/dados/pontos_criticos.geojson`**, então passa a medir o acesso ao abrigo. O **simulador em Python**: na versão alinhada (branch `python-sync`, que também lê o geojson agrupado por grupo) ele **também passa a medir o abrigo**; na versão antiga (que lia o CSV de 3 pontos `pontos_criticos.csv`) o abrigo seguiria `NaN`. Ver `docs/python_vs_gaml.md`.

## Alterações no modelo

O arquivo `models/ibirama.gaml` agora:

1. carrega os pontos ampliados do GeoJSON;
2. registra R2, R3 e R4 explicitamente;
3. usa 30 minutos para o perfil completo de alagamento;
4. reabre vias após 30 minutos de deslizamento sem rede energizada;
5. sorteia a liberação entre 60 e 90 minutos quando `rede_energizada=true`;
6. reabre trechos de erosão após a duração hipotética configurada, desde que o término ocorra dentro do horizonte simulado;
7. mede, 25 minutos após o início-base, o acesso a hospital, bombeiros, Defesa Civil, educação, UBS e abrigo; como as zonas podem começar até 20 minutos depois, essa medição representa uma janela do evento e não um pico simultâneo;
8. inclui os parâmetros de duração e rede energizada no novo `includes/resultados_gama_dc.csv`, sem misturar o esquema novo com os resultados históricos.

Os estados das vias são recalculados a cada cinco minutos simulados. Portanto, uma liberação é refletida na primeira atualização de cinco minutos após o término teórico.

## Fontes externas

- [Mapa de áreas de risco de Ibirama no Google My Maps](https://www.google.com/maps/d/viewer?mid=1AhHZ_XgW2E1Hio97Xshoy1YBsOaRllY)
- [Relação de escolas de Ibirama baseada no Censo Escolar](https://prospectei.app.br/escolas/cidade/ibirama-sc/)
- [QEdu, município de Ibirama](https://qedu.org.br/municipio/4206900-ibirama/busca)
- [ArcGIS World Geocoding Service](https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer)
- [OpenStreetMap](https://www.openstreetmap.org/copyright)

O conteúdo consultado nas fontes externas foi resumido e reescrito para atender às restrições de licenciamento. As coordenadas geocodificadas devem ser tratadas como dados derivados sujeitos a validação local.
