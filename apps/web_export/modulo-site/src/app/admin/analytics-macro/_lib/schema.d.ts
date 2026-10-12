// GERADO por apps/web_export (F-W001) de packages/shared/schemas/web_views.py.
// NAO EDITE A MAO: o contrato e o modelo pydantic; este arquivo e derivado dele.
// tag: dev-2026-10-11
// DATASET_SHA256: fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef
//
// Mapa arquivo -> interface:
//   catalogo.json -> CatalogoView
//   current.json -> PonteiroCurrent
//   heatmap_regime_ativo.json -> HeatmapView
//   internacional.json -> InternacionalView
//   meta.json -> MetaWeb
//   ranking_atual.json -> RankingAtualView
//   regimes_timeline.json -> TimelineView
//   vizinhos.json -> VizinhosView
//
// Todo campo nullable e `| null`, nunca ausente: ausencia e erro de contrato, e o
// exportador reprova a view antes de gravar (extra=forbid + campo obrigatorio).

/** O bloco `agregado` do `MANIFEST.json`, copiado sem recálculo. */
export interface AgregadoDoDataset {
  sha256: string;
  n_artefatos: number;
  n_artefatos_fora_do_agregado: number;
  bytes: number;
  linhas: number;
}

/** Um artefato `publicavel: true` do `MANIFEST.json`, com o perfil de CA-118. */
export interface ArtefatoPublicado {
  arquivo: string;
  linhas: number | null;
  colunas: number | null;
  bytes: number | null;
  sha256: string | null;
  date_min: string | null;
  date_max: string | null;
  pct_nulos: number | null;
  determinista: boolean;
}

/** O que `asset_id` determina: o grupo, a linha na ordem **declarada** e a janela própria. */
export interface AtivoDoHeatmap {
  asset_id: string;
  grupo: string;
  linha: number;
  data_inicio_serie: string | null;
}

/** `corr(USDBRL, IBOV)` num bloco — **sempre** com o `n` de pares (RF-W031). */
export interface BlocoDeCorrelacao {
  bloco: string;
  corr: number | null;
  n_pares: number | null;
}

/** T-07 — de onde veio cada número, o que ele não sustenta e o que não foi decidido. */
export interface CatalogoView {
  /** O nome do arquivo sem extensão. */
  view: string;
  /** A tela do PRD §4 que consome esta view (T-01..T-07). */
  tela: string;
  /** A frase de abertura da tela (P7 / RF-W035). */
  pergunta: string;
  tag: string;
  dataset_sha256: string;
  gate: GateDaView;
  /** Artefatos do MANIFEST.json lidos para montar esta view. */
  fontes: string[];
  series: SerieDoCatalogo[];
  cobertura: CoberturaDoCatalogo;
  artefatos: ArtefatoPublicado[];
  artefatos_nao_publicaveis: OmissaoDoGate[];
  limitacoes: LimitacaoChave[];
  decisoes_pendentes: DecisaoPendente[];
  adrs: StatusDeAdr[];
  reducoes: ReducaoDeclarada[];
}

/** Uma célula do mapa de calor, **como plotada** — com `n` no corpo, nunca só no tooltip. A célula não repete o que a chave já determina: `(vista, regime)` dá lente, materialização, horizonte, tabela de origem e coluna (em `HeatmapView.eixos`), e `asset_id` dá grupo, linha e `data_inicio_serie` (em `HeatmapView.ativos`). É **normalização**, não agregação: nenhum valor é combinado com outro, e o exportador reprova se a dependência funcional não valer no Parquet. */
export interface CelulaDoHeatmap {
  vista: string;
  regime: string;
  asset_id: string;
  n_obs: number;
  excesso_cdi: number | null;
  ret_medio: number | null;
  ret_mediana: number | null;
  erro_padrao_media: number | null;
  hit_ratio_cdi: number | null;
  pior_tri: number | null;
  pior_tri_quarter: string | null;
  alerta_n_baixo: boolean;
  conclusao_suprimida: boolean;
  /** Canal SEM cor da supressao (CA-109). Nao e paleta: e o segundo canal. */
  hachura: string | null;
}

