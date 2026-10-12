"""F-W001 — `apps/web_export/`: o gate, o orçamento, o determinismo e as recusas.

| # | O que este bloco prova | Por quê |
|---|---|---|
| 1 | normalização de valor: `NaN` → `null`, casas fixas, `-0.0` → `0.0` | CA-121 no JSON |
| 2 | **recusa sem manifesto** e com manifesto ilegível | não existe dataset do qual exportar |
| 3 | **recusa com artefato proibido** e com `publicavel: false` injetado | RF-W010/W015, **D-af** |
| 4 | **recusa com hash divergente** (byte alterado em disco) | RF-W011/W012 |
| 5 | o gate viaja em toda view e `especificacao_congelada` vem do ADR-001 **em disco** | RF-W002 |
| 6 | **`n < 5` sai com valor E `conclusao_suprimida: true`**; `n < 8` com alerta | RN-04, P1 |
| 7 | **determinismo**: 2 exportações ⇒ mesmo `sha256` em todos os arquivos; sem relógio | RNF-W008
|
| 8 | **orçamento**: o conjunto cabe em 400 KB, e passar disso é recusa | RNF-W001 |
| 9 | o ponteiro `current.json` vai **por último** e nomeia os arquivos da tag | RF-W011 |
| 10 | **acervo real** `data/canonical/` (padrão `Acervo`) — 3 valores conferidos na fonte | §15.9 |

Os blocos 1-9 rodam sobre uma **canônica sintética** montada em `tmp_path` (`canonical_sintetico`),
nomeada como tal, e **nunca pulam**: rodam no CI sem `data/`. Os números sintéticos são redondos de
propósito (`+5%`, `+3%`, `-2%`, `n = 20/6/4`) para que confusão entre sintético e acervo seja óbvia
na leitura. O bloco 10 segue o padrão `Acervo` de `test_tabela_ranking.py §8`: entra por acréscimo
quando os Parquet existem em disco e é desligado por `LDC_IGNORAR_DATA=1`.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from apps.pipeline.common.errors import SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical
from apps.pipeline.run import gravar_manifesto, montar_manifesto, verificar
from apps.web_export import exportar as X
from apps.web_export import views as V
from packages.shared.schemas.web_views import (
    CASAS_POR_UNIDADE,
    LIMITE_DE_BYTES,
    NOME_CURRENT,
    NOME_META,
    NOME_TIPOS_TS,
    UNIDADE_FRACAO,
    VIEWS,
)

COMO_GERAR = "rode `uv run python -m apps.pipeline run --offline`"
VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"
TAG = "tag-sintetica"

# ─────────────────────────────────────────────────────────────────────────────
# Canônica sintética — números redondos, nenhum imita o acervo
# ─────────────────────────────────────────────────────────────────────────────

N_OK = 20
N_ALERTA = 6
N_SUPRIMIDO = 4

LENTES_SINTETICAS: tuple[tuple[str, str, str, str, str, str, bool], ...] = (
    ("V1_revised_X_2000Q1", "V1", "V1 revised", "X", "revised", "T0", True),
    ("V1_asof_X_2000Q2", "V1", "V1 asof", "X", "asof", "T0", False),
    (
        "V3_vizinhos_2000Q2_T_mais_1",
        "V3",
        "V3 vizinhos",
        "VIZINHOS_2000Q2",
        "revised",
        "T+1",
        False,
    ),
)


def _ranking_sintetico() -> pd.DataFrame:
    linhas = []
    for rotulo, lente, titulo, regime, materializacao, horizonte, fallback in LENTES_SINTETICAS:
        for posicao, (asset, n) in enumerate(
            [("AAA", N_OK), ("BBB", N_ALERTA), ("CCC", N_SUPRIMIDO)], start=1
        ):
            linhas.append(
                {
                    "lente_rotulo": rotulo,
                    "lente_titulo": titulo,
                    "lente": lente,
                    "regime": regime,
                    "asset_id": asset,
                    "materializacao": materializacao,
                    "horizonte": horizonte,
                    "quarter_perguntado": "2000Q2",
                    "quarter_da_celula": "2000Q1" if fallback else "2000Q2",
                    "e_fallback": fallback,
                    "tabela_de_origem": "regime_asset_metrics.parquet",
                    "posicao": posicao,
                    "n_obs": n,
                    "excesso_cdi": 0.05,
                    "ret_medio": 0.03,
                    "ret_mediana": 0.03,
                    "hit_ratio_cdi": 0.5,
                    "erro_padrao_media": 0.02,
                    "alerta_n_baixo": n < 8,
                    "conclusao_suprimida": n < 5,
                    "fonte_versao": "v",
                    "excesso_em_erros_padrao": 2.5,
                    "distinguivel_de_ruido": True,
                    "simbolo_n": "",
                    "versao_build": "v",
                }
            )
    return pd.DataFrame(linhas)


def _heatmap_sintetico() -> pd.DataFrame:
    linhas = []
    for vista, tabela, lente, materializacao in [
        ("v1_revised", "regime_asset_metrics.parquet", "V1", "revised"),
        ("v1_asof", "regime_asset_metrics_asof.parquet", "V1", "asof"),
    ]:
        for coluna, regime in enumerate(["X", "Y"]):
            for linha, (asset, grupo, n) in enumerate(
                [
                    ("AAA", "Grupo 1", N_OK),
                    ("BBB", "Grupo 1", N_ALERTA),
                    ("CCC", "Grupo 2", N_SUPRIMIDO),
                ]
            ):
                linhas.append(
                    {
                        "vista": vista,
                        "tabela": tabela,
                        "materializacao": materializacao,
                        "horizonte": "T0",
                        "lente": lente,
                        "regime": regime,
                        "asset_id": asset,
                        "n_obs": n,
                        "excesso_cdi": 0.05,
                        "ret_medio": 0.03,
                        "ret_mediana": 0.03,
                        "erro_padrao_media": 0.02,
                        "hit_ratio_cdi": 0.5,
                        "sharpe_tri": 0.1,
                        "pior_tri": -0.02,
                        "pior_tri_quarter": "2000Q1",
                        "alerta_n_baixo": n < 8,
                        "conclusao_suprimida": n < 5,
                        "data_inicio_serie": "2000-01-01",
                        "fonte_versao": "v",
                        "grupo": grupo,
                        "linha": linha,
                        "coluna": coluna,
                        "y_centro": 0.0,
                        "cor_hex": "#e1e0d9" if n < 5 else "#1b4f72",
                        "hachura": "///" if n < 5 else None,
                        "borda": None,
                        "tinta_do_texto": "#000000",
                        "rotulo_valor": "+5,00%",
                        "rotulo_n": f"n{n}",
                        "gid": f"{vista}-{regime}-{asset}",
                        "tooltip": "sintetico",
                    }
                )
    return pd.DataFrame(linhas)


def _regimes_sintetico(*, asof: bool) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quarter": "2000Q1",
                "regime_v1": "X",
                "status_regime_v1": "CLASSIFICADO",
                "motivo_indeterminado": None,
                "g_score": 1.0,
                "pi_score": 1.0,
                "crescimento_acima": True,
                "inflacao_acelerando": True,
                "desempate_aplicado": False,
                "n_obs_regime_v1": N_OK,
                "alerta_n_baixo": False,
                "conclusao_suprimida": False,
                "alerta_desbalanceamento": False,
                "lag_adjusted": asof,
                "trocou_vs_revised": False,
                "especificacao_congelada": False,
                "versao_especificacao": "V1",
                "fonte_versao": "v",
            },
            {
                "quarter": "2000Q2",
                "regime_v1": None if not asof else "Y",
                "status_regime_v1": "INDETERMINADO" if not asof else "CLASSIFICADO",
                "motivo_indeterminado": "GAP_SINTETICO" if not asof else None,
                "g_score": None,
                "pi_score": 1.0,
                "crescimento_acima": None,
                "inflacao_acelerando": True,
                "desempate_aplicado": False,
                "n_obs_regime_v1": N_OK,
                "alerta_n_baixo": False,
                "conclusao_suprimida": False,
                "alerta_desbalanceamento": False,
                "lag_adjusted": asof,
                "trocou_vs_revised": True,
                "especificacao_congelada": False,
                "versao_especificacao": "V1",
                "fonte_versao": "v",
            },
        ]
    )


def _timeline_sintetica() -> pd.DataFrame:
    linhas = []
    for materializacao in ("revised", "asof"):
        for quarter, rotulo, regime, status in [
            ("2000Q1", "X", "X", "CLASSIFICADO"),
            ("2000Q2", "INDETERMINADO", None, "INDETERMINADO"),
        ]:
            linhas.append(
                {
                    "materializacao": materializacao,
                    "quarter": quarter,
                    "regime_v1": regime,
                    "status_regime_v1": status,
                    "n_obs_regime_v1": N_OK,
                    "lag_adjusted": materializacao == "asof",
                    "especificacao_congelada": False,
                    "versao_especificacao": "V1",
                    "fonte_versao": "v",
                    "quarter_end": f"{quarter[:4]}-03-31",
                    "ibov_nivel": 10000.0,
                    "selic_meta_pct": 10.0,
                    "cor_hex": "#898781" if regime is None else "#1b4f72",
                    "hachura": "///" if regime is None else None,
                    "rotulo_da_faixa": rotulo,
                    "trocou_vs_outra_materializacao": False,
                    "tipo_de_troca": "NENHUMA",
                }
            )
    return pd.DataFrame(linhas)


def _vizinhos_sinteticos() -> pd.DataFrame:
    linhas = []
    for k in (5, 8, 12):
        for rank in range(1, k + 1):
            linhas.append(
                {
                    "quarter_ref": "2000Q2",
                    "rank": rank,
                    "quarter_neighbor": f"19{90 + rank:02d}Q1",
                    "distancia": float(rank),
                    "metrica": "mahalanobis",
                    "k_usado": k,
                    "n_vizinhos": k,
                    "n_features": 5,
                    "features_usadas": "a|b|c|d|e",
                    "regime_v1_neighbor": "X",
                    "status_regime_v1_neighbor": "CLASSIFICADO",
                    "quarter_t_mais_1": f"19{90 + rank:02d}Q2",
                    "shrinkage": "ledoit_wolf",
                    "janela_padronizacao": "expanding_ate_T",
                    "somente_passado": True,
                    "restrito_pos_2016": False,
                    "alerta_n_baixo": True,
                    "especificacao_congelada": False,
                    "versao_especificacao": "V3",
                    "lag_adjusted": False,
                    "fonte_versao": "v",
                }
            )
    return pd.DataFrame(linhas)


def _internacional_sintetico() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "lente": "V1",
                "regime": "X",
                "asset_id": "III",
                "n_obs": n,
                "ret_medio": 0.03,
                "ret_mediana": 0.03,
                "excesso_cdi": 0.05,
                "ret_real": 0.02,
                "hit_ratio_cdi": 0.5,
                "corr_ibov": -0.5,
                "n_pares_ibov": n,
                "corr_imab": 0.5,
                "n_pares_imab": n,
                "is_total_return": None,
                "alerta_n_baixo": n < 8,
                "conclusao_suprimida": n < 5,
                "especificacao_congelada": False,
                "fonte_versao": "v",
            }
            for n in (N_OK, N_SUPRIMIDO)
        ]
    )


def _series_catalog_sintetico() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "series_id": "SIN_1",
                "nome": "Serie sintetica 1",
                "item_email": "A1",
                "fonte": "MANUAL",
                "identificador": "sin1",
                "fonte_url": "https://exemplo.invalid/sin1",
                "freq": "Q",
                "data_inicio": "2000-01-01",
                "data_fim": "2000-06-30",
                "unit": "indice",
                "transformacao_padrao": "nivel",
                "lag_divulgacao_dias": 30,
                "confianca": "CONFIRMADO",
                "status": "ok",
                "is_total_return": None,
                "calendario": None,
                "janela_rolante": False,
                "fonte_instavel": False,
                "licenca_restrita": False,
                "obs": None,
                "presente_no_processed": True,
                "data_inicio_observada": "2000-01-01",
                "data_fim_observada": "2000-06-30",
                "n_obs": 2,
                "pct_nulos": 0.0,
                "cobre_1t2006": False,
            }
        ]
    )


RELATORIOS_SINTETICOS: dict[str, dict[str, Any]] = {
    "relatorio_metricas.json": {
        "versao_build": "sintetico",
        "regime_atual": {"quarter": "2000Q2"},
        "concordancia_entre_lentes": {
            "em_todas_as_lentes": [],
            "top_por_lente": {"V1_revised_X_2000Q1": ["AAA"]},
        },
    },
    "relatorio_regimes_v1.json": {
        "versao_build": "sintetico",
        "divergencia_asof_vs_revised": {
            "trimestres_que_trocam": 1,
            "trimestres_comparaveis": 2,
            "pct_que_trocam": 0.5,
            "limiar_inoperante": 0.25,
            "modelo_operacional": False,
            "trocas": [{"quarter": "2000Q2", "asof": "Y", "revised": None}],
        },
        "distribuicao": {
            "desbalanceamento_relativo": 1.0,
            "por_grupo": {"X": {"n": 1}},
        },
        "indeterminados": {"n": 1, "quarters": ["2000Q2"]},
    },
    "relatorio_regimes_v3.json": {
        "versao_build": "sintetico",
        "ranking_ativos_t_mais_1": {
            "ativos": [
                {
                    "asset_id": "AAA",
                    "n": N_OK,
                    "media": 0.05,
                    "mediana": 0.03,
                    "erro_padrao": 0.02,
                    "hit_ratio_cdi": 0.5,
                },
                {
                    "asset_id": "CCC",
                    "n": N_SUPRIMIDO,
                    "media": -0.02,
                    "mediana": -0.02,
                    "erro_padrao": 0.06,
                    "hit_ratio_cdi": 0.25,
                },
            ]
        },
    },
    "relatorio_internacional.json": {
        "versao_build": "sintetico",
        "hedge_cambial": {
            "stress_vs_nao_stress": {
                "blocos": {"stress": {"correlacao": -0.5, "n_pares": N_OK}},
            },
            "dez_piores_trimestres_do_ibov": [
                {"quarter": "2000Q1", "ret_ibov": -0.2, "ret_usdbrl": 0.1, "stress_flag": True}
            ],
        },
        "faixa_de_d6": {
            "ativo_representativo": "III",
            "piso_estrutural": {"min": 0.16, "max": 0.2},
            "banda_tatica": {"min": 0.15, "max": 0.35},
            "cap_usado": 0.4,
            "decisao": "D6 sintetica",
            "forma": "faixa, nunca ponto",
            "distincao_obrigatoria": "hedgeado != cambial",
        },
        "regra_de_stress": {
            "n_stress": 1,
            "n_trimestres": 2,
            "nao_avaliaveis_pelo_ramo_inclinacao": ["2000Q1"],
            "ramo_embi_fora": "fora, sintetico",
            "cai_sobre": "a variacao",
        },
        "universo": {"bloqueados_sem_fonte": {"GOLD_BRL": "sem fonte"}},
    },
}

LIMITACOES_SINTETICAS = "\n".join(f"{i}. Limitacao sintetica {i}." for i in range(1, 11))

DECISOES_SINTETICAS = "\n".join(
    [
        "## 7. Decisoes",
        "",
        "| # | Decisão | Padrão provisório adotado | O que muda se o Comitê discordar |",
        "|---|---|---|---|",
        *[f"| D{i} | decisao {i} | padrao {i} | custo {i} |" for i in range(1, 13)],
        "",
    ]
)


def _escrever_docs(raiz: Path) -> None:
    for identificador, arquivo in V.ADRS_DO_PORTAL:
        alvo = raiz / V.PASTA_DOS_ADRS / arquivo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        status = "**Proposta**" if identificador == "ADR-001" else "**Aceita**"
        alvo.write_text(
            f"# {identificador} sintetico\n\n- **Status:** {status}\n", encoding="utf-8"
        )
    limitacoes = raiz / "docs" / "product" / "LIMITACOES-COMITE.md"
    limitacoes.parent.mkdir(parents=True, exist_ok=True)
    limitacoes.write_text(DECISOES_SINTETICAS, encoding="utf-8")
    caderno = raiz / "apps" / "analysis" / "notebooks" / "entrega_comite_2026-10-14.ipynb"
    caderno.parent.mkdir(parents=True, exist_ok=True)
    caderno.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "id": "md-s8",
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": [LIMITACOES_SINTETICAS],
                    }
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def canonical_sintetico(tmp_path: Path) -> Path:
    """Uma raiz de repo **sintética** com `data/canonical/` completo e `MANIFEST.json` coerente."""
    raiz = tmp_path / "repo"
    pasta = raiz / "data" / "canonical"
    (pasta / "tabelas").mkdir(parents=True)
    (pasta / "figuras").mkdir(parents=True)
    _ranking_sintetico().to_parquet(pasta / "tabelas" / "ranking_regime_atual.parquet", index=False)
    pd.DataFrame(
        [
            {
                "secao": "POR_LENTE",
                "chave": "V1_revised_X_2000Q1",
                "metrica": "top_5",
                "valor_num": None,
                "valor_texto": "AAA | BBB",
                "versao_build": "v",
            }
        ]
    ).to_parquet(pasta / "tabelas" / "concordancia_lentes.parquet", index=False)
    _heatmap_sintetico().to_parquet(pasta / "figuras" / "heatmap_dados.parquet", index=False)
    _timeline_sintetica().to_parquet(
        pasta / "figuras" / "timeline_regimes_dados.parquet", index=False
    )
    _regimes_sintetico(asof=False).to_parquet(pasta / "regimes_v1.parquet", index=False)
    _regimes_sintetico(asof=True).to_parquet(pasta / "regimes_v1_asof.parquet", index=False)
    _vizinhos_sinteticos().to_parquet(pasta / "regime_neighbors_v3.parquet", index=False)
    _internacional_sintetico().to_parquet(pasta / "internacional_por_regime.parquet", index=False)
    _series_catalog_sintetico().to_parquet(pasta / "series_catalog.parquet", index=False)
    for nome, conteudo in RELATORIOS_SINTETICOS.items():
        (pasta / nome).write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
    _escrever_docs(raiz)
    gravar_manifesto(montar_manifesto(raiz=raiz), destino=pasta / "MANIFEST.json")
    return raiz


def _exportar(raiz: Path, *, destino: Path | None = None) -> X.ResultadoExportacao:
    return X.exportar(tag=TAG, destino=destino or (raiz / "data" / "web"), raiz=raiz)


# ═════════════════════════════════════════════════════════════════════════════
# 1 — Normalização de valor
# ═════════════════════════════════════════════════════════════════════════════


def test_nan_vira_null_e_nunca_zero() -> None:
    """`NaN` sai como `null`. Zero renderizado no lugar de ausência é o erro de RNF-W010."""
    assert V.escalar(float("nan"), campo="excesso_cdi") is None
    assert V.escalar(None, campo="excesso_cdi") is None
    assert V.escalar(pd.NA, campo="excesso_cdi") is None
    assert V.escalar(float("inf"), campo="excesso_cdi") is None


def test_casas_decimais_sao_as_declaradas_por_unidade() -> None:
    """Fração arredonda nas casas de `CASAS_POR_UNIDADE` — não no `repr` do float."""
    casas = CASAS_POR_UNIDADE[UNIDADE_FRACAO]
    assert V.casas_do_campo("excesso_cdi") == casas
    assert V.escalar(0.0594769722, campo="excesso_cdi") == round(0.0594769722, casas)
    assert V.escalar(10.123456789, campo="selic_meta_pct") == 10.1235
    assert V.escalar(37951.9712, campo="ibov_nivel") == 37951.97


def test_zero_negativo_e_normalizado() -> None:
    """`-0.0` e `0.0` são o mesmo número e têm de ser o mesmo byte (CA-121)."""
    assert V.escalar(-0.0, campo="excesso_cdi") == 0.0
    assert json.dumps(V.escalar(-0.0, campo="excesso_cdi")) == "0.0"


def test_coluna_fora_da_tabela_levanta_nomeando() -> None:
    """Campo do contrato ausente no Parquet para e **nomeia** — nunca sai `undefined` na tela."""
    with pytest.raises(SerieInconsistente, match="colunas do contrato"):
        V.registro(pd.Series({"a": 1}), ("a", "inexistente"))


# ═════════════════════════════════════════════════════════════════════════════
# 2 — Recusa sem manifesto
# ═════════════════════════════════════════════════════════════════════════════


def test_recusa_sem_manifesto(tmp_path: Path) -> None:
    """Sem `MANIFEST.json` não há dataset: `BLOQUEADO - FONTE INDISPONIVEL`, nunca JSON parcial."""
    (tmp_path / "data" / "canonical").mkdir(parents=True)
    with pytest.raises(X.ErroDeExportacao, match="FONTE INDISPONIVEL"):
        X.exportar(tag=TAG, destino=tmp_path / "web", raiz=tmp_path)
    assert not (tmp_path / "web").exists()


def test_recusa_com_manifesto_ilegivel(canonical_sintetico: Path) -> None:
    """Manifesto corrompido não é "manifesto vazio": é recusa."""
    alvo = canonical_sintetico / "data" / "canonical" / "MANIFEST.json"
    alvo.write_text("{ nao e json", encoding="utf-8")
    with pytest.raises(X.ErroDeExportacao, match="nao e JSON valido"):
        _exportar(canonical_sintetico)


# ═════════════════════════════════════════════════════════════════════════════
# 3 — Recusa com artefato proibido ou não publicável
# ═════════════════════════════════════════════════════════════════════════════


def test_recusa_quando_artefato_lido_e_marcado_nao_publicavel(canonical_sintetico: Path) -> None:
    """**A lista de inclusão não vence o manifesto** (o princípio de F-031, **D-af**).

    Injeta `publicavel: false` num artefato que uma view leria e exige falha — não omissão
    silenciosa da view.
    """
    alvo = canonical_sintetico / "data" / "canonical" / "MANIFEST.json"
    manifesto = json.loads(alvo.read_text(encoding="utf-8"))
    for entrada in manifesto["artefatos"]:
        if entrada["arquivo"] == V.NOME_HEATMAP:
            entrada["publicavel"] = False
            entrada["motivo_nao_publicavel"] = "injetado pelo teste"
    alvo.write_text(json.dumps(manifesto, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(X.GateFechadoParaOArtefato, match="publicavel:false"):
        _exportar(canonical_sintetico)
    assert not (canonical_sintetico / "data" / "web").exists()


def test_artefato_proibido_na_lista_de_leitura_levanta(
    canonical_sintetico: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RF-W015: `internacional_pesos`, `raw_series`, `regime_neighbors` e `ldc.duckdb` jamais."""
    monkeypatch.setattr(
        V, "ARTEFATOS_LIDOS", (*V.ARTEFATOS_LIDOS, "internacional_pesos.parquet"), raising=True
    )
    with pytest.raises(X.ArtefatoProibido, match="ARTEFATO PROIBIDO"):
        _exportar(canonical_sintetico)


