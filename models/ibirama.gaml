/**
 * COMO O MODELO FUNCIONA
 *  - Agentes "viajante": carro, moto ou pedestre, cada um com perfil de risco (cauteloso/normal/arrojado).
 *  - Agentes "via": trechos de rua. Têm estado (livre, degradado, fechado) separado para cada modal.
 *  - Agentes "zona_risco": os 49 polígonos do mapa oficial. Num cenário, cada polígono do tipo de
 *    evento escolhido é ativado com probabilidade que depende do grau (Médio/Alto/Muito Alto).
 *    As vias a até `buffer_m` metros do polígono são afetadas.
 *  - Eventos: alagamento (lâmina d'água sobe, fica, desce), deslizamento (fecha o trecho),
 *    erosão (degrada ou, com probabilidade, interrompe).
 *  - Informação: o agente só refaz a rota quando (a) VÊ um trecho fechado na rota dentro do raio de
 *    visão ou (b) recebe o aviso da Defesa Civil (fração do nível de informação do cenário).
 *  - Sem rota: espera; esgotada a paciência, volta; quem nunca saiu de casa "desiste"; quem para no
 *    meio do caminho e não consegue voltar fica "preso".
 *
 * Todos os valores marcados HIPÓTESE são pontos de partida, não dados medidos.
 */
model ibirama