/** Uma célula de `internacional_por_regime` — retorno **em BRL**, importado de F-022. */
export interface CelulaInternacional {
  lente: string;
  regime: string;
  asset_id: string;
  n_obs: number;
  ret_medio: number | null;
  ret_mediana: number | null;
  excesso_cdi: number | null;
  ret_real: number | null;
  hit_ratio_cdi: number | null;
  corr_ibov: number | null;
  n_pares_ibov: number | null;
  corr_imab: number | null;
  n_pares_imab: number | null;
  is_total_return: boolean | null;
  alerta_n_baixo: boolean;
  conclusao_suprimida: boolean;
}

/** Quantas séries existem, quantas chegaram e quantas cobrem 1T2006. */
export interface CoberturaDoCatalogo {
  n_series: number;
  n_presentes: number;
  n_cobrem_1t2006: number;
}

/** O bloco `congelamento` do `MANIFEST.json` + se o `FROZEN.txt` existe em disco. */
export interface CongelamentoDoDataset {
  tag: string | null;
  git_commit: string | null;
  git_ref: string | null;
  frozen_txt_presente: boolean;
  /** True só com MANIFEST.congelamento E FROZEN.txt em disco. */
  dataset_congelado: boolean;
}

/** A data **do dado**, nunca a do relógio (`run.py:data_do_dado`). */
export interface DataDoDado {
  date_min_raw_series: string | null;
  date_max_raw_series: string | null;
  vintage_max: string | null;
  primeiro_trimestre_macro: string | null;
  ultimo_trimestre_macro: string | null;
}

/** Uma das 12 decisões da §7 de `LIMITACOES-COMITE.md`, com o custo de discordar. */
export interface DecisaoPendente {
  id: string;
  decisao: string;
  padrao_provisorio: string;
  se_discordar: string;
}

/** 19/19/16/13 + 16 indeterminados — ausência **rotulada**, nunca uma 5ª cor (P10). */
export interface DistribuicaoDeRegimes {
  por_grupo: Record<string, number>;
  n_indeterminados: number;
  quarters_indeterminados: string[];
  desbalanceamento: number | null;
}

/** As 22 trocas de rótulo `asof` × `revised` em 66 comparáveis — 33,33% (RF-W029). */
export interface DivergenciaDeMaterializacao {
  n_divergencias: number;
  n_comparaveis: number;
  pct: number | null;
  limiar_pct: number | null;
  acima_do_limiar: boolean | null;
  quarters: string[];
}

/** O **eixo** da escala divergente de uma vista: ±`extremo_simetrico`, por campo pintável. **É eixo, não estatística.** Nenhum valor é combinado com outro: `extremo_simetrico` é o `max(|valor|)` da vista **inteira**, que é a extensão do eixo de cor — o mesmo papel do `ylim` de um gráfico. Não é um achado sobre o dado, não vai a texto do relatório e não entra em nenhuma conclusão; serve para que `-x` e `+x` caiam no mesmo passo e o neutro do meio signifique "empatou" (ADR-002 §3: simetria obrigatória). **Por que vem do exportador, e por vista.** A extensão é sobre a vista inteira, nunca sobre o recorte filtrado: se dependesse do filtro, marcar uma classe de ativo repintaria as outras e duas leituras da mesma tag deixariam de ser comparáveis. Calculá-la no front obrigava a tela a varrer as células a cada requisição e deixava o valor dependente de quem varre; declarada aqui, é a mesma para a figura do PDF, para a tela e para qualquer outro consumidor. Em unidade **nativa** (D-W4): quem apresenta multiplica pelo `meta.fator_de_apresentacao`. */
export interface EixoDeCorDaVista {
  vista: string;
  campo: string;
  /** max(|valor|) da vista inteira, unidade nativa. null = nenhum valor na vista. */
  extremo_simetrico: number | null;
  limite_inferior: number | null;
  limite_superior: number | null;
  n_celulas_com_valor: number;
  n_celulas: number;
}

/** O que `(vista, regime)` determina: a coluna da grade e de que tabela a célula saiu. */
export interface EixoDoHeatmap {
  vista: string;
  regime: string;
  tabela: string;
  lente: string;
  materializacao: string;
  horizonte: string;
  coluna: number;
}