def test_nenhum_proibido_esta_na_lista_de_leitura() -> None:
    """A trava estática: as duas listas são disjuntas no código publicado."""
    assert not set(V.ARTEFATOS_LIDOS) & set(V.ARTEFATOS_PROIBIDOS)
    for proibido in ("internacional_pesos.parquet", "raw_series.parquet", "ldc.duckdb"):
        assert proibido in V.ARTEFATOS_PROIBIDOS


def test_recusa_quando_artefato_lido_nao_esta_no_manifesto(canonical_sintetico: Path) -> None:
    """Artefato não manifestado é artefato que o `verify` não protege."""
    alvo = canonical_sintetico / "data" / "canonical" / "MANIFEST.json"
    manifesto = json.loads(alvo.read_text(encoding="utf-8"))
    manifesto["artefatos"] = [
        e for e in manifesto["artefatos"] if e["arquivo"] != V.NOME_SERIES_CATALOG
    ]
    alvo.write_text(json.dumps(manifesto, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(X.ErroDeExportacao, match="nao esta\\(o\\) no MANIFEST"):
        _exportar(canonical_sintetico)


# ═════════════════════════════════════════════════════════════════════════════
# 4 — Recusa com hash divergente
# ═════════════════════════════════════════════════════════════════════════════


def test_recusa_com_byte_alterado_em_disco(canonical_sintetico: Path) -> None:
    """Byte alterado depois do manifesto ⇒ exportar publicaria outro dataset. Recusa."""
    alvo = canonical_sintetico / "data" / "canonical" / "relatorio_metricas.json"
    alvo.write_text(alvo.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(X.DatasetDivergente, match="DATASET DIVERGENTE"):
        _exportar(canonical_sintetico)


def test_recusa_quando_frozen_declara_outro_hash(canonical_sintetico: Path) -> None:
    """`FROZEN.txt` apontando para outro `DATASET_SHA256` é divergência, não detalhe."""
    (canonical_sintetico / "data" / "canonical" / "FROZEN.txt").write_text(
        "tag                 : outra\nDATASET_SHA256      : " + "0" * 64 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(X.DatasetDivergente, match="FROZEN"):
        _exportar(canonical_sintetico)


# ═════════════════════════════════════════════════════════════════════════════
# 5 — O gate viaja em toda view
# ═════════════════════════════════════════════════════════════════════════════


def test_gate_vem_do_adr_em_disco_e_viaja_em_toda_view(canonical_sintetico: Path) -> None:
    """ADR-001 em `Proposta` ⇒ `especificacao_congelada: false` + marca, nas 6 views."""
    resultado = _exportar(canonical_sintetico)
    assert resultado.gate["status_adr_001"] == "PROPOSTA"
    assert resultado.gate["especificacao_congelada"] is False
    assert resultado.gate["marca"]
    for nome in VIEWS:
        corpo = json.loads((resultado.pasta_da_tag / f"{nome}.json").read_text(encoding="utf-8"))
        assert corpo["gate"]["especificacao_congelada"] is False
        assert corpo["gate"]["status_adr_001"] == "PROPOSTA"
        assert corpo["gate"]["publicavel"] is False
        assert "NAO CONGELADA" in corpo["gate"]["veredito_publicacao"]


def test_gate_abre_sozinho_quando_o_adr_vira_aceita(canonical_sintetico: Path) -> None:
    """P3: a faixa some no rebuild quando o Edu vira o `Status` — **zero linha de código**."""
    adr = canonical_sintetico / V.PASTA_DOS_ADRS / V.ADRS_DO_PORTAL[0][1]
    adr.write_text("# ADR-001\n\n- **Status:** **Aceita**\n", encoding="utf-8")
    resultado = _exportar(canonical_sintetico)
    assert resultado.gate["especificacao_congelada"] is True
    assert resultado.gate["marca"] == ""
    corpo = json.loads((resultado.pasta_da_tag / "catalogo.json").read_text(encoding="utf-8"))
    assert corpo["gate"]["publicavel"] is True


def test_gate_falha_fechada_sem_o_adr(canonical_sintetico: Path) -> None:
    """ADR ausente ⇒ `DESCONHECIDO` ⇒ **não** congelada. Nunca o contrário."""
    (canonical_sintetico / V.PASTA_DOS_ADRS / V.ADRS_DO_PORTAL[0][1]).unlink()
    gate = X.ler_gate(raiz=canonical_sintetico)
    assert gate["status_adr_001"] == "DESCONHECIDO"
    assert gate["especificacao_congelada"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 6 — As duas travas de `n`
# ═════════════════════════════════════════════════════════════════════════════


def test_n_menor_que_5_sai_com_valor_e_com_a_flag(canonical_sintetico: Path) -> None:
    """A supressão não apaga o número: emite o valor **e** `conclusao_suprimida: true`.
    Célula vazia renderizada como zero é o erro de RNF-W010; "sem conclusão (n=4)" é o certo.
    """
    resultado = _exportar(canonical_sintetico)
    celulas = json.loads(
        (resultado.pasta_da_tag / "heatmap_regime_ativo.json").read_text(encoding="utf-8")
    )["celulas"]
    suprimidas = [c for c in celulas if c["n_obs"] < 5]
    assert suprimidas
    for celula in suprimidas:
        assert celula["conclusao_suprimida"] is True
        assert celula["excesso_cdi"] is not None
        assert celula["hachura"], "n<5 precisa do segundo canal (hachura), nao so da cor"
    for celula in celulas:
        assert celula["alerta_n_baixo"] is (celula["n_obs"] < 8)
        assert celula["conclusao_suprimida"] is (celula["n_obs"] < 5)
        assert "n_obs" in celula, "toda celula carrega n (RN-04)"


def test_flag_divergente_do_limiar_do_pipeline_levanta(canonical_sintetico: Path) -> None:
    """Se o Parquet trouxer a flag errada para o `n`, a ponte para em vez de publicar."""
    pasta = canonical_sintetico / "data" / "canonical" / "figuras"
    quadro = pd.read_parquet(pasta / "heatmap_dados.parquet")
    quadro.loc[quadro["n_obs"] < 5, "conclusao_suprimida"] = False
    quadro.to_parquet(pasta / "heatmap_dados.parquet", index=False)
    gravar_manifesto(
        montar_manifesto(raiz=canonical_sintetico),
        destino=canonical_sintetico / "data" / "canonical" / "MANIFEST.json",
    )
    with pytest.raises(SerieInconsistente, match="conclusao_suprimida"):
        _exportar(canonical_sintetico)


def test_ranking_t_mais_1_carrega_as_duas_flags(canonical_sintetico: Path) -> None:
    """O ranking em T+1 vem de relatório (sem flags): elas são **derivadas** das funções do
    pipeline.
    """
    resultado = _exportar(canonical_sintetico)
    linhas = json.loads((resultado.pasta_da_tag / "vizinhos.json").read_text(encoding="utf-8"))[
        "ranking_t_mais_1"
    ]
    por_ativo = {linha["asset_id"]: linha for linha in linhas}
    assert por_ativo["CCC"]["conclusao_suprimida"] is True
    assert por_ativo["CCC"]["excesso_cdi"] is not None
    assert por_ativo["AAA"]["conclusao_suprimida"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 7 — Determinismo
# ═════════════════════════════════════════════════════════════════════════════


def test_duas_exportacoes_dao_o_mesmo_sha256(canonical_sintetico: Path) -> None:
    """RNF-W008: 2 exportações ⇒ mesmo `sha256` em **todos** os arquivos."""
    primeira = {item["arquivo"]: item["sha256"] for item in _exportar(canonical_sintetico).arquivos}
    segunda = {item["arquivo"]: item["sha256"] for item in _exportar(canonical_sintetico).arquivos}
    assert primeira == segunda
    assert len(primeira) == len(VIEWS) + 3


def test_destino_diferente_nao_muda_os_bytes(canonical_sintetico: Path) -> None:
    """O conteúdo depende do dataset, não de onde foi escrito."""
    uma = _exportar(canonical_sintetico, destino=canonical_sintetico / "a")
    outra = _exportar(canonical_sintetico, destino=canonical_sintetico / "b")
    assert {i["arquivo"]: i["sha256"] for i in uma.arquivos} == {
        i["arquivo"]: i["sha256"] for i in outra.arquivos
    }


def test_meta_nao_tem_relogio(canonical_sintetico: Path) -> None:
    """A data que `meta.json` publica é a **do dado**. Nenhum campo vem de `datetime.now()`."""
    resultado = _exportar(canonical_sintetico)
    meta = json.loads((resultado.pasta_da_tag / NOME_META).read_text(encoding="utf-8"))
    assert set(meta["data_do_dado"]) == {
        "date_min_raw_series",
        "date_max_raw_series",
        "vintage_max",
        "primeiro_trimestre_macro",
        "ultimo_trimestre_macro",
    }
    assert meta["data_do_dado"]["ultimo_trimestre_macro"] is None  # sintético não tem macro
    corpo = (resultado.pasta_da_tag / NOME_META).read_text(encoding="utf-8")
    for proibido in ("gerado_em", "exportado_em", "timestamp", "now"):
        assert proibido not in corpo


def test_chaves_ordenadas_em_todo_arquivo(canonical_sintetico: Path) -> None:
    """`sort_keys=True`: a ordem das chaves não depende da ordem de inserção do Python."""
    resultado = _exportar(canonical_sintetico)
    for nome in [*[f"{v}.json" for v in VIEWS], NOME_META]:
        corpo = json.loads((resultado.pasta_da_tag / nome).read_text(encoding="utf-8"))
        assert list(corpo) == sorted(corpo), nome


# ═════════════════════════════════════════════════════════════════════════════
# 8 — Orçamento
# ═════════════════════════════════════════════════════════════════════════════


def test_orcamento_declarado_e_conferido(canonical_sintetico: Path) -> None:
    """O orçamento é **medido** e publicado em `meta.orcamento` — não é promessa."""
    resultado = _exportar(canonical_sintetico)
    assert resultado.bytes_das_views <= LIMITE_DE_BYTES
    meta = json.loads((resultado.pasta_da_tag / NOME_META).read_text(encoding="utf-8"))
    assert meta["orcamento"]["ok"] is True
    assert meta["orcamento"]["limite_bytes"] == LIMITE_DE_BYTES
    assert meta["orcamento"]["bytes_das_views"] == resultado.bytes_das_views


def test_passar_do_orcamento_e_recusa(
    canonical_sintetico: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acima do limite, o exportador **para**. Descobrir isso no 4G do Alexandre é tarde."""
    monkeypatch.setattr(X, "LIMITE_DE_BYTES", 10, raising=True)
    with pytest.raises(X.OrcamentoExcedido, match="ORCAMENTO EXCEDIDO"):
        _exportar(canonical_sintetico)


def test_reducoes_sao_declaradas_com_motivo(canonical_sintetico: Path) -> None:
    """Toda omissão tem artefato (ou `null`) e motivo — omissão declarada não é omissão."""
    resultado = _exportar(canonical_sintetico)
    meta = json.loads((resultado.pasta_da_tag / NOME_META).read_text(encoding="utf-8"))
    assert meta["reducoes"]
    for reducao in meta["reducoes"]:
        assert reducao["o_que"] and reducao["por_que"]
    catalogo = json.loads((resultado.pasta_da_tag / "catalogo.json").read_text(encoding="utf-8"))
    assert catalogo["reducoes"] == meta["reducoes"]


# ═════════════════════════════════════════════════════════════════════════════
# 9 — O ponteiro
# ═════════════════════════════════════════════════════════════════════════════


def test_current_fica_no_pai_e_nomeia_os_arquivos(canonical_sintetico: Path) -> None:
    """Um ponteiro, `no-cache`, no diretório **pai** da tag; a tag é `immutable` (RF-W011)."""
    resultado = _exportar(canonical_sintetico)
    ponteiro = json.loads((resultado.destino / NOME_CURRENT).read_text(encoding="utf-8"))
    assert ponteiro["tag"] == TAG
    assert ponteiro["cache_control"] == "no-cache"
    assert ponteiro["cache_control_da_tag"] == "immutable"
    assert ponteiro["meta"] == f"{TAG}/{NOME_META}"
    for nome in VIEWS:
        assert ponteiro["arquivos"][nome] == f"{TAG}/{nome}.json"
        assert (resultado.destino / ponteiro["arquivos"][nome]).is_file()
    assert ponteiro["dataset_sha256"] == resultado.dataset_sha256


def test_ponteiro_e_o_ultimo_arquivo_escrito(canonical_sintetico: Path) -> None:
    """O ponteiro **sempre por último**: se a escrita falhar no meio, ele aponta para a tag
    antiga.
    """
    resultado = _exportar(canonical_sintetico)
    assert resultado.arquivos[-1]["arquivo"] == NOME_CURRENT
    assert resultado.arquivos[-2]["arquivo"] == NOME_META


def test_meta_publica_o_sha256_de_cada_view(canonical_sintetico: Path) -> None:
    """RF-W012: o portal confere o hash do que leu contra o que o manifesto declara."""
    resultado = _exportar(canonical_sintetico)
    meta = json.loads((resultado.pasta_da_tag / NOME_META).read_text(encoding="utf-8"))
    for entrada in meta["views"]:
        corpo = (resultado.pasta_da_tag / entrada["arquivo"]).read_bytes()
        assert hashlib.sha256(corpo).hexdigest() == entrada["sha256"]
        assert len(corpo) == entrada["bytes"]


def test_aviso_quando_o_destino_fica_dentro_do_canonical(canonical_sintetico: Path) -> None:
    """Escrever em `data/canonical/` quebra o `verify` do pipeline — o exportador avisa.

    E a quebra é demonstrada, não suposta: depois de exportar para dentro de `data/canonical/`, o
    `verificar` do pipeline reprova com **um artefato não listado por arquivo escrito**, porque
    `run.inventariar` varre a pasta recursivamente. É a colisão que **D-ag** resolveu para o pacote
    de entrega com uma exclusão por prefixo, e que `AVISO_DESTINO_NO_CANONICAL` propõe resolver
    igual. Até lá, o destino padrão (`data/web/`) é o correto.
    """
    fora = _exportar(canonical_sintetico, destino=canonical_sintetico / "data" / "web")
    assert fora.destino_no_canonical is False
    assert verificar(raiz=canonical_sintetico).ok, "exportar para data/web nao mexe no verify"

    dentro = _exportar(
        canonical_sintetico, destino=caminho_canonical("web", raiz=canonical_sintetico)
    )
    assert dentro.destino_no_canonical is True
    assert X.AVISO_DESTINO_NO_CANONICAL.startswith("AVISO")
    depois = verificar(raiz=canonical_sintetico)
    assert not depois.ok
    assert len(depois.graves) == len(dentro.arquivos) + 1  # + o agregado divergente


def test_prefixo_entre_ks_e_conferido(canonical_sintetico: Path) -> None:
    """Emitir **um** ranking só vale se os `k` menores forem prefixo dele. Senão, levanta."""
    pasta = canonical_sintetico / "data" / "canonical"
    quadro = pd.read_parquet(pasta / "regime_neighbors_v3.parquet")
    alvo = (quadro["k_usado"] == 5) & (quadro["rank"] == 1)
    quadro.loc[alvo, "quarter_neighbor"] = "1888Q1"
    quadro.to_parquet(pasta / "regime_neighbors_v3.parquet", index=False)
    gravar_manifesto(montar_manifesto(raiz=canonical_sintetico), destino=pasta / "MANIFEST.json")
    with pytest.raises(SerieInconsistente, match="NAO e prefixo"):
        _exportar(canonical_sintetico)


def test_dependencia_funcional_quebrada_levanta(canonical_sintetico: Path) -> None:
    """Dois `grupo` para o mesmo ativo ⇒ normalizar perderia informação ⇒ recusa."""
    pasta = canonical_sintetico / "data" / "canonical" / "figuras"
    quadro = pd.read_parquet(pasta / "heatmap_dados.parquet")
    quadro.loc[quadro.index[0], "grupo"] = "Outro grupo"
    quadro.to_parquet(pasta / "heatmap_dados.parquet", index=False)
    gravar_manifesto(
        montar_manifesto(raiz=canonical_sintetico),
        destino=canonical_sintetico / "data" / "canonical" / "MANIFEST.json",
    )
    with pytest.raises(SerieInconsistente, match="nao determina"):
        _exportar(canonical_sintetico)


def test_sp500_usd_na_figura_levanta(canonical_sintetico: Path) -> None:
    """`SP500_USD` foi retirado da figura (Anti-SPEC §10.2.12): a view não pode reintroduzi-lo."""
    pasta = canonical_sintetico / "data" / "canonical" / "figuras"
    quadro = pd.read_parquet(pasta / "heatmap_dados.parquet")
    quadro.loc[quadro.index[0], "asset_id"] = V.ASSET_FORA_DA_FIGURA
    quadro.to_parquet(pasta / "heatmap_dados.parquet", index=False)
    gravar_manifesto(
        montar_manifesto(raiz=canonical_sintetico),
        destino=canonical_sintetico / "data" / "canonical" / "MANIFEST.json",
    )
    with pytest.raises(SerieInconsistente, match="SP500_USD"):
        _exportar(canonical_sintetico)


def test_internacional_nao_emite_variancia_minima(canonical_sintetico: Path) -> None:
    """T-06 sem a tabela de variância mínima e **sem número pontual** de alocação."""
    resultado = _exportar(canonical_sintetico)
    corpo = (resultado.pasta_da_tag / "internacional.json").read_text(encoding="utf-8")
    for proibido in ("variancia_minima", "peso_variancia_minima", "peso_sugerido_na_banda"):
        assert proibido not in corpo
    dados = json.loads(corpo)
    assert dados["omitido_pelo_gate"][0]["artefato"] == "internacional_pesos.parquet"
    assert dados["faixa_d6"]["piso_estrutural_min"] is not None
    assert dados["faixa_d6"]["banda_tatica_max"] is not None


def test_nenhum_arquivo_cita_artefato_proibido(canonical_sintetico: Path) -> None:
    """Varredura: nenhum nome de artefato proibido aparece nas views — exceto o motivo do gate."""
    resultado = _exportar(canonical_sintetico)
    for nome in VIEWS:
        corpo = (resultado.pasta_da_tag / f"{nome}.json").read_text(encoding="utf-8")
        for proibido in V.ARTEFATOS_PROIBIDOS:
            if proibido == "internacional_pesos.parquet":
                continue  # citado como OMISSÃO declarada, nunca como fonte de valor
            assert proibido not in corpo, f"{nome} cita {proibido}"


# ═════════════════════════════════════════════════════════════════════════════
# 9a — O acerto de contrato com o módulo do portal (2026-10-11)
# ═════════════════════════════════════════════════════════════════════════════


def test_meta_declara_a_apresentacao_campo_a_campo(canonical_sintetico: Path) -> None:
    """Item 1 de `MODULO-ANALYTICS-MACRO.md §2`: o fator sai do contrato, não do código do front.

    O valor continua **nativo** (D-W4): o que o `meta` ganha é a instrução de apresentação, campo a
    campo. `fracao → percentual` com fator 100 e 2 casas é a conversão que a tela já fazia — e o
    número 100 passa a estar escrito de um lado só.
    """
    resultado = _exportar(canonical_sintetico)
    meta = json.loads((resultado.pasta_da_tag / NOME_META).read_text(encoding="utf-8"))

    for chave in ("unidade_de_apresentacao", "fator_de_apresentacao", "casas_de_apresentacao"):
        assert set(meta[chave]) == set(meta["unidade_por_campo"]), chave

    assert meta["unidade_de_apresentacao"]["excesso_cdi"] == "percentual"
    assert meta["fator_de_apresentacao"]["excesso_cdi"] == 100.0
    assert meta["casas_de_apresentacao"]["excesso_cdi"] == 2
    # Selic já é % a.a.: apresentar com fator 100 é o erro de 100x que a tabela existe para impedir
    assert meta["unidade_de_apresentacao"]["selic_meta_pct"] == "percentual_a_a"
    assert meta["fator_de_apresentacao"]["selic_meta_pct"] == 1.0
    assert meta["fator_de_apresentacao"]["n_obs"] == 1.0
    assert meta["casas_de_apresentacao"]["n_obs"] == 0
    # e o valor emitido segue sendo o nativo, nunca o apresentado
    celulas = json.loads(
        (resultado.pasta_da_tag / "heatmap_regime_ativo.json").read_text(encoding="utf-8")
    )["celulas"]
    assert all(abs(c["excesso_cdi"]) < 1 for c in celulas if c["excesso_cdi"] is not None)


def test_heatmap_declara_o_eixo_de_cor_por_vista(canonical_sintetico: Path) -> None:
    """Item 2: `extremo_simetrico` por vista, como **eixo** — simétrico e sobre a vista inteira."""
    resultado = _exportar(canonical_sintetico)
    view = json.loads(
        (resultado.pasta_da_tag / "heatmap_regime_ativo.json").read_text(encoding="utf-8")
    )
    eixos = view["eixos_de_cor"]
    assert {e["vista"] for e in eixos} == set(view["vistas"])
    assert {e["campo"] for e in eixos} == set(V.CAMPOS_DO_EIXO_DE_COR)

    for eixo in eixos:
        da_vista = [
            c[eixo["campo"]]
            for c in view["celulas"]
            if c["vista"] == eixo["vista"] and c[eixo["campo"]] is not None
        ]
        assert eixo["n_celulas_com_valor"] == len(da_vista)
        if not da_vista:
            assert eixo["extremo_simetrico"] is None
            continue
        assert eixo["extremo_simetrico"] == max(abs(v) for v in da_vista)
        # simetria é o ponto: sem ela o neutro do meio deixa de significar "empatou"
        assert eixo["limite_inferior"] == -eixo["extremo_simetrico"]
        assert eixo["limite_superior"] == eixo["extremo_simetrico"]


def test_extremo_e_da_vista_inteira_nao_do_recorte() -> None:
    """O extremo não pode depender de filtro: marcar uma classe repintaria as outras.

    Duas vistas, e o maior valor de cada uma num ativo diferente — se o cálculo escorregasse para
    o conjunto todo, as duas linhas sairiam com o mesmo extremo.
    """
    celulas = pd.DataFrame(
        {
            "vista": ["A", "A", "B", "B"],
            "excesso_cdi": [0.10, -0.02, 0.01, -0.30],
            "ret_medio": [0.10, -0.02, 0.01, -0.30],
            "ret_mediana": [0.10, -0.02, 0.01, -0.30],
            "pior_tri": [None, None, None, None],
        }
    )
    por_chave = {(e["vista"], e["campo"]): e for e in V.eixos_de_cor(celulas)}
    assert por_chave[("A", "excesso_cdi")]["extremo_simetrico"] == 0.10
    assert por_chave[("B", "excesso_cdi")]["extremo_simetrico"] == 0.30
    # coluna inteira ausente: o eixo sai `null`, nunca 0 (um extremo 0 pintaria tudo no passo 1)
    assert por_chave[("A", "pior_tri")]["extremo_simetrico"] is None
    assert por_chave[("A", "pior_tri")]["n_celulas_com_valor"] == 0
    assert por_chave[("A", "pior_tri")]["n_celulas"] == 2


def test_nenhuma_view_emite_cor(canonical_sintetico: Path) -> None:
    """Item 3 (**D-ai**): o exportador parou de emitir `cor_hex`. Cor é decisão de apresentação.

    A coluna existe no Parquet da figura (hex matplotlib da paleta placeholder da skill `dataviz`),
    o módulo do portal já pintava com a rampa da LDC e tinha teste provando que ignorava o hex —
    então o campo era uma segunda verdade de cor sem consumidor. O que fica é o canal **sem** cor:
    `hachura` e `conclusao_suprimida`.
    """
    resultado = _exportar(canonical_sintetico)
    for nome in (*VIEWS, NOME_META.removesuffix(".json")):
        caminho = resultado.pasta_da_tag / f"{nome}.json"
        assert "cor_hex" not in caminho.read_text(encoding="utf-8"), nome
    assert "cor_hex" not in V.CAMPOS_DA_CELULA
    assert "cor_hex" not in V.CAMPOS_DO_ESTILO

    timeline = json.loads(
        (resultado.pasta_da_tag / "regimes_timeline.json").read_text(encoding="utf-8")
    )
    estilos = timeline["estilo_por_rotulo"].values()
    assert estilos and all("hachura" in estilo for estilo in estilos)


# ═════════════════════════════════════════════════════════════════════════════
# 10 — Acervo real `data/canonical/` (padrão `Acervo`; LDC_IGNORAR_DATA=1 desliga)
# ═════════════════════════════════════════════════════════════════════════════

TAG_DO_ACERVO = "dev-2026-10-11"
N_CELULAS_DO_HEATMAP = 322
N_LINHAS_DO_RANKING = 72
N_PONTOS_DA_TIMELINE = 166
N_SERIES = 138
N_TRIMESTRES = 83
N_REFERENCIAS_DA_LENTE_CANONICA = 58
N_CELULAS_SUPRIMIDAS = 4
"""IMOB e IFIX (`n = 4`) na coluna `VIZINHOS_2026Q3` das 2 vistas que a têm."""


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (vazio, `0`, `false` e `nao` contam como desligada)."""
    return os.environ.get(VAR_IGNORAR_DATA, "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


def canonical_disponivel() -> bool:
    """Os artefatos que o exportador lê existem nesta máquina, e o manifesto também?"""
    if not X.caminho_do_manifesto().is_file():
        return False
    return all(caminho_canonical(nome).is_file() for nome in V.ARTEFATOS_LIDOS)


acervo_real = pytest.mark.skipif(
    ignorar_data_real() or not canonical_disponivel(),
    reason=f"data/canonical/ ausente ou {VAR_IGNORAR_DATA} ligada — {COMO_GERAR}",
)


@pytest.fixture(scope="module")
def exportacao_real(tmp_path_factory: pytest.TempPathFactory) -> X.ResultadoExportacao:
    """A exportação do acervo real para `tmp_path` — o teste **não** escreve em `data/`."""
    if ignorar_data_real() or not canonical_disponivel():
        pytest.skip("acervo real indisponível")
    destino = tmp_path_factory.mktemp("web-acervo")
    try:
        return X.exportar(tag=TAG_DO_ACERVO, destino=destino)
    except X.DatasetDivergente as erro:
        pytest.skip(f"`verify` do acervo reprovou — não é falha desta feature: {erro}")


@acervo_real
def test_acervo_contagens_sao_as_do_pipeline(exportacao_real: X.ResultadoExportacao) -> None:
    """As contagens do acervo: 322 células, 72 linhas de ranking, 166 pontos, 138 séries, 83 tri."""
    meta = json.loads((exportacao_real.pasta_da_tag / NOME_META).read_text(encoding="utf-8"))
    contagens = meta["contagens"]
    assert contagens["n_celulas_do_heatmap"] == N_CELULAS_DO_HEATMAP
    assert contagens["n_linhas_do_ranking"] == N_LINHAS_DO_RANKING
    assert contagens["n_pontos_da_timeline"] == N_PONTOS_DA_TIMELINE
    assert contagens["n_series_do_catalogo"] == N_SERIES
    assert contagens["n_trimestres"] == N_TRIMESTRES
    assert contagens["n_referencias_de_vizinhos"] == N_REFERENCIAS_DA_LENTE_CANONICA
    assert contagens["n_views"] == len(VIEWS)
    assert meta["artefatos_nao_publicaveis"] == ["internacional_pesos.parquet"]


@acervo_real
def test_acervo_tres_valores_conferidos_na_fonte(exportacao_real: X.ResultadoExportacao) -> None:
    """Os 3 valores de `AGENTS.md §15.9`, cada um contra o `relatorio_*.json` que o produziu."""
    pasta = exportacao_real.pasta_da_tag
    ler = lambda nome: json.loads((pasta / nome).read_text(encoding="utf-8"))  # noqa: E731
    fonte = lambda nome: json.loads(caminho_canonical(nome).read_text(encoding="utf-8"))  # noqa: E731

    # 1 — T-01, topo do ranking da V1 asof (F-022 → relatorio_metricas.json)
    esperado = fonte("relatorio_metricas.json")["regime_atual"]["ranking_v1_asof_2026Q3"][0]
    obtido = next(
        linha
        for linha in ler("ranking_atual.json")["rankings"]
        if "asof" in linha["lente_rotulo"] and linha["posicao"] == 1
    )
    assert obtido["asset_id"] == esperado["asset_id"] == "IDIV"
    assert obtido["n_obs"] == esperado["n_obs"] == 13
    assert obtido["excesso_cdi"] == round(esperado["excesso_cdi"], 4)
    assert obtido["erro_padrao_media"] == round(esperado["erro_padrao_media"], 4)

    # 2 — T-03, topo do ranking em T+1 (F-021 → relatorio_regimes_v3.json)
    esperado = fonte("relatorio_regimes_v3.json")["ranking_ativos_t_mais_1"]["ativos"][0]
    obtido = ler("vizinhos.json")["ranking_t_mais_1"][0]
    assert obtido["asset_id"] == esperado["asset_id"] == "INDX"
    assert obtido["n_obs"] == esperado["n"] == 8
    assert obtido["excesso_cdi"] == round(esperado["media"], 4)
    assert obtido["erro_padrao_media"] == round(esperado["erro_padrao"], 4)

    # 3 — T-06, corr(USDBRL, IBOV) nos 4 blocos, cada um com o seu n (F-026)
    blocos = fonte("relatorio_internacional.json")["hedge_cambial"]["stress_vs_nao_stress"][
        "blocos"
    ]
    for entrada in ler("internacional.json")["correlacoes"]:
        esperado = blocos[entrada["bloco"]]
        assert entrada["corr"] == round(esperado["correlacao"], 6)
        assert entrada["n_pares"] == esperado["n_pares"]
    assert {e["bloco"] for e in ler("internacional.json")["correlacoes"]} == set(blocos)


@acervo_real
def test_acervo_supressao_atinge_imob_e_ifix(exportacao_real: X.ResultadoExportacao) -> None:
    """`n < 5` hoje é IMOB e IFIX na coluna de vizinhos — com valor e com a flag."""
    celulas = json.loads(
        (exportacao_real.pasta_da_tag / "heatmap_regime_ativo.json").read_text(encoding="utf-8")
    )["celulas"]
    suprimidas = [c for c in celulas if c["conclusao_suprimida"]]
    assert len(suprimidas) == N_CELULAS_SUPRIMIDAS
    assert {c["asset_id"] for c in suprimidas} == {"IMOB", "IFIX"}
    assert all(c["n_obs"] == 4 for c in suprimidas)
    assert all(c["excesso_cdi"] is not None for c in suprimidas)
    assert all(c["hachura"] for c in suprimidas)


@acervo_real
def test_acervo_cabe_no_orcamento_e_e_deterministico(
    exportacao_real: X.ResultadoExportacao, tmp_path: Path
) -> None:
    """O conjunto real cabe em 400 KB e a segunda exportação dá os mesmos bytes."""
    assert exportacao_real.bytes_das_views <= LIMITE_DE_BYTES
    assert exportacao_real.bytes_gzip_totais < exportacao_real.bytes_totais
    segunda = X.exportar(tag=TAG_DO_ACERVO, destino=tmp_path / "segunda")
    assert {i["arquivo"]: i["sha256"] for i in segunda.arquivos} == {
        i["arquivo"]: i["sha256"] for i in exportacao_real.arquivos
    }


@acervo_real
def test_acervo_t01_responde_indeterminado_na_revised(
    exportacao_real: X.ResultadoExportacao,
) -> None:
    """A V1 `revised` responde **INDETERMINADO** em 2026Q3, com motivo e fallback rotulado."""
    respostas = json.loads(
        (exportacao_real.pasta_da_tag / "ranking_atual.json").read_text(encoding="utf-8")
    )["respostas"]
    revised = next(r for r in respostas if r["lente"] == "V1" and r["materializacao"] == "revised")
    assert revised["status_regime_v1"] == "INDETERMINADO"
    assert revised["motivo_indeterminado"]
    assert revised["e_fallback"] is True
    assert revised["quarter_perguntado"] == "2026Q3"
    assert revised["quarter_da_celula"] == "2026Q2"


@acervo_real
def test_acervo_nao_emite_nenhum_arquivo_dentro_de_data(
    exportacao_real: X.ResultadoExportacao,
) -> None:
    """A exportação do teste mora em `tmp_path`: nenhum byte foi escrito em `data/`."""
    assert "data" not in exportacao_real.destino.parts[-3:]
    assert (exportacao_real.pasta_da_tag / NOME_TIPOS_TS).is_file()
