"""F-028 — testes da página de limitações do Comitê (`docs/product/LIMITACOES-COMITE.md`).

**Classe B.** O artefato desta feature é um documento, não código: o teste é o portão que impede a
página de ir ao Comitê sem os blocos obrigatórios de **CA-112** e **sem os números medidos** —
porque uma página de limitações que erra um número é pior que nenhuma.

Três seções, nesta ordem de confiança:

| Seção | Sobre o quê | O que prova |
|---|---|---|
| **A** | estrutura | os 8 blocos obrigatórios existem, na ordem, e o aviso de topo está lá |
| **B** | conteúdo de CA-112 | `n`/erro-padrão, quebra estrutural, look-ahead, janela curta |
| **C** | **acervo real** | cada número citado é **o que o relatório publica**, não um valor à mão |

A seção C pula sem `data/canonical/` (mesmo padrão declarado de `test_canonical_regimes_v3.py` e
`test_processed_layer_conventions.py`): o `actions/checkout` do CI entrega a árvore sem `data/`.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "docs" / "product" / "LIMITACOES-COMITE.md"
CANONICAL = RAIZ / "data" / "canonical"

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"

#: Os 8 blocos que o Feature Contract de F-028 exige, na ordem em que têm de aparecer.
BLOCOS_OBRIGATORIOS = (
    "1. O que foi pedido",
    "2. Substituições de fonte",
    "3. Janelas próprias",
    "4. Convenções que mudam o número",
    "5. Look-ahead",
    "6. O que **não** está neste pacote",
    "7. Decisões que o Comitê",
    "8. Como reproduzir",
)

#: Faixa de tamanho do Feature Contract: página de 1 leitura, não relatório.
LINHAS_MINIMAS = 150
LINHAS_MAXIMAS = 250


@pytest.fixture(scope="module")
def texto() -> str:
    """O documento inteiro, lido com encoding explícito (`CLAUDE.md §4`)."""
    assert PAGINA.is_file(), f"a página de limitações não existe em {PAGINA}"
    return PAGINA.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Seção A — estrutura
# ─────────────────────────────────────────────────────────────────────────────


def test_a_pagina_existe_e_tem_tamanho_de_uma_pagina_de_leitura(texto: str) -> None:
    n = len(texto.rstrip("\n").split("\n"))
    assert LINHAS_MINIMAS <= n <= LINHAS_MAXIMAS, (
        f"{n} linhas: fora da faixa [{LINHAS_MINIMAS}, {LINHAS_MAXIMAS}] do Feature Contract"
    )


def test_a_os_oito_blocos_obrigatorios_estao_presentes_e_na_ordem(texto: str) -> None:
    posicoes = []
    for bloco in BLOCOS_OBRIGATORIOS:
        assert bloco in texto, f"bloco obrigatório ausente: {bloco!r}"
        posicoes.append(texto.index(bloco))
    assert posicoes == sorted(posicoes), f"blocos fora de ordem: {posicoes}"


def test_a_aviso_de_topo_declara_a_especificacao_nao_congelada(texto: str) -> None:
    """Enquanto ADR-001 estiver em Proposta, o aviso é a primeira coisa que o leitor vê."""
    topo = texto[: texto.index("1. O que foi pedido")]
    assert "não está congelada" in topo
    assert "ADR-001" in topo and "Proposta" in topo
    assert "material de discussão" in topo
    # Anti-SPEC §10.2.10: a página não pode prometer previsão em lugar nenhum.
    assert "nada aqui é previsão" in topo


def test_a_pagina_e_para_gestor_sem_jargao_de_codigo(texto: str) -> None:
    """Sem nome de módulo, de classe ou de função no corpo — é documento de Comitê."""
    proibidos = (
        "apps/pipeline",
        "packages/shared",
        "pandera",
        "pytest",
        "def ",
        "parquet",
        "DataFrame",
    )
    corpo = texto.lower()
    encontrados = [p for p in proibidos if p.lower() in corpo]
    assert not encontrados, f"jargão de código na página do Comitê: {encontrados}"


def test_a_declara_a_audiencia_e_o_que_cobre(texto: str) -> None:
    cabecalho = texto[: texto.index("⚠️")]
    assert "Alexandre Kaercher" in cabecalho
    assert "Comitê de Alocação" in cabecalho
    assert "CA-112" in cabecalho


# ─────────────────────────────────────────────────────────────────────────────
# Seção B — o conteúdo que CA-112 enumera
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("rotulo", "exigidos"),
    [
        ("n pequeno e erro-padrão", ("erro-padrão", "2,8 pontos percentuais", "4,2 pp")),
        ("quebra estrutural 2006-2008 × pós-2016", ("Quebra estrutural", "pós-2016", "19%")),
        ("resultado do teste de look-ahead", ("33,33%", "25%", "descritiva, não operacional")),
        ("séries de janela curta", ("ICON", "IMOB", "IFIX", "2011")),
        ("índice não é investível sem fricção", ("Índice não é ativo investível", "corretagem")),
        ("substituições de fonte", ("Tesouro Direto", "ANBIMA", "FRED")),
        ("supressão por n baixo", ("n < 8", "n < 5", "sem conclusão")),
    ],
)
def test_b_ca112_cada_conteudo_obrigatorio_aparece(
    texto: str, rotulo: str, exigidos: tuple[str, ...]
) -> None:
    faltando = [e for e in exigidos if e not in texto]
    assert not faltando, f"CA-112 — {rotulo}: faltando {faltando}"


def test_b_as_substituicoes_de_fonte_nomeiam_as_cinco_de_ca117(texto: str) -> None:
    """CA-117: ETTJ→Tesouro, swap DI morto, "DataFit" inexistente, FII 2019+, IFIX 2011+."""
    assert "ETTJ" in texto and "Tesouro Direto" in texto
    assert "swap DI" in texto and "30/09/2019" in texto
    assert '"ANBIMA DataFit" não existe' in texto
    assert "2019" in texto and "FII por segmento" in texto
    assert "IFIX" in texto and "2011" in texto


def test_b_declara_que_o_fii_segmentado_ficou_fora_do_pacote(texto: str) -> None:
    """F-012 não rodou: a página tem de dizer "fora", não "entregue com janela curta"."""
    assert "FORA do pacote" in texto
    assert "não foi executada" in texto


def test_b_lista_o_que_nao_esta_no_pacote(texto: str) -> None:
    corpo = texto.lower()
    for item in ("backtest", "previsão", "top 5", "risco-país", "termos de troca", "v2"):
        assert item in corpo, f"ausente da lista de exclusões: {item!r}"


def test_b_as_decisoes_a_ratificar_trazem_o_custo_da_virada(texto: str) -> None:
    """As 8 originais + D-i/D-s/D-t/D-u, cada uma com o que muda se o Comitê discordar."""
    for decisao in ("D1", "D3", "D5", "D6", "D12", "L1", "L2", "L4", "D-i", "D-s", "D-t", "D-u"):
        assert f"**{decisao}**" in texto, f"decisão a ratificar ausente: {decisao}"
    assert "O que muda se o Comitê discordar" in texto


def test_b_cita_os_relatorios_como_fonte_dos_numeros(texto: str) -> None:
    """Todo número vem do relatório da rodada, não de um context pack."""
    for relatorio in (
        "relatorio_retornos.json",
        "relatorio_macro.json",
        "relatorio_asof.json",
        "relatorio_regimes_v1.json",
        "relatorio_regimes_v3.json",
        "relatorio_alinhamento.json",
    ):
        assert relatorio in texto, f"a página não cita {relatorio}"


def test_b_nao_usa_linguagem_preditiva(texto: str) -> None:
    """Anti-SPEC §10.2.10. "vai render"/"vai performar" só aparece como negação explícita."""
    for padrao in (r"vai render", r"vai performar", r"deve render"):
        for achado in re.finditer(padrao, texto, flags=re.IGNORECASE):
            janela = texto[max(0, achado.start() - 90) : achado.start()]
            assert re.search(r"nunca|não|nenhum", janela, flags=re.IGNORECASE), (
                f"linguagem preditiva sem negação: ...{janela[-60:]}{achado.group()}"
            )


def test_b_como_reproduzir_diz_que_o_comando_unico_e_f029(texto: str) -> None:
    """F-029 está em curso: a página não pode prometer um comando que ainda não existe."""
    reproduzir = texto[texto.index("8. Como reproduzir") :]
    assert "F-029" in reproduzir
    assert "reconstruir-dataset.md" in reproduzir
    assert "sha256" in reproduzir


# ─────────────────────────────────────────────────────────────────────────────
# Seção C — acervo real: os números citados são os publicados
# ─────────────────────────────────────────────────────────────────────────────


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (vazio, `0`, `false` e `nao` contam como desligada)."""
    return os.environ.get(VAR_IGNORAR_DATA, "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


RELATORIOS = (
    "relatorio_retornos.json",
    "relatorio_macro.json",
    "relatorio_asof.json",
    "relatorio_regimes_v1.json",
    "relatorio_regimes_v3.json",
    "relatorio_alinhamento.json",
)


def acervo_disponivel() -> bool:
    """Os relatórios de que a seção C depende existem nesta máquina?"""
    return all((CANONICAL / nome).is_file() for nome in RELATORIOS)


pulo_do_acervo = pytest.mark.skipif(
    ignorar_data_real() or not acervo_disponivel(),
    reason=(
        "seção C confere a página contra data/canonical/relatorio_*.json. Reconstrua o canônico e "
        f"deixe {VAR_IGNORAR_DATA} desligada."
    ),
)


@pytest.fixture(scope="module")
def relatorios() -> dict[str, dict]:
    """Os relatórios publicados, como estão em disco."""
    return {nome: json.loads((CANONICAL / nome).read_text(encoding="utf-8")) for nome in RELATORIOS}


@pulo_do_acervo
def test_c_o_numero_do_look_ahead_e_o_calculado_por_f018_f019(
    texto: str, relatorios: dict[str, dict]
) -> None:
    """CA-112: o % citado é o medido, e o limiar de CA-074 é o publicado."""
    div = relatorios["relatorio_regimes_v1.json"]["divergencia_asof_vs_revised"]
    pct = div["pct_que_trocam"] * 100
    assert f"{pct:.2f}".replace(".", ",") in texto, f"a página não cita {pct:.2f}% de troca"
    assert f"{div['trimestres_que_trocam']} de {div['trimestres_comparaveis']}" in texto
    assert f"{div['limiar_inoperante'] * 100:.0f}%" in texto
    # e afirma a consequência, não só o número
    assert div["modelo_operacional"] is False
    assert "descritiva, não operacional" in texto


@pulo_do_acervo
def test_c_o_gate_de_publicacao_citado_e_o_que_esta_em_disco(
    texto: str, relatorios: dict[str, dict]
) -> None:
    gate = relatorios["relatorio_regimes_v3.json"]["gate_de_publicacao"]
    espec = relatorios["relatorio_regimes_v1.json"]["especificacao"]
    assert gate["publicavel"] is False and espec["especificacao_congelada"] is False
    assert "`publicavel = false`" in texto
    assert "`especificacao_congelada = false`" in texto


@pulo_do_acervo
def test_c_as_janelas_proprias_citadas_sao_as_medidas(
    texto: str, relatorios: dict[str, dict]
) -> None:
    """ICON, IMOB e IFIX: a contagem de trimestres com retorno vem do relatório."""
    por_ativo = {a["asset_id"]: a for a in relatorios["relatorio_retornos.json"]["ativos"]}
    for asset_id in ("ICON", "IMOB", "IFIX"):
        n = por_ativo[asset_id]["n_retornos"]
        assert f"**{n}**" in texto, f"{asset_id}: a página não cita n_retornos = {n}"
    assert por_ativo["IBOV"]["n_retornos"] == 82
    assert "**82**" in texto


@pulo_do_acervo
def test_c_o_n_por_regime_citado_e_o_da_distribuicao_publicada(
    texto: str, relatorios: dict[str, dict]
) -> None:
    grupos = relatorios["relatorio_regimes_v1.json"]["distribuicao"]["por_grupo"]
    for rotulo, grupo in grupos.items():
        assert f"**{grupo['n']}**" in texto, f"{rotulo}: n = {grupo['n']} ausente da página"
    assert "**indeterminados**" in texto


@pulo_do_acervo
def test_c_os_215_ffill_da_b3_e_a_janela_do_cdi_estao_citados(
    texto: str, relatorios: dict[str, dict]
) -> None:
    d_h = relatorios["relatorio_alinhamento.json"]["decisao_d_h"]
    assert f"**{d_h['celulas_com_ffill']} células" in texto
    assert f"em {d_h['series_com_ffill']} séries" in texto
    assert f"**{d_h['trimestres_com_ffill']} trimestres**" in texto
    janela = relatorios["relatorio_retornos.json"]["convencoes"][
        "janela_do_cdi_vs_caminho_do_ativo"
    ]
    assert "599" in janela and "599 de 1.857" in texto
    assert "0,1575" in texto


@pulo_do_acervo
def test_c_os_indeterminados_e_a_crise_de_2008_estao_citados(
    texto: str, relatorios: dict[str, dict]
) -> None:
    v1 = relatorios["relatorio_regimes_v1.json"]
    assert f"**{v1['regimes_v1']['classificados']} dos 83 trimestres**" in texto
    assert "crise de 2008 fica fora do eixo de crescimento" in texto
    recuperados = relatorios["relatorio_macro.json"]["sensibilidade_ibcbr_gap"][
        "trimestres_recuperados"
    ]
    assert f"**{recuperados}** trimestres" in texto


@pulo_do_acervo
def test_c_a_v3_citada_tem_5_features_e_77_referencias(
    texto: str, relatorios: dict[str, dict]
) -> None:
    v3 = relatorios["relatorio_regimes_v3.json"]
    assert v3["features"]["n_features"] == 5
    assert "**5 variáveis, não 6**" in texto
    assert f"**{v3['cobertura']['com_vetor_completo']} dos 83**" in texto
    # a variante sem look-ahead dá a mesma lista — é o achado que a página afirma
    assert v3["sensibilidade"]["somente_passado_vs_descritiva"]["jaccard"] == 1.0
    assert "exatamente a mesma" in texto
    # e a tabela de contrato perde 4 dos 8 vizinhos de 2026Q3
    perda = v3["divergencia_contrato_vs_completo"]["2026Q3"]
    assert f"**{perda['n_a'] - perda['em_comum']} dos {perda['n_a']} vizinhos" in texto


@pulo_do_acervo
def test_c_o_erro_padrao_citado_e_o_medido_no_ranking(
    texto: str, relatorios: dict[str, dict]
) -> None:
    ativos = relatorios["relatorio_regimes_v3.json"]["ranking_ativos_t_mais_1"]["ativos"]
    primeiro = ativos[0]
    assert f"**+{primeiro['media'] * 100:.2f}%**".replace(".", ",") in texto
    assert f"**{primeiro['erro_padrao'] * 100:.2f} pp**".replace(".", ",") in texto
    # o maior erro-padrão entre as linhas publicáveis e o maior de todos (uma suprimida)
    publicaveis = [a for a in ativos if not a["conclusao_suprimida"]]
    for ep in (
        min(a["erro_padrao"] for a in ativos),
        max(a["erro_padrao"] for a in publicaveis),
        max(a["erro_padrao"] for a in ativos),
    ):
        assert f"**{ep * 100:.2f} pp**".replace(".", ",") in texto, f"erro-padrão {ep} não citado"
    suprimidos = {a["asset_id"] for a in ativos if a["conclusao_suprimida"]}
    assert suprimidos == {"IFIX", "IMOB"}
    assert "**IFIX e IMOB** (n = 4, suprimidos)" in texto


@pulo_do_acervo
def test_c_o_tamanho_da_base_citado_e_o_publicado(texto: str, relatorios: dict[str, dict]) -> None:
    arq = relatorios["relatorio_retornos.json"]["asset_returns_quarterly"]
    assert f"**{arq['ativos']} ativos" in texto
    assert f"{arq['linhas']:,}".replace(",", ".") in texto
    assert f"{arq['trimestres']} trimestres**" in texto
    macro = relatorios["relatorio_macro.json"]["macro_quarterly"]
    assert f"**{macro['colunas']} variáveis macro" in texto
    nulos = relatorios["relatorio_retornos.json"]["asset_returns_quarterly"]["nulos_por_coluna"]
    assert f"**{nulos['is_total_return']} linhas**" in texto


@pulo_do_acervo
def test_c_os_hashes_citados_sao_os_das_tabelas_em_disco(
    texto: str, relatorios: dict[str, dict]
) -> None:
    """Hash diferente = outro dataset: os prefixos citados têm de ser os publicados."""
    esperados = {
        "macro": relatorios["relatorio_macro.json"]["macro_quarterly"]["sha256"],
        "asof": relatorios["relatorio_asof.json"]["macro_quarterly_asof"]["sha256"],
        "retornos": relatorios["relatorio_retornos.json"]["asset_returns_quarterly"]["sha256"],
        "regimes_v1": relatorios["relatorio_regimes_v1.json"]["regimes_v1"]["sha256"],
        "v3": relatorios["relatorio_regimes_v3.json"]["regime_neighbors_v3"]["sha256"],
    }
    for rotulo, sha in esperados.items():
        assert f"`{sha[:8]}…`" in texto, f"{rotulo}: prefixo {sha[:8]} não citado na página"


@pulo_do_acervo
def test_c_zero_violacao_de_divulgacao_e_o_que_a_pagina_afirma(
    texto: str, relatorios: dict[str, dict]
) -> None:
    anti = relatorios["relatorio_asof.json"]["anti_look_ahead"]
    assert anti["celulas_com_divulgacao_depois_do_fim_de_T"] == 0
    assert f"**0 violações em {anti['celulas_com_date_obs']:,}".replace(",", ".") in texto
    # o piso declarado (safra única) também tem de estar na página
    assert "vintage_unico" in relatorios["relatorio_asof.json"]["limitacoes"]
    assert "uma única safra por série" in texto