/** O que um rótulo de faixa determina — `INDETERMINADO` é hachura, nunca uma 5ª cor (P10). **Sem cor** (D-ai): o rótulo e a hachura são semântica do regime, que é do pipeline; o hex é decisão de apresentação, que é de quem desenha. Ver `CelulaDoHeatmap`. */
export interface EstiloDaFaixa {
  regime_v1: string | null;
  status_regime_v1: string;
  hachura: string | null;
}

/** O que foi retirado da figura e por quê — a linha segue nas tabelas (Anti-SPEC §10.2.12). */
export interface ExclusaoDaFigura {
  asset_id: string;
  motivo: string;
}

/** A faixa de D6 — **faixa**, nunca ponto (CA-107 / RF-W032). */
export interface FaixaDeD6 {
  ativo_representativo: string;
  piso_estrutural_min: number | null;
  piso_estrutural_max: number | null;
  banda_tatica_min: number | null;
  banda_tatica_max: number | null;
  cap_usado: number | null;
  forma: string;
  distincao_obrigatoria: string;
  decisao: string;
}

/** O estado do gate de publicação, lido do **ADR-001 em disco**, em toda view (RF-W002). */
export interface GateDaView {
  /** False enquanto o ADR-001 não estiver ACEITA em disco (CA-090). */
  especificacao_congelada: boolean;
  /** PROPOSTA | ACEITA | DESCONHECIDO — falha fechada. */
  status_adr_001: string;
  /** O texto de AGENTS.md §9 por escrito. */
  veredito_publicacao: string;
  /** A faixa fixa do topo de toda tela. Vazia quando congelada. */
  marca: string;
  /** Espelha especificacao_congelada — nunca um terceiro valor. */
  publicavel: boolean;
}

/** T-02 — as **322** células das **3** vistas (115 + 92 + 115), com `n`, erro-padrão e as 2 flags por célula, mais o eixo de cor de cada vista. `v1_revised` e `horizonte_cruzado` têm 115 células (23 ativos × 5 colunas) e `v1_asof` tem 92 (a V3 não tem materialização `asof`, então falta a coluna de vizinhos) — medido na tag, não suposto. */
export interface HeatmapView {
  /** O nome do arquivo sem extensão. */
  view: string;
  /** A tela do PRD §4 que consome esta view (T-01..T-07). */
  tela: string;
  /** A frase de abertura da tela (P7 / RF-W035). */
  pergunta: string;
  tag: string;
  dataset_sha256: string;
  gate: GateDaView;
  /** Artefatos do MANIFEST.json lidos para montar esta view. */
  fontes: string[];
  celulas: CelulaDoHeatmap[];
  eixos: EixoDoHeatmap[];
  eixos_de_cor: EixoDeCorDaVista[];
  ativos: AtivoDoHeatmap[];
  vistas: string[];
  regimes: string[];
  grupos: string[];
  limiares_de_n: LimiaresDeN;
  excluidos_da_figura: ExclusaoDaFigura[];
  /** Divergente SIMÉTRICA em ±extremo — assimétrica é proibida. */
  escala: string;
  metrica_padrao: string;
}

/** Uma entrada do índice de views — com `sha256` e bytes, para RF-W012 ser verificável. */
export interface IndiceDaView {
  arquivo: string;
  view: string;
  tela: string;
  /** O slot em docs/research/ldc-analytics-arquitetura.md §1.1. */
  slot_arquitetura: string;
  bytes: number;
  sha256: string;
  /** Linhas do payload principal da view. */
  n_registros: number;
}

/** T-06 — o internacional em BRL por regime, as correlações e a faixa. **Sem** variância mínima. */
export interface InternacionalView {
  /** O nome do arquivo sem extensão. */
  view: string;
  /** A tela do PRD §4 que consome esta view (T-01..T-07). */
  tela: string;
  /** A frase de abertura da tela (P7 / RF-W035). */
  pergunta: string;
  tag: string;
  dataset_sha256: string;
  gate: GateDaView;
  /** Artefatos do MANIFEST.json lidos para montar esta view. */
  fontes: string[];
  celulas: CelulaInternacional[];
  lentes: string[];
  assets: string[];
  correlacoes: BlocoDeCorrelacao[];
  faixa_d6: FaixaDeD6;
  regra_de_stress: RegraDeStress;
  dez_piores_do_ibov: PiorTrimestreDoIbov[];
  omitido_pelo_gate: OmissaoDoGate[];
  proxies_indisponiveis: string[];
}

