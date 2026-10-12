/**
 * As fixturas dos testes, montadas a partir dos tipos GERADOS pelo exportador
 * (`_lib/schema.d.ts`). Nenhum campo é inventado: se o contrato mudar, o `tsc` reprova este
 * arquivo antes de qualquer teste rodar — o que é o ponto.
 *
 * Os números são os do pacote do Comitê (`LIMITACOES-COMITE.md`, `F-022.md` §5.1), em **fração**,
 * como o exportador publica: `0,0504` é o `+5,04%` da tela.
 */

import type { GateDaView, MetaWeb } from "../_lib/schema";

export const TAG = "comite-2026-10-14";
export const OUTRA_TAG = "comite-2026-07-01";
export const SHA = "fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef";

export function gate(parcial: Partial<GateDaView> = {}): GateDaView {
  return {
    especificacao_congelada: false,
    status_adr_001: "PROPOSTA",
    veredito_publicacao:
      "Material de discussao: o ADR-001 nao esta aceito, logo nada aqui e insumo de decisao.",
    marca: "MATERIAL DE DISCUSSAO - especificacao nao congelada (ADR-001 em Proposta)",
    publicavel: false,
    ...parcial,
  };
}

export function meta(parcial: Partial<MetaWeb> = {}): MetaWeb {
  return {
    schema_versao: 2,
    feature: "F-W001",
    tag: TAG,
    dataset_sha256: SHA,
    dataset_sha256_curto: SHA.slice(0, 12),
    agregado: {
      sha256: SHA,
      n_artefatos: 47,
      n_artefatos_fora_do_agregado: 1,
      bytes: 11486650,
      linhas: 306813,
    },
    data_do_dado: {
      date_min_raw_series: "1979-12-31",
      date_max_raw_series: "2026-10-10",
      vintage_max: "2026-10-11",
      primeiro_trimestre_macro: "2006Q1",
      ultimo_trimestre_macro: "2026Q3",
    },
    congelamento: {
      tag: TAG,
      git_commit: "0".repeat(40),
      git_ref: "refs/tags/comite-2026-10-14",
      frozen_txt_presente: true,
      dataset_congelado: true,
    },
    versao_build: { "relatorio_metricas.json": "5f8a0485c521" },
    web_export_versao_build: "697b8e864181aaaa",
    gate: gate(),
    views: [],
    contagens: { celulas_do_heatmap: 322 },
    limitacoes: [{ numero: 1, texto: "n pequeno: 13 a 19 observacoes por regime." }],
    n_decisoes_pendentes: 12,
    unidade_por_campo: {
      excesso_cdi: "fracao",
      ret_medio: "fracao",
      ret_mediana: "fracao",
      ret_real: "fracao",
      pior_tri: "fracao",
      erro_padrao_media: "fracao",
      hit_ratio_cdi: "fracao",
      distancia: "adimensional",
      n_obs: "contagem",
      selic_meta_pct: "percentual_a_a",
    },
    casas_por_unidade: {
      fracao: 4,
      adimensional: 6,
      contagem: 0,
      percentual_a_a: 4,
      indice: 2,
      pontos_percentuais: 4,
    },
    /*
     * A tabela de apresentação, declarada pelo exportador desde 2026-10-11: é daqui que a tela
     * tira o fator 100 de `fracao -> percentual`, e não de uma constante escrita no front.
     */
    unidade_de_apresentacao: {
      excesso_cdi: "percentual",
      ret_medio: "percentual",
      ret_mediana: "percentual",
      ret_real: "percentual",
      pior_tri: "percentual",
      erro_padrao_media: "percentual",
      hit_ratio_cdi: "percentual",
      distancia: "adimensional",
      n_obs: "contagem",
      selic_meta_pct: "percentual_a_a",
    },
    fator_de_apresentacao: {
      excesso_cdi: 100,
      ret_medio: 100,
      ret_mediana: 100,
      ret_real: 100,
      pior_tri: 100,
      erro_padrao_media: 100,
      hit_ratio_cdi: 100,
      distancia: 1,
      n_obs: 1,
      selic_meta_pct: 1,
    },
    casas_de_apresentacao: {
      excesso_cdi: 2,
      ret_medio: 2,
      ret_mediana: 2,
      ret_real: 2,
      pior_tri: 2,
      erro_padrao_media: 2,
      hit_ratio_cdi: 2,
      distancia: 3,
      n_obs: 0,
      selic_meta_pct: 2,
    },
    reducoes: [],
    orcamento: {
      limite_bytes: 400000,
      bytes_das_views: 123456,
      ok: true,
      arquivos_contados: 8,
    },
    artefatos_nao_publicaveis: ["internacional_pesos.parquet"],
    politica_de_cache: { "current.json": "no-cache" },
    ...parcial,
  };
}