global {
	// ================================ ARQUIVOS DE ENTRADA ====================================
	string pasta_dados <- "../includes/dados/";   // no GAMA: copie a pasta dados/ inteira para dentro de includes/ do projeto
	// Rede viária real e pontos críticos ampliados após consulta à Defesa Civil.
	string arquivo_vias <- "vias.shp";
	string arquivo_pontos <- "pontos_criticos.geojson";
	file shape_vias <- shape_file(pasta_dados + arquivo_vias);
	file shape_riscos <- shape_file(pasta_dados + "riscos.shp");
	file shape_pontos <- geojson_file(pasta_dados + arquivo_pontos, "EPSG:4326");
	geometry shape <- envelope(shape_vias);
	// Camadas de fundo (prédios, rios, água, áreas verdes). Só desenho, não afeta a simulação.
	// Troque para true DEPOIS de rodar scripts/02b_baixar_camadas_mapa.py e copiar predios/agua/rios/verde para includes/dados/
	bool usar_camadas_mapa <- false;
	bool usar_fundo_imagem <- file_exists(pasta_dados + "fundo_mapa.png");
	float step <- 10.0 #s;

	// ================================ PARÂMETROS DO CENÁRIO ==================================
	string tipo_evento <- "alagamento";   // nenhum | alagamento | deslizamento | erosao | combinado
	string severidade <- "media";         // baixa | media | alta
	string info_nivel <- "parcial";       // local | parcial | amplo
	// Amostra de ~10% da frota de Ibirama (Senatran, dez/2025): 12.733 carros-equivalentes e 4.203 motos.
	int n_carro <- 1270;
	int n_moto <- 420;
	int n_pedestre <- 250;                // HIPÓTESE (não há contagem oficial de pedestres)
	float fracao_amostra <- 0.10;         // cada agente representa 1/fracao veículos reais (ajusta a capacidade das vias)
	bool od_ponderada <- true;            // true: origens sorteadas com peso pelo tipo de via; false: uniforme
	float janela_partida_min <- 180.0;    // minutos em que as viagens começam
	float inicio_evento_min <- 45.0;
	float atraso_aviso_min <- 10.0;       // demora do aviso oficial após o início do evento
	float horizonte_min <- 480.0;         // duração da simulação (min). Se mudar, ajuste o `until` do batch
	float buffer_m <- 40.0;               // distância polígono-rua para a rua ser afetada
	float raio_visao <- 60.0;             // distância (m) em que o agente vê um trecho fechado à frente
	// Tempos informados pela Defesa Civil de Ibirama (reunião do projeto).
	float duracao_alagamento_min <- 30.0;
	float duracao_deslizamento_min <- 30.0;
	bool rede_energizada <- false;         // true: deslizamento leva entre 60 e 90 min para liberação
	float duracao_desl_energ_min <- 60.0;
	float duracao_desl_energ_max <- 90.0;
	float duracao_erosao_min <- 480.0;     // HIPÓTESE: ainda não informada pela Defesa Civil

	// ================================ HIPÓTESES (calibrar) ===================================
	list<string> MODOS <- ["carro", "moto", "pedestre"];
	list<string> PERFIS <- ["cauteloso", "normal", "arrojado"];
	// Grupos medidos separadamente; "abrigo" permanece NaN até haver um endereço oficial.
	list<string> GRUPOS_ACESSO <- ["hospital", "bombeiros", "defesa_civil", "educacao", "ubs", "abrigo"];
	map<string, float> LIMITE_PROF <- ["carro"::0.30, "moto"::0.20, "pedestre"::0.40];   // m de lâmina d'água
	float FATOR_ARRISCAR <- 1.5;          // arrisca passar se profundidade <= 1,5 x limite
	float VEL_ARRISCAR <- 0.2;            // fração da velocidade ao atravessar trecho perigoso
	map<int, float> BASE_ATIV <- [1::0.25, 2::0.50, 3::0.80];  // prob. de ativar por grau
	map<string, float> SEV <- ["baixa"::0.4, "media"::0.7, "alta"::1.0];
	map<int, point> PROF_PICO <- [1::{0.2, 0.4}, 2::{0.3, 0.7}, 3::{0.5, 1.2}];  // (mín, máx) em m
	// Perfil temporal do alagamento dentro dos 30 min informados: 10 min de subida,
	// 5 min no pico e 15 min de recessão. As frações acompanham o parâmetro de duração.
	float FRAC_RAMPA <- 1.0 / 3.0;
	float FRAC_PLATO <- 1.0 / 6.0;
	float P_COLAPSO <- 0.30;
	map<string, float> BETA <- ["cauteloso"::2.0, "normal"::1.0, "arrojado"::0.3];       // aversão ao risco na rota
	map<string, float> OUSADIA <- ["cauteloso"::0.0, "normal"::0.15, "arrojado"::0.70];  // prob. de aceitar atravessar
	map<string, float> ESPERA_MAX <- ["cauteloso"::3600.0, "normal"::2400.0, "arrojado"::1200.0];  // s
	map<string, list<float>> PERFIL_MODO <- ["carro"::[0.30, 0.55, 0.15], "moto"::[0.15, 0.50, 0.35], "pedestre"::[0.45, 0.45, 0.10]];
	map<string, float> COBERTURA <- ["local"::0.0, "parcial"::0.5, "amplo"::0.9];
	map<string, float> VEL_MODO <- ["carro"::1.0, "moto"::1.1, "pedestre"::1.0];
	map<string, float> VEL_CLASSE_KMH <- ["motorway"::80.0, "trunk"::60.0, "primary"::50.0, "secondary"::50.0, "tertiary"::40.0, "unclassified"::30.0, "residential"::30.0, "living_street"::20.0, "service"::20.0, "track"::20.0];
	// Peso de cada tipo de via para sortear origens (HIPÓTESE: o fluxo se concentra nas vias principais)
	map<string, float> PESO_VIA <- ["motorway"::10.0, "trunk"::10.0, "primary"::8.0, "secondary"::6.0, "tertiary"::4.0, "unclassified"::1.5, "residential"::1.5, "living_street"::1.0, "service"::0.5, "track"::0.2];
	float LENT_MIN <- 0.10;               // a lentidão por fila nunca passa de 10x (HIPÓTESE)
	float VEL_PED <- 1.3;                 // m/s
	float COMP_VEICULO <- 8.0;            // m de via por veículo (capacidade)

	// ================================ ESTADO GLOBAL ==========================================
	int versao <- 0;                      // aumenta sempre que o conjunto de trechos fechados muda
	float t_aviso <- 0.0;
	float cobertura_aviso <- 0.0;
	map<string, graph> cache_grafos <- [];
	map<string, graph> grafos_v0 <- [];   // mapa "sem bloqueios" (quem não sabe de nada usa este)
	list<point> nos_todos <- [];
	list<point> nos_veic <- [];
	list<point> destinos <- [];
	map<point, float> peso_no <- [];      // peso de cada nó da rede (maior peso entre as vias de carro que chegam nele)
	list<float> pesos_origem <- [];       // peso dos nós de nos_veic, na mesma ordem
	bool acesso_medido <- false;
	bool finalizado <- false;
	map<string, float> acesso <- [];

	// ---------------------------------------------------------------- funções de rota ---------
	bool usavel (via v, string m, bool cruza) {
		return !(v.fechada[m]) or (cruza and v.cruzavel[m]);
	}

	float custo (via v, string m, string pf) {
		if (v.fechada[m]) {
			return v.tempo_livre[m] / VEL_ARRISCAR;
		}
		return v.tempo_livre[m] * (1 + BETA[pf] * v.risco);
	}

	graph construir_grafo (string m, string pf, bool cruza) {
		list<via> ok <- via where (usavel(each, m, cruza));
		map<via, float> pesos <- ok as_map (each :: custo(each, m, pf));
		return as_edge_graph(ok) with_weights pesos;
	}

	graph grafo_atual (string m, string pf, bool cruza) {
		string chave <- m + "|" + pf + "|" + string(cruza);
		if (!(cache_grafos contains_key chave)) {
			cache_grafos[chave] <- construir_grafo(m, pf, cruza);
		}
		return cache_grafos[chave];
	}

	// ================================ INICIALIZAÇÃO ==========================================
	init {
		cobertura_aviso <- COBERTURA[info_nivel];
		t_aviso <- (inicio_evento_min + atraso_aviso_min) * 60.0;

		create via from: shape_vias with: [highway::string(read("highway")), veic::int(read("carro"))];
		create zona_risco from: shape_riscos with: [zid::int(read("id")), grau_num::int(read("grau_num")), alaga::int(read("alaga")), eros::int(read("eros")), desl::int(read("desl")), tipo_txt::string(read("tipo_txt"))];
		create ponto_critico from: shape_pontos with: [tipo::string(read("tipo")), grupo::string(read("grupo")), nome::string(read("nome")), precisao::string(read("precisao"))];
		if (usar_camadas_mapa) {
			create verde from: shape_file(pasta_dados + "verde.shp");
			create agua from: shape_file(pasta_dados + "agua.shp");
			create rio from: shape_file(pasta_dados + "rios.shp");
			create predio from: shape_file(pasta_dados + "predios.shp");
		}

		ask zona_risco {
			risco_grau <- (grau_num = 1) ? 0.33 : ((grau_num = 2) ? 0.66 : 1.0);
			nivel_risco <- (grau_num = 1) ? "R2" : ((grau_num = 2) ? "R3" : "R4");
		}
		ask via {
			do iniciar;
		}
		nos_todos <- remove_duplicates(via accumulate [first(each.shape.points), last(each.shape.points)]);

		// grafos "sem bloqueios" (estado inicial = tudo aberto), um por modal e perfil
		loop m over: MODOS {
			loop pf over: PERFIS {
				grafos_v0[m + "|" + pf] <- construir_grafo(m, pf, false);
			}
		}

		// nós de onde um carro consegue chegar ao primeiro ponto crítico (evita origens isoladas)
		point referencia <- (one_of(ponto_critico)).location;
		point no_ref <- nos_todos closest_to referencia;
		loop v over: (via where (each.veic = 1)) {
			point pa <- first(v.shape.points);
			point pb <- last(v.shape.points);
			if (!(peso_no contains_key pa) or peso_no[pa] < v.peso) { peso_no[pa] <- v.peso; }
			if (!(peso_no contains_key pb) or peso_no[pb] < v.peso) { peso_no[pb] <- v.peso; }
		}
		list<point> candidatos <- (min(800, length(nos_todos))) among nos_todos;
		if (od_ponderada) {   // garante que os nós das vias principais (peso >= 4) estejam entre os candidatos
			candidatos <- remove_duplicates(candidatos + (nos_todos where ((peso_no contains_key each) and (peso_no[each] >= 4.0))));
		}
		graph g0 <- grafos_v0["carro|normal"];
		nos_veic <- candidatos where (each = no_ref or (path_between(g0, each, no_ref) != nil));
		ask ponto_critico {
			no_rede <- nos_veic closest_to location;
		}
		pesos_origem <- nos_veic collect ((peso_no contains_key each) ? peso_no[each] : 1.0);
		list<point> destinos_extra <- [];
		if (od_ponderada) {
			loop times: min(20, length(nos_veic)) {
				destinos_extra << nos_veic[rnd_choice(pesos_origem)];
			}
			destinos_extra <- remove_duplicates(destinos_extra);
		} else {
			destinos_extra <- (min(20, length(nos_veic))) among nos_veic;
		}
		list<point> destinos_criticos <- ponto_critico collect each.no_rede;
		destinos <- remove_duplicates(destinos_criticos + destinos_extra);

		// população (criada ANTES de sortear eventos, para ser igual entre cenários com a mesma semente)
		loop m over: MODOS {
			int n <- (m = "carro") ? n_carro : ((m = "moto") ? n_moto : n_pedestre);
			create viajante number: n {
				modo <- m;
				list<float> pesos <- PERFIL_MODO[m];
				perfil <- PERFIS[rnd_choice(pesos)];
				cruza <- flip(OUSADIA[perfil]);
				alvo <- any(destinos);
				if (m = "pedestre") {
					list<point> perto <- nos_todos where (each distance_to alvo < 1500.0 and each distance_to alvo > 100.0);
					origem <- empty(perto) ? any(nos_todos) : any(perto);
				} else {
					origem <- od_ponderada ? nos_veic[rnd_choice(pesos_origem)] : any(nos_veic);
					loop while: origem = alvo {
						origem <- od_ponderada ? nos_veic[rnd_choice(pesos_origem)] : any(nos_veic);
					}
				}
				origem_fixa <- origem;
				location <- origem;
				t_partida <- rnd(janela_partida_min * 60.0);
				u_aviso <- rnd(1.0);
			}
		}

		// eventos
		ask zona_risco {
			do sortear;
		}
		write "Rede: " + length(via) + " trechos | " + length(zona_risco where each.ativa) + " polígonos de risco ativados | evento=" + tipo_evento + " severidade=" + severidade + " info=" + info_nivel;
	}

	// ================================ CICLO GLOBAL ===========================================
	// A cada 5 min simulados: atualiza o estado dos trechos a partir dos eventos.
	reflex atualizar_eventos when: (cycle mod 30 = 0) {
		ask via {
			prof <- 0.0;
			desliz <- false;
			eros_deg <- false;
			eros_col <- false;
		}
		ask zona_risco {
			do aplicar;
		}
		ask via {
			do recalcular;
		}
		bool mudou <- via one_matches (each.codigo != each.codigo_ant);
		if (mudou) {
			ask via {
				codigo_ant <- codigo;
			}
			versao <- versao + 1;
			cache_grafos <- [];
		}
	}

	reflex zerar_ocupacao {
		ask via {
			ocup_ant <- ocup;
			ocup <- 0;
		}
	}

	// Acessibilidade 25 min após o início-base do evento (amostra de nós).
	// Como cada zona pode começar até 20 min depois, este indicador representa uma janela do evento,
	// não um pico simultâneo. Educação reúne escolas, CEIs, IFC e UDESC; UBS reúne UBSs/ESFs.
	reflex medir_acesso when: (!acesso_medido and time >= (inicio_evento_min + 25.0) * 60.0) {
		acesso_medido <- true;
		list<point> amostra <- (min(150, length(nos_veic))) among nos_veic;
		loop tp over: GRUPOS_ACESSO {
			list<ponto_critico> pcs <- ponto_critico where (each.grupo = tp);
			// sem ponto desse tipo (ex.: abrigo ainda não informado): não mede, e o CSV recebe NaN
			loop m over: ["carro", "pedestre"] {
				if (empty(pcs)) { continue; }
				graph g <- grafo_atual(m, "normal", false);
				int sem <- 0;
				loop pt over: amostra {
					bool alcanca <- false;
					loop pc over: pcs {
						if (!alcanca) {
							if (pt = pc.no_rede) {
								alcanca <- true;
							} else {
								path p <- path_between(g, pt, pc.no_rede);
								if (p != nil and !empty(p.edges)) {
									alcanca <- true;
								}
							}
						}
					}
					if (!alcanca) {
						sem <- sem + 1;
					}
				}
				acesso[tp + "|" + m] <- empty(amostra) ? 0.0 : 100.0 * sem / length(amostra);
			}
		}
	}

	// Fim da simulação: grava uma linha no CSV de resultados
	reflex finalizar when: (!finalizado and time >= horizonte_min * 60.0) {
		finalizado <- true;
		string linha <- tipo_evento + "," + severidade + "," + info_nivel + "," + string(rede_energizada)
			+ "," + duracao_alagamento_min + "," + duracao_deslizamento_min + "," + duracao_erosao_min
			+ "," + seed + "," + length(zona_risco where each.ativa);
		loop m over: MODOS {
			list<viajante> s <- viajante where (each.modo = m);
			int n <- length(s);
			list<viajante> c <- s where (each.estado = "concluiu");
			float pc <- n = 0 ? 0.0 : 100.0 * length(c) / n;
			float pv <- n = 0 ? 0.0 : 100.0 * length(s where (each.estado = "voltou")) / n;
			float pd <- n = 0 ? 0.0 : 100.0 * length(s where (each.estado = "desistiu")) / n;
			float pp <- n = 0 ? 0.0 : 100.0 * length(s where (each.estado = "preso")) / n;
			float pe <- n = 0 ? 0.0 : 100.0 * length(s where (each.estado in ["aguardando", "viajando", "espera"])) / n;
			float tm <- empty(c) ? 0.0 : mean(c collect ((each.t_chegada - each.t_partida) / 60.0));
			float dm <- empty(c) ? 0.0 : mean(c collect each.dist);
			int tr <- sum(s collect each.travessias);
			int rp <- sum(s collect each.replan);
			linha <- linha + "," + n + "," + pc + "," + pv + "," + pd + "," + pp + "," + pe + "," + tm + "," + dm + "," + tr + "," + rp;
		}
		// concentração do fluxo (Gini e % das 10 vias mais usadas)
		list<int> ps <- (via collect each.passagens) sort_by each;
		float tot <- sum(ps);
		float gini <- 0.0;
		float top10 <- 0.0;
		if (tot > 0) {
			float soma <- 0.0;
			int nn <- length(ps);
			loop i from: 0 to: nn - 1 {
				soma <- soma + (i + 1) * ps[i];
			}
			gini <- (2 * soma / (nn * tot)) - (nn + 1) / nn;
			top10 <- 100.0 * sum(copy_between(ps, nn - 10, nn)) / tot;
		}
		linha <- linha + "," + gini + "," + top10;
		loop tp over: GRUPOS_ACESSO {
			loop m over: ["carro", "pedestre"] {
				linha <- linha + "," + (acesso contains_key (tp + "|" + m) ? string(acesso[tp + "|" + m]) : "NaN");
			}
		}
		save (linha + "\n") to: "../includes/resultados_gama_dc.csv" format: "text" rewrite: false;
		write "Simulação concluída. Linha gravada em includes/resultados_gama_dc.csv";
	}
}