/** A lente exportada, declarada campo a campo — o que muda a resposta está na linha. */
export interface LenteDosVizinhos {
  metrica: string;
  somente_passado: boolean;
  restrito_pos_2016: boolean;
  janela_padronizacao: string;
  shrinkage: string | null;
  n_features: number;
  features_usadas: string;
}

/** Os dois limiares de `n`, lidos de `regimes_v1`, nunca digitados na tela. */
export interface LimiaresDeN {
  alerta_abaixo_de: number;
  supressao_abaixo_de: number;
  legenda: Record<string, string>;
}

/** Uma das 10 limitações, com o número medido que a abre (RF-W034). */
export interface LimitacaoChave {
  numero: number;
  texto: string;
}

/** Uma linha de `concordancia_lentes.parquet` — Jaccard, Spearman e a distribuição. */
export interface LinhaDeConcordancia {
  secao: string;
  chave: string;
  metrica: string;
  valor_num: number | null;
  valor_texto: string | null;
}

/** Uma linha do ranking de ativos de uma lente. `n` e as 2 flags em **toda** linha. */
export interface LinhaDeRanking {
  lente_rotulo: string;
  lente: string;
  regime: string;
  asset_id: string;
  posicao: number;
  n_obs: number;
  excesso_cdi: number | null;
  ret_medio: number | null;
  ret_mediana: number | null;
  hit_ratio_cdi: number | null;
  erro_padrao_media: number | null;
  excesso_em_erros_padrao: number | null;
  distinguivel_de_ruido: boolean | null;
  alerta_n_baixo: boolean;
  conclusao_suprimida: boolean;
}

/** Uma linha do ranking medido em **T+1** dos vizinhos, com barra de erro (RF-W027). */
export interface LinhaDoRankingT1 {
  asset_id: string;
  n_obs: number;
  excesso_cdi: number | null;
  ret_medio: number | null;
  ret_mediana: number | null;
  erro_padrao_media: number | null;
  hit_ratio_cdi: number | null;
  alerta_n_baixo: boolean;
  conclusao_suprimida: boolean;
}

/** O que não depende da materialização: fim do trimestre, IBOV (índice) e Selic (% a.a.). */
export interface MercadoDoQuarter {
  quarter_end: string | null;
  ibov_nivel: number | null;
  selic_meta_pct: number | null;
}

/** `meta.json` — o manifesto da tag. **Nenhum campo vem do relógio** (CA-121). */
export interface MetaWeb {
  schema_versao: number;
  feature: string;
  tag: string;
  dataset_sha256: string;
  dataset_sha256_curto: string;
  agregado: AgregadoDoDataset;
  data_do_dado: DataDoDado;
  congelamento: CongelamentoDoDataset;
  /** `versao_build` por relatorio_*.json — a etapa do pipeline que gerou o dado. */
  versao_build: Record<string, string>;
  /** sha256 dos módulos deste exportador. */
  web_export_versao_build: string;
  gate: GateDaView;
  views: IndiceDaView[];
  contagens: Record<string, number>;
  limitacoes: LimitacaoChave[];
  n_decisoes_pendentes: number;
  unidade_por_campo: Record<string, string>;
  casas_por_unidade: Record<string, number>;
  /** campo -> unidade na TELA. O JSON continua na nativa: aqui só a instrução. */
  unidade_de_apresentacao: Record<string, string>;
  /** campo -> fator (fracao->percentual = 100). O unico numero da conversao. */
  fator_de_apresentacao: Record<string, number>;
  /** campo -> casas na tela. 4 casas em fracao sao 2 casas em percentual. */
  casas_de_apresentacao: Record<string, number>;
  reducoes: ReducaoDeclarada[];
  orcamento: OrcamentoDoConjunto;
  /** Nome dos artefatos com publicavel:false. Nenhum valor deles é lido ou emitido. */
  artefatos_nao_publicaveis: string[];
  politica_de_cache: Record<string, string>;
}

/** O que o gate cortou desta view, com o nome do artefato e o motivo do `MANIFEST.json`. */
export interface OmissaoDoGate {
  artefato: string;
  motivo: string;
}

/** RNF-W001 medido, não estimado. */
export interface OrcamentoDoConjunto {
  limite_bytes: number;
  bytes_das_views: number;
  ok: boolean;
  arquivos_contados: number;
}

/** Um dos 10 piores trimestres do IBOV, com a variação do dólar e a flag de stress. */
export interface PiorTrimestreDoIbov {
  quarter: string;
  ret_ibov: number | null;
  ret_usdbrl: number | null;
  stress_flag: boolean;
}

/** `current.json` — o **único** arquivo com `no-cache`, no diretório pai da tag (RF-W011). */
export interface PonteiroCurrent {
  tag: string;
  dataset_sha256: string;
  /** Caminho relativo do meta.json da tag. */
  meta: string;
  /** view -> caminho relativo, para o front não adivinhar o nome. */
  arquivos: Record<string, string>;
  especificacao_congelada: boolean;
  cache_control: "no-cache";
  cache_control_da_tag: "immutable";
}

/** Um trimestre × materialização. O rótulo da faixa indexa o estilo **e** o quadrante. `regime_v1`, `status_regime_v1` e `hachura` não se repetem 166 vezes: o `rotulo_da_faixa` os determina (5 rótulos, conferido pelo exportador) e eles vivem em `TimelineView.estilo_por_rotulo`. `quarter_end`, `ibov_nivel` e `selic_meta_pct` são idênticos nas duas materializações — são mercado, não regime — e vivem em `TimelineView.mercado_por_quarter`, também conferido. */
export interface PontoDaTimeline {
  materializacao: string;
  quarter: string;
  rotulo_da_faixa: string;
  n_obs_regime_v1: number;
  trocou_vs_outra_materializacao: boolean;
  tipo_de_troca: string;
}

/** O quadrante V1 de um trimestre — ou o motivo de ele não ter (D-m). */
export interface QuadranteDoQuarter {
  regime_v1: string | null;
  status_regime_v1: string | null;
}

/** T-01 — as 3 respostas lado a lado, os 3 rankings e a concordância entre as lentes. */
export interface RankingAtualView {
  /** O nome do arquivo sem extensão. */
  view: string;
  /** A tela do PRD §4 que consome esta view (T-01..T-07). */
  tela: string;
  /** A frase de abertura da tela (P7 / RF-W035). */
  pergunta: string;
  tag: string;
  dataset_sha256: string;
  gate: GateDaView;
  /** Artefatos do MANIFEST.json lidos para montar esta view. */
  fontes: string[];
  quarter_perguntado: string;
  respostas: RespostaDeRegimeWeb[];
  rankings: LinhaDeRanking[];
  concordancia: LinhaDeConcordancia[];
  vizinhos_do_quarter: VizinhoDoQuarter[];
  n_vizinhos: number;
  /** Interseção dos top-5 das 3 lentes. Vazia em 3T2026 — primeiro plano (P9). */
  intersecao_dos_top5: string[];
  top5_por_lente: Record<string, string[]>;
}

/** Os vizinhos de uma referência num `k` — a chave sai do grupo, não de cada linha. */
export interface RankingDeVizinhos {
  quarter_ref: string;
  k_usado: number;
  n_vizinhos: number;
  vizinhos: Vizinho[];
}

/** O que **não** foi exportado nesta tag, e por quê. Omissão declarada nunca é omissão. */
export interface ReducaoDeclarada {
  o_que: string;
  artefato: string | null;
  por_que: string;
}

/** 20 de 83 por ramo, 14 não avaliáveis **nomeados**, ramo risco-país declaradamente fora. */
export interface RegraDeStress {
  n_stress: number | null;
  n_total: number | null;
  quarters_nao_avaliaveis: string[];
  ramo_fora: string;
  cai_sobre: string;
}