// ==================================================================================== VIA ====
species via {
	string highway;
	int veic <- 1;                        // 1 = carro/moto podem usar
	float v_livre <- 8.33;                // m/s
	float risco <- 0.0;                   // 0..1, pelo polígono mais grave perto da via
	list<zona_risco> zonas <- [];
	float prof <- 0.0;
	bool desliz <- false;
	bool eros_deg <- false;
	bool eros_col <- false;
	int ocup <- 0;
	int ocup_ant <- 0;
	int passagens <- 0;
	float cap <- 1.0;
	float peso <- 1.0;                    // peso da via para sortear origens (PESO_VIA)
	map<string, bool> fechada <- ["carro"::false, "moto"::false, "pedestre"::false];
	map<string, bool> cruzavel <- ["carro"::false, "moto"::false, "pedestre"::false];
	map<string, float> fator <- ["carro"::1.0, "moto"::1.0, "pedestre"::1.0];
	map<string, float> tempo_livre <- ["carro"::1.0, "moto"::1.0, "pedestre"::1.0];
	int codigo <- 0;
	int codigo_ant <- 0;

	action iniciar {
		float comp <- shape.perimeter;
		v_livre <- ((VEL_CLASSE_KMH contains_key highway) ? VEL_CLASSE_KMH[highway] : 30.0) / 3.6;
		cap <- max(1.0, comp / COMP_VEICULO * fracao_amostra);
		peso <- (PESO_VIA contains_key highway) ? PESO_VIA[highway] : 1.0;
		tempo_livre["carro"] <- comp / v_livre;
		tempo_livre["moto"] <- comp / (v_livre * VEL_MODO["moto"]);
		tempo_livre["pedestre"] <- comp / VEL_PED;
		geometry area <- shape + buffer_m;
		zonas <- zona_risco where (each.shape intersects area);
		risco <- empty(zonas) ? 0.0 : max(zonas collect each.risco_grau);
		do recalcular;
		codigo_ant <- codigo;
	}

	// Estado da via para cada modal, a partir de lâmina d'água, deslizamento e erosão
	action recalcular {
		loop m over: MODOS {
			float lim <- LIMITE_PROF[m];
			bool veiculo <- (m != "pedestre");
			bool bloq <- (veiculo and veic = 0) or desliz or eros_col or (prof > lim);
			bool cruz <- false;
			float f <- 0.0;
			if (bloq) {
				cruz <- true;
				if (veiculo and veic = 0) { cruz <- false; }
				if (prof > lim and prof > FATOR_ARRISCAR * lim) { cruz <- false; }
				if (veiculo and (desliz or eros_col)) { cruz <- false; }
			} else {
				f <- 1.0 - 0.7 * prof / lim;
				if (eros_deg) { f <- f * (veiculo ? 0.5 : 0.8); }
			}
			fechada[m] <- bloq;
			cruzavel[m] <- cruz;
			fator[m] <- f;
		}
		codigo <- (fechada["carro"] ? 1 : 0) + (fechada["moto"] ? 2 : 0) + (fechada["pedestre"] ? 4 : 0)
			+ (cruzavel["carro"] ? 8 : 0) + (cruzavel["moto"] ? 16 : 0) + (cruzavel["pedestre"] ? 32 : 0);
	}

	aspect default {
		rgb cor <- rgb(70, 70, 70);
		float larg <- (highway in ["primary", "secondary", "trunk"]) ? 3.5 : ((highway = "tertiary") ? 2.5 : 1.8);
		if (risco > 0) { cor <- rgb(232, 130, 0); }
		if (prof > 0) { cor <- #deepskyblue; larg <- larg + 1.0; }
		if (fechada["carro"] and veic = 1) { cor <- #red; larg <- larg + 1.5; }
		draw shape color: rgb(255, 255, 255, 190) width: larg + 1.6;   // contorno claro: destaca a rua sobre o mapa de fundo
		draw shape color: cor width: larg;
	}
}

// ========================================================================== ZONA DE RISCO ====
species zona_risco {
	int zid;
	int grau_num;
	string nivel_risco;                  // R2=Médio, R3=Alto, R4=Muito Alto; a camada não contém R1
	int alaga;
	int eros;
	int desl;
	string tipo_txt;
	float risco_grau <- 0.0;
	bool ativa <- false;                    // recebeu algum evento no sorteio desta execução
	bool em_curso <- false;                // evento efetivamente vigente no instante atual
	bool a_alaga <- false;
	bool a_desl <- false;
	bool a_eros <- false;
	bool colapso <- false;
	float t_alaga <- 0.0;
	float pico <- 0.0;
	float t_desl <- 0.0;
	float dur_desl_s <- 0.0;
	float t_eros <- 0.0;
	float dur_eros_s <- 0.0;
	list<via> trechos <- [];

	// Sorteia se cada família de evento deste polígono ocorre neste cenário
	action sortear {
		trechos <- via where (each.zonas contains self);
		float p <- min(1.0, BASE_ATIV[grau_num] * SEV[severidade]);
		float t0 <- inicio_evento_min * 60.0;
		bool quer_alaga <- (tipo_evento = "alagamento" or tipo_evento = "combinado") and alaga = 1;
		bool quer_desl <- (tipo_evento = "deslizamento" or tipo_evento = "combinado") and desl = 1;
		bool quer_eros <- (tipo_evento = "erosao" or tipo_evento = "combinado") and eros = 1;
		if (quer_alaga and flip(p)) {
			a_alaga <- true;
			t_alaga <- t0 + rnd(1200.0);
			point faixa <- PROF_PICO[grau_num];
			pico <- faixa.x + rnd(faixa.y - faixa.x);
		}
		if (quer_desl and flip(p)) {
			a_desl <- true;
			t_desl <- t0 + rnd(1200.0);
			// A Defesa Civil informou 30 min sem rede energizada e 60-90 min com rede.
			dur_desl_s <- rede_energizada
				? (duracao_desl_energ_min + rnd(duracao_desl_energ_max - duracao_desl_energ_min)) * 60.0
				: duracao_deslizamento_min * 60.0;
		}
		if (quer_eros and flip(p)) {
			a_eros <- true;
			t_eros <- t0 + rnd(1200.0);
			dur_eros_s <- duracao_erosao_min * 60.0;
			colapso <- flip(P_COLAPSO);
		}
		ativa <- a_alaga or a_desl or a_eros;
	}

	float profundidade (float t) {
		if (!a_alaga or t < t_alaga) { return 0.0; }
		float dur <- duracao_alagamento_min * 60.0;
		float rampa <- dur * FRAC_RAMPA;
		float plato <- dur * FRAC_PLATO;
		float recesso <- dur - rampa - plato;
		float dt <- t - t_alaga;
		if (dt < rampa) { return pico * dt / rampa; }
		if (dt < rampa + plato) { return pico; }
		if (dt < dur) { return pico * (1.0 - (dt - rampa - plato) / recesso); }
		return 0.0;
	}

	// Empurra o estado atual deste polígono para as vias dele; encerrado o tempo informado,
	// a limpeza do estado global permite que as vias sejam reabertas automaticamente.
	action aplicar {
		if (ativa) {
			float h <- profundidade(time);
			bool d <- a_desl and time >= t_desl and time < t_desl + dur_desl_s;
			bool eros_ativa <- a_eros and time >= t_eros and time < t_eros + dur_eros_s;
			bool ed <- eros_ativa and !colapso;
			bool ec <- eros_ativa and colapso;
			em_curso <- h > 0.0 or d or ed or ec;
			if (em_curso) {
				ask trechos {
					if (h > prof) { prof <- h; }
					if (d) { desliz <- true; }
					if (ed) { eros_deg <- true; }
					if (ec) { eros_col <- true; }
				}
			}
		}
	}

	aspect default {
		rgb cor <- grau_num = 3 ? rgb(230, 81, 0, 80) : rgb(255, 193, 7, 80);
		if (em_curso) { cor <- rgb(200, 0, 0, 120); }
		draw shape color: cor border: #black;
	}
}

// ============================================================ CAMADAS DE FUNDO (só desenho) ====
species verde {
	aspect default {
		draw shape color: rgb(196, 222, 176);
	}
}

species agua {
	aspect default {
		draw shape color: rgb(158, 207, 235);
	}
}

species rio {
	aspect default {
		draw shape color: rgb(120, 187, 226) width: 3.0;
	}
}

species predio {
	aspect default {
		draw shape color: rgb(222, 218, 210) border: rgb(186, 181, 172);
	}
}

// ==================================================================== PONTO CRÍTICO ==========
species ponto_critico {
	string tipo;
	string grupo;
	string nome;
	string precisao;
	point no_rede;
	aspect default {
		rgb cor_ponto <- (grupo = "hospital") ? #red
			: ((grupo = "bombeiros") ? #orangered
			: ((grupo = "defesa_civil") ? #purple
			: ((grupo = "ubs") ? #magenta : #green)));
		draw triangle(120) color: cor_ponto border: #black;
	}
}

// ======================================================================== VIAJANTE ===========
species viajante skills: [moving] {
	string modo;
	string perfil;
	int variante <- rnd(0, 11);           // só para variar a cor do ícone (carro/moto/pedestre)
	bool cruza <- false;                  // aceita atravessar trecho perigoso
	point origem;
	point origem_fixa;
	point alvo;
	float t_partida <- 0.0;
	float u_aviso <- 0.0;
	string estado <- "aguardando";        // aguardando | viajando | espera | concluiu | voltou | desistiu | preso
	bool voltando <- false;
	bool vigilante <- false;              // já descobriu que há bloqueios: mantém o mapa atualizado
	int conhecido <- 0;                   // versão do mapa de bloqueios que o agente conhece
	graph meu_grafo;
	list<via> rota <- [];
	bool refazer <- true;
	float t_espera <- 0.0;
	float t_chegada <- 0.0;
	float dist <- 0.0;
	int travessias <- 0;
	int replan <- 0;
	via via_anterior <- nil;

	reflex agir when: (estado in ["aguardando", "viajando", "espera"]) {
		if (estado = "aguardando") {
			if (time >= t_partida) {
				estado <- "viajando";
				meu_grafo <- grafos_v0[modo + "|" + perfil];
				do atualizar_conhecimento;
				do planejar;
			}
		} else {
			do atualizar_conhecimento;
			if (estado = "viajando") {
				do perceber;
			}
			if (estado = "espera") {
				do esperar;
			} else if (estado = "viajando") {
				do andar;
			}
		}
	}

	// Pede ao mundo (global) o grafo do mapa de bloqueios atual para este agente.
	// (funções do global não podem ser chamadas direto de dentro de uma species)
	action pegar_grafo_atual {
		ask world {
			myself.meu_grafo <- grafo_atual(myself.modo, myself.perfil, myself.cruza);
		}
	}

	// Aviso oficial (ou conhecimento prévio): passa a usar o mapa de bloqueios atual
	action atualizar_conhecimento {
		bool alerta <- (time >= t_aviso) and (u_aviso < cobertura_aviso);
		if ((alerta or vigilante) and conhecido != versao) {
			conhecido <- versao;
			do pegar_grafo_atual;
			if (estado = "viajando") {
				do planejar;
			}
		}
	}

	// Vê trecho fechado na própria rota, dentro do raio de visão: descobre e refaz a rota
	action perceber {
		if (!vigilante and !empty(rota)) {
			list<via> fechadas <- rota where (each.fechada[modo] and !(cruza and each.cruzavel[modo]));
			if (!empty(fechadas)) {
				via prox <- fechadas closest_to location;
				if (prox distance_to location <= raio_visao) {
					vigilante <- true;
					replan <- replan + 1;
					conhecido <- versao;
					do pegar_grafo_atual;
					do planejar;
				}
			}
		}
	}

	action planejar {
		path p <- path_between(meu_grafo, location, alvo);
		if (p = nil or empty(p.edges)) {
			if (location distance_to alvo < 5.0) {
				do chegar;
			} else {
				estado <- "espera";
				rota <- [];
			}
		} else {
			rota <- list<via>(p.edges);
			refazer <- true;
			if (estado = "espera") {
				estado <- "viajando";
			}
		}
	}

	// Sem rota possível: espera; depois volta; se nem isso, desiste (nunca saiu) ou fica preso
	action esperar {
		vigilante <- true;
		t_espera <- t_espera + step;
		do atualizar_conhecimento;
		if (cycle mod 30 = 0) {
			do planejar;
		}
		if (estado = "espera" and t_espera > ESPERA_MAX[perfil]) {
			if (!voltando and location distance_to origem_fixa > 30.0) {
				voltando <- true;
				alvo <- origem_fixa;
				t_espera <- 0.0;
				do planejar;
			} else {
				estado <- (dist = 0.0) ? "desistiu" : "preso";
				t_chegada <- time;
			}
		}
	}

	action andar {
		via v <- (current_edge != nil) ? via(current_edge) : (via closest_to location);
		bool fechado <- v.fechada[modo];
		float f <- fechado ? VEL_ARRISCAR : v.fator[modo];
		float vel <- 0.0;
		if (modo = "pedestre") {
			vel <- VEL_PED * f;
		} else {
			float r <- v.ocup_ant / v.cap;
			float expo <- (modo = "moto") ? 0.5 : 1.0;   // moto sofre menos com fila (HIPÓTESE)
			vel <- v.v_livre * VEL_MODO[modo] * f * max(LENT_MIN, 1.0 / (1 + expo * 0.15 * (r ^ 4)));
			ask v {
				ocup <- ocup + 1;
			}
		}
		if (v != via_anterior) {
			if (fechado) { travessias <- travessias + 1; }
			if (modo != "pedestre") {
				ask v {
					passagens <- passagens + 1;
				}
			}
			via_anterior <- v;
		}
		vel <- max(vel, 0.05);
		point p0 <- location;
		do goto target: alvo on: meu_grafo speed: vel recompute_path: refazer;
		refazer <- false;
		dist <- dist + (p0 distance_to location);
		if (location distance_to alvo < 5.0) {
			do chegar;
		}
	}

	action chegar {
		estado <- voltando ? "voltou" : "concluiu";
		t_chegada <- time;
	}

	aspect default {
		// Ícones exagerados (o mapa tem ~6 km de largura), girados conforme a direção do movimento.
		// Halo vermelho = parado, esperando uma rota livre.
		if (estado in ["viajando", "espera"]) {
			if (estado = "espera") {
				draw circle(26) color: rgb(255, 0, 0, 70) border: #red;
			}
			if (modo = "carro") {
				draw image_file(pasta_dados + "icones/carro_" + string((variante mod 6) + 1) + ".png") size: {44, 20} rotate: heading;
			} else if (modo = "moto") {
				draw image_file(pasta_dados + "icones/moto_" + string((variante mod 4) + 1) + ".png") size: {38, 14} rotate: heading;
			} else {
				draw image_file(pasta_dados + "icones/pedestre_" + string((variante mod 4) + 1) + ".png") size: {22, 22};
			}
		}
	}
}

// ================================================================================ EXPERIMENTOS ====
// 1) Interativo: abre o mapa, permite mudar os parâmetros e ver os gráficos.
experiment Interativo type: gui {
	parameter "Tipo de evento" var: tipo_evento <- "alagamento" among: ["nenhum", "alagamento", "deslizamento", "erosao", "combinado"] category: "Cenário";
	parameter "Severidade" var: severidade <- "media" among: ["baixa", "media", "alta"] category: "Cenário";
	parameter "Nível de informação" var: info_nivel <- "parcial" among: ["local", "parcial", "amplo"] category: "Cenário";
	parameter "Carros" var: n_carro <- 1270 min: 0 max: 3000 category: "População";
	parameter "Motos" var: n_moto <- 420 min: 0 max: 3000 category: "População";
	parameter "Pedestres" var: n_pedestre <- 250 min: 0 max: 3000 category: "População";
	parameter "Fração da frota simulada" var: fracao_amostra <- 0.10 min: 0.01 max: 1.0 category: "População";
	parameter "Origens ponderadas por tipo de via" var: od_ponderada <- true category: "População";
	parameter "Janela de partida (min)" var: janela_partida_min <- 180.0 min: 10.0 max: 480.0 category: "População";
	parameter "Início do evento (min)" var: inicio_evento_min <- 45.0 min: 0.0 max: 300.0 category: "Evento";
	parameter "Duração do alagamento (min)" var: duracao_alagamento_min <- 30.0 min: 5.0 max: 240.0 category: "Evento";
	parameter "Duração do deslizamento (min)" var: duracao_deslizamento_min <- 30.0 min: 5.0 max: 240.0 category: "Evento";
	parameter "Há rede energizada" var: rede_energizada <- false category: "Evento";
	parameter "Duração da erosão (min, hipótese)" var: duracao_erosao_min <- 480.0 min: 5.0 max: 480.0 category: "Evento";
	parameter "Raio de visão (m)" var: raio_visao <- 60.0 min: 10.0 max: 300.0 category: "Agentes";

	output {
		display "Mapa" background: rgb(232, 240, 222) {
			graphics "fundo" refresh: false {
				if (usar_fundo_imagem) {
					draw image_file(pasta_dados + "fundo_mapa.png") at: world.location size: {world.shape.width, world.shape.height};
				}
			}
			species verde refresh: false;
			species agua refresh: false;
			species rio refresh: false;
			species predio refresh: false;
			species via;
			species zona_risco;
			species ponto_critico;
			species viajante;
			overlay position: {5, 5} size: {250 #px, 215 #px} background: #black transparency: 0.35 border: #black rounded: true {
				int h <- int(time / 3600);
				int mi <- (int(time) mod 3600) div 60;
				draw "Tempo simulado: " + h + " h " + mi + " min" at: {10 #px, 20 #px} color: #white font: font("SansSerif", 12, #bold);
				draw "Em viagem: " + (viajante count (each.estado = "viajando")) at: {10 #px, 40 #px} color: #white font: font("SansSerif", 11, #plain);
				draw "Concluíram: " + (viajante count (each.estado = "concluiu")) at: {10 #px, 58 #px} color: #white font: font("SansSerif", 11, #plain);
				draw rectangle(22 #px, 10 #px) at: {24 #px, 83 #px} color: rgb(30, 100, 220) border: #white;
				draw "Carro" at: {44 #px, 87 #px} color: #white font: font("SansSerif", 11, #plain);
				draw rectangle(22 #px, 6 #px) at: {24 #px, 101 #px} color: #magenta border: #white;
				draw "Moto" at: {44 #px, 105 #px} color: #white font: font("SansSerif", 11, #plain);
				draw circle(5 #px) at: {24 #px, 119 #px} color: rgb(30, 170, 60) border: #white;
				draw "Pedestre" at: {44 #px, 123 #px} color: #white font: font("SansSerif", 11, #plain);
				draw line([{14 #px, 138 #px}, {34 #px, 138 #px}]) color: rgb(232, 130, 0) width: 3;
				draw "Rua em área de risco" at: {44 #px, 142 #px} color: #white font: font("SansSerif", 11, #plain);
				draw line([{14 #px, 156 #px}, {34 #px, 156 #px}]) color: #deepskyblue width: 3;
				draw "Rua alagada" at: {44 #px, 160 #px} color: #white font: font("SansSerif", 11, #plain);
				draw line([{14 #px, 174 #px}, {34 #px, 174 #px}]) color: #red width: 3;
				draw "Rua fechada (carro)" at: {44 #px, 178 #px} color: #white font: font("SansSerif", 11, #plain);
				draw "Halo vermelho = parado esperando rota" at: {10 #px, 200 #px} color: #lightgray font: font("SansSerif", 10, #plain);
			}
		}
		display "Desfechos" refresh: every(10 #cycles) {
			chart "Situação dos agentes" type: series {
				data "Em viagem" value: viajante count (each.estado = "viajando") color: #blue;
				data "Esperando rota" value: viajante count (each.estado = "espera") color: #black;
				data "Concluíram" value: viajante count (each.estado = "concluiu") color: #green;
				data "Voltaram" value: viajante count (each.estado = "voltou") color: #orange;
				data "Desistiram" value: viajante count (each.estado = "desistiu") color: #gray;
				data "Presos" value: viajante count (each.estado = "preso") color: #red;
			}
		}
		monitor "Trechos fechados (carro)" value: via count (each.fechada["carro"] and each.veic = 1);
		monitor "Eventos em curso" value: zona_risco count each.em_curso;
	}
}

// 2) Em lote: todos os cenários x repetições; grava em includes/resultados_gama_dc.csv (uma linha por execução).
//    Se mudar `horizonte_min`, mude também o número abaixo (480 min = 28800 s).
experiment Lote type: batch repeat: 10 keep_seed: true until: (time >= 28800.0) {
	parameter "Tipo de evento" var: tipo_evento among: ["nenhum", "alagamento", "deslizamento", "erosao", "combinado"];
	parameter "Severidade" var: severidade among: ["baixa", "media", "alta"];
	parameter "Nível de informação" var: info_nivel among: ["local", "parcial", "amplo"];
	parameter "Rede energizada" var: rede_energizada among: [false, true];
}