/** Uma das **três** respostas a "em que regime estamos" — nenhuma escolhida (RF-W019). */
export interface RespostaDeRegimeWeb {
  lente_rotulo: string;
  lente: string;
  lente_titulo: string;
  /** O regime da CÉLULA de onde o ranking saiu. Com `e_fallback`, não é 2026Q3. */
  regime: string | null;
  /** O status do trimestre PERGUNTADO (V1): INDETERMINADO é resposta, não erro. */
  status_regime_v1: string | null;
  /** Por que o trimestre perguntado não tem quadrante (D-m). Nunca preenchido. */
  motivo_indeterminado: string | null;
  materializacao: string;
  horizonte: string;
  quarter_perguntado: string;
  quarter_da_celula: string;
  e_fallback: boolean;
  n_obs: number;
  alerta_n_baixo: boolean;
  conclusao_suprimida: boolean;
  tabela_de_origem: string;
}

/** Uma série do catálogo, com cobertura **declarada** ao lado da **observada** (RF-W033). */
export interface SerieDoCatalogo {
  series_id: string;
  nome: string;
  item_email: string | null;
  fonte: string;
  freq: string;
  unit: string;
  status: string;
  confianca: string;
  lag_divulgacao_dias: number | null;
  data_inicio: string | null;
  data_inicio_observada: string | null;
  data_fim: string | null;
  data_fim_observada: string | null;
  presente_no_processed: boolean;
  cobre_1t2006: boolean | null;
  n_obs: number | null;
  pct_nulos: number | null;
  fonte_url: string | null;
}

/** O status de um ADR como está **em disco** — o portal mostra, nunca edita. */
export interface StatusDeAdr {
  id: string;
  arquivo: string;
  status: string;
}

/** T-04 — 83 trimestres × 2 materializações, com IBOV, Selic e as divergências. */
export interface TimelineView {
  /** O nome do arquivo sem extensão. */
  view: string;
  /** A tela do PRD §4 que consome esta view (T-01..T-07). */
  tela: string;
  /** A frase de abertura da tela (P7 / RF-W035). */
  pergunta: string;
  tag: string;
  dataset_sha256: string;
  gate: GateDaView;
  /** Artefatos do MANIFEST.json lidos para montar esta view. */
  fontes: string[];
  trimestres: PontoDaTimeline[];
  estilo_por_rotulo: Record<string, EstiloDaFaixa>;
  mercado_por_quarter: Record<string, MercadoDoQuarter>;
  materializacoes: string[];
  divergencia: DivergenciaDeMaterializacao;
  distribuicao: DistribuicaoDeRegimes;
  n_trimestres: number;
  janela: string;
}

/** Um vizinho, sem repetir o que já está na chave do grupo (normalização, não agregação). */
export interface Vizinho {
  rank: number;
  quarter_neighbor: string;
  distancia: number | null;
}

/** Um vizinho do trimestre corrente, com o quadrante V1 ou o motivo de não ter (RF-W026). */
export interface VizinhoDoQuarter {
  rank: number;
  quarter_neighbor: string;
  distancia: number | null;
  quarter_t_mais_1: string | null;
  regime_v1_neighbor: string | null;
  status_regime_v1_neighbor: string | null;
}

/** T-03 — "momentos semelhantes": a lente canônica, os 3 `k` e o ranking em T+1. */
export interface VizinhosView {
  /** O nome do arquivo sem extensão. */
  view: string;
  /** A tela do PRD §4 que consome esta view (T-01..T-07). */
  tela: string;
  /** A frase de abertura da tela (P7 / RF-W035). */
  pergunta: string;
  tag: string;
  dataset_sha256: string;
  gate: GateDaView;
  /** Artefatos do MANIFEST.json lidos para montar esta view. */
  fontes: string[];
  lente: LenteDosVizinhos;
  ks: number[];
  k_completo: number;
  regra_de_truncamento: string;
  referencias: string[];
  rankings: RankingDeVizinhos[];
  quadrante_por_quarter: Record<string, QuadranteDoQuarter>;
  t_mais_1_por_quarter: Record<string, string>;
  quarter_do_comite: string;
  ranking_t_mais_1: LinhaDoRankingT1[];
  /** O que a tela diz: 5 features de 6, o que somente_passado não elimina. */
  declaracoes: string[];
}
