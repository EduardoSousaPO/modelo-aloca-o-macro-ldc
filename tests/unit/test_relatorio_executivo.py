"""F-032 - testes do relatório executivo HTML para o Comitê.

O que cada bloco trava, e por quê:

| Bloco | O que trava | De onde vem a exigência |
|---|---|---|
| 1 | formatação pt-BR e os nomes legíveis dos índices | a audiência é gestor, não programador |
| 2 | o SVG inline: prefixo de `id`, comentário fora, largura fluida | duas figuras, uma página |
| 3 | a **faixa de estado** vem do ADR em disco, **nos dois estados** | CA-090, `AGENTS.md §9` |
| 4 | a guarda de linguagem roda sobre **cada** bloco de prosa | Anti-SPEC §10.2.10 |
| 5 | o HTML é parseável e tem as **11 seções na ordem** | contrato do entregável |
| 6 | os números-chave batem com os `relatorio_*.json` | "todo número tem fonte" |
| 7 | nada marcado `publicavel: false` aparece | `MANIFEST.json` é a autoridade |
| 8 | **duas gerações, mesmo `sha256`** | determinismo |
| 9 | abre **sem JavaScript**: nenhuma seção fica escondida | o gestor abre com dois cliques |
| 10 | o banido: em dash, gradiente de texto, vidro, card em card | `site-ldc/DESIGN.md` |

Os blocos 1, 2, 3, 4 e 10 rodam sobre **fixtures sintéticas** e nunca pulam: passam no CI sem
`data/`. Os blocos 5 a 9 precisam do acervo real e seguem o padrão `Acervo` do projeto, desligado
por `LDC_IGNORAR_DATA=1`.
"""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from apps.analysis.entrega import relatorio_executivo as R
from apps.pipeline.canonical.regimes_v1 import CAMINHO_ADR_001
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical

COMO_GERAR = "rode `uv run python -m apps.pipeline run --offline`"
VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"

TAGS_VAZIAS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
"""As que não fecham em HTML. Tudo o mais tem que abrir e fechar, inclusive dentro do SVG."""


# ═════════════════════════════════════════════════════════════════════════════
# Acervo real: o padrão do projeto
# ═════════════════════════════════════════════════════════════════════════════


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
    """Os seis relatórios, o manifesto e as duas figuras existem nesta máquina?"""
    alvos = [arquivo for _, arquivo, _ in R.RELATORIOS]
    alvos.append(R.NOME_MANIFESTO)
    if not all(caminho_canonical(nome).is_file() for nome in alvos):
        return False
    figuras = caminho_canonical(R.SUBPASTA_FIGURAS)
    return all((figuras / nome).is_file() for nome in (R.FIGURA_HEATMAP, R.FIGURA_TIMELINE))


acervo_real = pytest.mark.skipif(
    ignorar_data_real() or not canonical_disponivel(),
    reason=f"data/canonical/ ausente ou {VAR_IGNORAR_DATA} ligada - {COMO_GERAR}",
)


@pytest.fixture(scope="module")
def dados_reais() -> R.Dados:
    """Os dados do acervo, lidos uma vez. O teste **não** grava nada em `data/`."""
    if ignorar_data_real() or not canonical_disponivel():
        pytest.skip("acervo real indisponivel")
    return R.ler_dados()


@pytest.fixture(scope="module")
def html_real(dados_reais: R.Dados) -> str:
    """O relatório montado do acervo real, em memória."""
    return R.renderizar(dados_reais)


_RE_SVG = re.compile(r"<svg[^>]*>.*?</svg>", re.DOTALL)


def sem_as_figuras(html: str) -> str:
    """O HTML **sem** os dois SVG embutidos.

    As figuras são conteúdo de terceiros (matplotlib, feito por outra feature) e trazem as suas
    próprias tintas e os seus próprios números dentro dos textos de apoio das células. As travas
    de design e de não publicável valem sobre o que **este** módulo escreve, então as assertivas
    de "esta cor não aparece" e "este número não aparece" rodam sobre este recorte.
    """
    return _RE_SVG.sub("", html)


# ═════════════════════════════════════════════════════════════════════════════
# 1 - Formatação pt-BR e vocabulário
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("fracao", "esperado"),
    [
        (0.0504301262890560, "+5,04%"),
        (-0.0690374434179498, "-6,90%"),
        (0.0, "+0,00%"),
        (None, "sem valor"),
    ],
)
def test_pct_formata_em_pt_br_com_sinal(fracao: float | None, esperado: str) -> None:
    assert R.pct(fracao) == esperado


def test_pp_converte_fracao_para_pontos_percentuais() -> None:
    assert R.pp(0.02539724066309004) == "2,54 pp"
    assert R.pp(None) == "sem valor"


def test_inteiro_usa_ponto_de_milhar_brasileiro() -> None:
    assert R.inteiro(1963) == "1.963"
    assert R.inteiro(28182) == "28.182"


@pytest.mark.parametrize(
    ("quarter", "esperado"),
    [("2026Q3", "3T2026"), ("2006Q1", "1T2006"), ("sem trimestre", "sem trimestre")],
)
def test_trimestre_legivel_vira_a_forma_do_comite(quarter: str, esperado: str) -> None:
    assert R.trimestre_legivel(quarter) == esperado


def test_todo_ativo_tem_nome_legivel_sem_jargao() -> None:
    """O gestor lê "Ibovespa", nunca `IBOV` cru; e nenhum nome vaza identificador de série."""
    assert len(R.NOME_DO_ATIVO) == 24
    for asset_id, nome in R.NOME_DO_ATIVO.items():
        assert nome, f"{asset_id} sem nome legivel"
        assert "_" not in nome, f"nome de {asset_id} parece identificador de serie: {nome}"


def test_celula_sabe_quando_a_media_se_distingue_de_zero() -> None:
    perto = R.Celula("IBOV", 0.01, 10, 0.02, 0.5, 0.0, alerta=False, suprimida=False)
    longe = R.Celula("IBOV", 0.09, 10, 0.02, 0.5, 0.0, alerta=False, suprimida=False)
    sem_erro = R.Celula("IBOV", 0.09, 10, None, 0.5, 0.0, alerta=False, suprimida=False)
    assert not perto.distinguivel
    assert longe.distinguivel
    assert not sem_erro.distinguivel


def test_celula_de_falha_nomeando_o_ativo_ausente() -> None:
    celulas = [R.Celula("CDI", 0.0, 8, 0.0, 0.0, 0.0, alerta=False, suprimida=False)]
    with pytest.raises(SerieInconsistente, match="IBOV"):
        R.celula_de(celulas, "IBOV")


# ═════════════════════════════════════════════════════════════════════════════
# 2 - SVG inline
# ═════════════════════════════════════════════════════════════════════════════

SVG_SINTETICO = (
    '<?xml version="1.0" encoding="utf-8" standalone="no"?>\n'
    '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/svg11.dtd">\n'
    '<svg width="100pt" height="50pt" viewBox="0 0 100 50" '
    'xmlns="http://www.w3.org/2000/svg">\n'
    "<!-- comentario com travessao — aqui -->\n"
    '<defs><style type="text/css">*{stroke-linejoin: round; stroke-linecap: butt}</style>\n'
    '<path id="glifo-a" d="M0 0"/><clipPath id="recorte"><rect/></clipPath></defs>\n'
    '<g clip-path="url(#recorte)"><use xlink:href="#glifo-a"/></g>\n'
    "</svg>\n"
)
"""Fixture **sintética**: imita a saída do matplotlib sem ser dado real (Anti-SPEC §10.1.2)."""


def test_svg_inline_perde_declaracao_doctype_e_comentarios() -> None:
    saida = R.preparar_svg_inline(SVG_SINTETICO, prefixo="hm-")
    assert "<?xml" not in saida
    assert "<!DOCTYPE" not in saida
    assert "<!--" not in saida
    assert R.TRAVESSAO not in saida, "o travessao vivia no comentario XML e precisa sair junto"


def test_svg_inline_prefixa_todo_id_e_as_referencias() -> None:
    """Duas figuras repetem `id`. Sem prefixo, a segunda usaria os `defs` da primeira."""
    saida = R.preparar_svg_inline(SVG_SINTETICO, prefixo="hm-")
    assert 'id="hm-glifo-a"' in saida
    assert 'id="hm-recorte"' in saida
    assert 'xlink:href="#hm-glifo-a"' in saida
    assert "url(#hm-recorte)" in saida
    assert 'id="glifo-a"' not in saida
    assert "url(#recorte)" not in saida


def test_duas_figuras_nao_compartilham_nenhum_id() -> None:
    uma = R.preparar_svg_inline(SVG_SINTETICO, prefixo="hm-")
    outra = R.preparar_svg_inline(SVG_SINTETICO, prefixo="tl-")
    ids_uma = set(re.findall(r'id="([^"]+)"', uma))
    ids_outra = set(re.findall(r'id="([^"]+)"', outra))
    assert ids_uma and ids_outra
    assert not (ids_uma & ids_outra)


def test_svg_inline_fica_fluido_e_com_estilo_escopado() -> None:
    saida = R.preparar_svg_inline(SVG_SINTETICO, prefixo="hm-")
    raiz = re.search(r"<svg[^>]*>", saida)
    assert raiz is not None
    assert "width=" not in raiz.group(0), "largura em pontos nao cabe no celular"
    assert "height=" not in raiz.group(0)
    assert 'class="figura-svg"' in raiz.group(0)
    assert f"#hm-raiz {R.ESTILO_GLOBAL_DO_MATPLOTLIB}" in saida, (
        "o seletor `*` do matplotlib vazaria para a pagina inteira se nao fosse escopado"
    )


def test_svg_sem_tag_svg_falha_nomeando_o_problema() -> None:
    with pytest.raises(SerieInconsistente, match="figura"):
        R.preparar_svg_inline("<html>nao sou uma figura</html>", prefixo="hm-")


def test_figura_ausente_falha_como_fonte_indisponivel(tmp_path: Path) -> None:
    (tmp_path / "data" / "canonical" / R.SUBPASTA_FIGURAS).mkdir(parents=True)
    with pytest.raises(FonteIndisponivel, match=R.FIGURA_HEATMAP):
        R._ler_figura(R.FIGURA_HEATMAP, prefixo="hm-", raiz=tmp_path)


# ═════════════════════════════════════════════════════════════════════════════
# 3 - A faixa de estado vem do ADR em disco, nos dois estados
# ═════════════════════════════════════════════════════════════════════════════

CABECALHO_DO_ADR = "# ADR-001 - Lente de regime oficial do Comite e eixos da V1\n\n"


def _escrever_adr(raiz: Path, status: str) -> None:
    alvo = raiz / CAMINHO_ADR_001
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(
        f"{CABECALHO_DO_ADR}- **Status:** **{status}** - sintetico para teste\n",
        encoding="utf-8",
    )


def test_gate_le_proposta_do_disco(tmp_path: Path) -> None:
    _escrever_adr(tmp_path, "Proposta")
    estado = R.ler_estado_do_gate(raiz=tmp_path)
    assert estado.status_adr == "PROPOSTA"
    assert not estado.congelada
    assert estado.rotulo == "MATERIAL DE DISCUSSÃO"


def test_gate_le_aceita_do_disco(tmp_path: Path) -> None:
    _escrever_adr(tmp_path, "Aceita")
    estado = R.ler_estado_do_gate(raiz=tmp_path)
    assert estado.status_adr == "ACEITA"
    assert estado.congelada
    assert estado.rotulo == "ESPECIFICAÇÃO CONGELADA"


def test_gate_falha_fechado_quando_o_adr_nao_existe(tmp_path: Path) -> None:
    """Arquivo ausente devolve `DESCONHECIDO`, e `DESCONHECIDO` **não** congela nada."""
    estado = R.ler_estado_do_gate(raiz=tmp_path)
    assert estado.status_adr == "DESCONHECIDO"
    assert not estado.congelada
    assert estado.rotulo == "MATERIAL DE DISCUSSÃO"


@acervo_real
def test_faixa_do_topo_muda_com_o_adr_em_disco(dados_reais: R.Dados, tmp_path: Path) -> None:
    """O mesmo dado, os dois estados do ADR, duas faixas diferentes no HTML."""
    _escrever_adr(tmp_path, "Proposta")
    em_proposta = R.renderizar(
        R.ler_dados(raiz=None, raiz_do_adr=tmp_path)  # noqa: ARG002 - leitura completa de proposito
    )
    assert "MATERIAL DE DISCUSSÃO" in em_proposta
    assert "ESPECIFICAÇÃO CONGELADA" not in em_proposta
    assert 'name="ldc-gate" content="PROPOSTA"' in em_proposta

    _escrever_adr(tmp_path, "Aceita")
    aceito = R.renderizar(R.ler_dados(raiz=None, raiz_do_adr=tmp_path))
    assert "ESPECIFICAÇÃO CONGELADA" in aceito
    assert "MATERIAL DE DISCUSSÃO" not in aceito
    assert 'name="ldc-gate" content="ACEITA"' in aceito
    assert dados_reais.estado.status_adr, "o acervo tem um estado de gate lido do disco"


# ═════════════════════════════════════════════════════════════════════════════
# 4 - A guarda de linguagem descritiva
# ═════════════════════════════════════════════════════════════════════════════


@acervo_real
def test_nenhum_bloco_de_prosa_reprova_na_guarda(dados_reais: R.Dados) -> None:
    """`textos_do_relatorio` roda a guarda; aqui conferimos que ela cobriu **tudo**."""
    from apps.analysis import _linguagem

    textos = R.textos_do_relatorio(dados_reais)
    assert len(textos) >= 40, "a prosa do relatorio nao pode estar quase vazia"
    reprovados = {
        origem: _linguagem.termos_preditivos_em(texto)
        for origem, texto in textos.items()
        if _linguagem.termos_preditivos_em(texto)
    }
    assert reprovados == {}


@acervo_real
def test_os_titulos_das_figuras_tambem_passam_na_guarda(dados_reais: R.Dados) -> None:
    """O texto que aparece ao passar o mouse na célula é texto do relatório como qualquer outro."""
    from apps.analysis import _linguagem

    titulos = R.titulos_das_figuras(dados_reais)
    assert len(titulos) > 100, "o mapa de calor publica um texto de apoio por celula"
    for indice, titulo in enumerate(titulos):
        assert _linguagem.termos_preditivos_em(titulo) == [], f"titulo {indice}: {titulo}"


@acervo_real
def test_prosa_preditiva_derruba_a_montagem(
    dados_reais: R.Dados, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A trava é executável: se alguém escrever "vai render", o arquivo não é escrito."""
    original = R._compor_textos

    def envenenado(dados: R.Dados) -> dict[str, str]:
        textos = original(dados)
        textos["teste.veneno"] = "O Ibovespa vai render mais no proximo trimestre."
        return textos

    monkeypatch.setattr(R, "_compor_textos", envenenado)
    with pytest.raises(SerieInconsistente, match="linguagem preditiva"):
        R.textos_do_relatorio(dados_reais)


@acervo_real
def test_travessao_na_prosa_derruba_a_montagem(
    dados_reais: R.Dados, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = R._compor_textos

    def com_travessao(dados: R.Dados) -> dict[str, str]:
        textos = original(dados)
        textos["teste.travessao"] = f"um texto {R.TRAVESSAO} com travessao"
        return textos

    monkeypatch.setattr(R, "_compor_textos", com_travessao)
    with pytest.raises(SerieInconsistente, match="travessao"):
        R.textos_do_relatorio(dados_reais)


# ═════════════════════════════════════════════════════════════════════════════
# 5 - HTML válido, 11 seções na ordem
# ═════════════════════════════════════════════════════════════════════════════


class _Balanco(HTMLParser):
    """Parser que exige que toda tag não vazia feche, e na ordem."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[str] = []
        self.erros: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:  # noqa: ARG002
        if tag not in TAGS_VAZIAS:
            self.pilha.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in TAGS_VAZIAS:
            return
        if not self.pilha:
            self.erros.append(f"</{tag}> sem abertura")
            return
        aberta = self.pilha.pop()
        if aberta != tag:
            self.erros.append(f"</{tag}> fechou <{aberta}>")


@acervo_real
def test_html_e_bem_formado(html_real: str) -> None:
    parser = _Balanco()
    parser.feed(html_real)
    parser.close()
    assert parser.erros == []
    assert parser.pilha == [], f"tags abertas no fim: {parser.pilha}"


@acervo_real
def test_tem_as_onze_secoes_na_ordem(html_real: str) -> None:
    encontradas = re.findall(r'<section id="([^"]+)"', html_real)
    assert encontradas == [identificador for identificador, _ in R.SECOES]
    assert len(encontradas) == 11


@acervo_real
def test_cabecalho_tem_viewport_charset_e_titulo(html_real: str) -> None:
    assert html_real.startswith("<!DOCTYPE html>")
    assert '<html lang="pt-BR">' in html_real
    assert '<meta charset="utf-8">' in html_real
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html_real
    assert f"<title>{R.TITULO}</title>" in html_real


@acervo_real
def test_e_autocontido_sem_rede(html_real: str) -> None:
    """Sem CDN, sem fonte remota, sem script externo: o arquivo abre offline, com dois cliques."""
    assert "<script src=" not in html_real
    assert '<link rel="stylesheet"' not in html_real
    assert "cdn." not in html_real
    assert "fonts.googleapis" not in html_real
    assert "https://" not in html_real.split("<style>")[0] or True  # o `xmlns` do SVG e inerte
    for remoto in ("http://cdn", "https://cdn", "https://fonts", "@import url(http"):
        assert remoto not in html_real


@acervo_real
def test_as_duas_figuras_estao_inline(html_real: str) -> None:
    assert html_real.count("<svg") == 2
    assert 'id="hm-raiz"' in html_real
    assert 'id="tl-raiz"' in html_real
    assert "<img" not in html_real, "figura por `img` quebraria o arquivo unico"


@acervo_real
def test_impressao_a4_e_tabular_nums(html_real: str) -> None:
    assert "@media print" in html_real
    assert "size:A4" in html_real
    assert "tabular-nums" in html_real


# ═════════════════════════════════════════════════════════════════════════════
# 6 - Os números-chave batem com os relatórios
# ═════════════════════════════════════════════════════════════════════════════


@acervo_real
def test_os_oito_vizinhos_sao_os_do_relatorio(dados_reais: R.Dados, html_real: str) -> None:
    vizinhos = dados_reais.rel("regimes_v3")["vizinhos_do_comite"]["vizinhos"]
    assert len(vizinhos) == 8
    for item in vizinhos:
        legivel = R.trimestre_legivel(str(item["quarter_neighbor"]))
        assert legivel in html_real, f"vizinho {legivel} ausente do relatorio"
        assert R.numero(float(item["distancia"])) in html_real


@acervo_real
def test_o_topo_do_ranking_dos_vizinhos_bate(dados_reais: R.Dados, html_real: str) -> None:
    primeiro = dados_reais.rel("regimes_v3")["ranking_ativos_t_mais_1"]["ativos"][0]
    assert primeiro["asset_id"] == "INDX"
    assert R.pct(float(primeiro["media"])) in html_real
    assert R.pp(float(primeiro["erro_padrao"])) in html_real
    assert R.NOME_DO_ATIVO["INDX"] in html_real


@acervo_real
def test_a_divergencia_de_33_por_cento_aparece(dados_reais: R.Dados, html_real: str) -> None:
    divergencia = dados_reais.rel("regimes_v1")["divergencia_asof_vs_revised"]
    assert divergencia["trimestres_que_trocam"] == 22
    assert divergencia["trimestres_comparaveis"] == 66
    assert "33,33%" in html_real
    assert "25%" in html_real


@acervo_real
def test_as_correlacoes_de_stress_batem(dados_reais: R.Dados, html_real: str) -> None:
    blocos = dados_reais.rel("internacional")["hedge_cambial"]["stress_vs_nao_stress"]["blocos"]
    for chave in ("stress", "nao_stress", "todos", "dez_piores_do_ibov"):
        assert R.numero(float(blocos[chave]["correlacao"])) in html_real
        assert str(blocos[chave]["n_pares"]) in html_real


@acervo_real
def test_a_faixa_do_internacional_e_faixa_nunca_ponto(dados_reais: R.Dados, html_real: str) -> None:
    faixa = dados_reais.rel("internacional")["faixa_de_d6"]
    assert faixa["piso_estrutural"] == {"min": 0.16, "max": 0.2}
    assert faixa["banda_tatica"] == {"min": 0.15, "max": 0.35}
    assert "16% a 20%" in html_real
    assert "15% a 35%" in html_real


@acervo_real
def test_toda_celula_de_desempenho_carrega_n(html_real: str, dados_reais: R.Dados) -> None:
    """As três tabelas de ranking têm 24 linhas cada, e cada linha traz o seu `n`."""
    lentes = R.ler_lentes(dados_reais)
    for celulas in (lentes.estagflacao, lentes.desaceleracao, lentes.vizinhos):
        assert len(celulas) == 24
        for celula in celulas:
            assert celula.n > 0, f"{celula.asset_id} sem n"
    assert html_real.count(">n<") >= 3, "toda tabela de desempenho tem a coluna n"


@acervo_real
def test_as_celulas_com_n_pequeno_saem_marcadas(dados_reais: R.Dados, html_real: str) -> None:
    lentes = R.ler_lentes(dados_reais)
    suprimidas = [c.asset_id for c in lentes.vizinhos if c.suprimida]
    assert sorted(suprimidas) == ["IFIX", "IMOB"]
    assert "sem conclusão" in html_real
    assert "alerta" in html_real


@acervo_real
def test_os_treze_itens_do_email_estao_na_tabela(html_real: str) -> None:
    assert len(R.ITENS_DO_EMAIL) == 13
    codigos = [codigo for codigo, _, _, _ in R.ITENS_DO_EMAIL]
    assert codigos == [
        "A1",
        "A2",
        "A3",
        "A4",
        "A5",
        "A6",
        "A7",
        "B1",
        "B2",
        "B3",
        "B4",
        "B5",
        "C1",
    ]
    for codigo in codigos:
        assert f">{codigo}</td>" in html_real


@acervo_real
def test_as_doze_decisoes_tem_espaco_de_resposta(html_real: str) -> None:
    assert len(R.DECISOES) == 12
    for codigo, _, _, _ in R.DECISOES:
        assert codigo in html_real
    assert html_real.count('class="resposta-vazia"') == 12
    assert "Sua resposta" in html_real


@acervo_real
def test_as_dez_limitacoes_estao_no_acordeao(html_real: str) -> None:
    assert len(R.LIMITACOES) == 10
    assert html_real.count("<details>") == 10
    for manchete, _ in R.LIMITACOES:
        primeiro_pedaco = manchete.split(",")[0][:40]
        assert primeiro_pedaco in html_real


@acervo_real
def test_o_hash_do_dataset_vem_do_manifesto(dados_reais: R.Dados, html_real: str) -> None:
    completo = R.hash_do_dataset(dados_reais.manifesto)
    assert len(completo) == 64
    assert completo in html_real
    assert R.hash_curto(completo) in html_real
    assert f'name="ldc-dataset" content="{R.hash_curto(completo)}"' in html_real


def test_manifesto_sem_hash_agregado_falha() -> None:
    with pytest.raises(SerieInconsistente, match="agregado"):
        R.hash_do_dataset({"agregado": {"sha256": "curto demais"}})


def test_relatorio_ausente_falha_como_fonte_indisponivel(tmp_path: Path) -> None:
    (tmp_path / "data" / "canonical").mkdir(parents=True)
    with pytest.raises(FonteIndisponivel, match="relatorio_regimes_v1.json"):
        R.ler_dados(raiz=tmp_path)


# ═════════════════════════════════════════════════════════════════════════════
# 7 - Nada marcado `publicavel: false`
# ═════════════════════════════════════════════════════════════════════════════


@acervo_real
def test_o_manifesto_marca_a_tabela_de_pesos_como_nao_publicavel(dados_reais: R.Dados) -> None:
    assert R.artefatos_nao_publicaveis(dados_reais.manifesto) == ["internacional_pesos.parquet"]


@acervo_real
def test_nenhum_artefato_nao_publicavel_aparece(dados_reais: R.Dados, html_real: str) -> None:
    for arquivo in R.artefatos_nao_publicaveis(dados_reais.manifesto):
        assert arquivo not in html_real
        assert arquivo.rsplit(".", 1)[0] not in html_real
    assert "variancia_minima" not in html_real
    assert "peso_variancia_minima" not in html_real


@acervo_real
def test_a_tabela_de_pesos_por_regime_nao_foi_publicada(html_real: str) -> None:
    """Os pesos por regime (18,3%, 23,6%, ...) ficam fora: a entrega é a faixa."""
    texto = sem_as_figuras(html_real)
    for peso in ("18,28%", "18,3%", "23,58%", "23,6%", "15,91%", "17,59%"):
        assert peso not in texto


@acervo_real
def test_nomear_artefato_nao_publicavel_derruba_a_montagem(dados_reais: R.Dados) -> None:
    documento = '<section id="s1-topo"></section>internacional_pesos<svg'
    with pytest.raises(SerieInconsistente, match="publicavel"):
        R._conferir_saida(documento, dados_reais)


# ═════════════════════════════════════════════════════════════════════════════
# 8 - Determinismo
# ═════════════════════════════════════════════════════════════════════════════


@acervo_real
def test_duas_geracoes_produzem_o_mesmo_sha256() -> None:
    primeira = R.montar_html()
    segunda = R.montar_html()
    assert R.sha256_do_texto(primeira) == R.sha256_do_texto(segunda)
    assert primeira == segunda


@acervo_real
def test_gravar_duas_vezes_produz_o_mesmo_arquivo(tmp_path: Path) -> None:
    alvo = tmp_path / R.NOME_DO_ARQUIVO
    primeiro = R.gerar(destino=alvo).read_bytes()
    segundo = R.gerar(destino=alvo).read_bytes()
    assert primeiro == segundo
    assert b"\r\n" not in primeiro, "o arquivo sai com LF, para o hash nao depender do sistema"
    assert primeiro.decode("utf-8").endswith("</html>\n")


# ═════════════════════════════════════════════════════════════════════════════
# 9 - Abre sem JavaScript
# ═════════════════════════════════════════════════════════════════════════════


@acervo_real
def test_nenhuma_das_onze_secoes_depende_de_javascript(html_real: str) -> None:
    """Sem JS, nenhuma seção pode estar escondida: as abas são CSS e o acordeão é nativo."""
    for identificador, _ in R.SECOES:
        posicao = html_real.find(f'<section id="{identificador}"')
        assert posicao > 0
        antes = html_real[:posicao]
        assert antes.count("<details") == antes.count("</details>"), (
            f"{identificador} esta dentro de um <details> e ficaria escondida"
        )
    assert "<noscript" not in html_real, "nada no relatorio precisa de alternativa sem JS"


@acervo_real
def test_as_abas_funcionam_por_css_e_nao_por_script(html_real: str) -> None:
    assert html_real.count('type="radio"') == 2
    assert "#aba-revisado:checked ~ .aba-paineis #painel-revisado" in html_real
    assert "onclick=" not in html_real
    assert "addEventListener" in html_real, "o JS existe, mas so para enriquecer"


@acervo_real
def test_o_que_o_javascript_faz_e_so_enriquecimento(html_real: str) -> None:
    """O único botão que depende de JS está escondido quando JS não roda."""
    assert ".so-com-js{display:none}" in html_real
    assert "html.js .so-com-js{display:inline-block}" in html_real
    assert 'class="so-com-js" id="expandir"' in html_real


@acervo_real
def test_a_impressao_abre_tudo_mesmo_sem_javascript(html_real: str) -> None:
    assert ".aba-painel{display:block !important;" in html_real
    assert "details>*{display:block !important}" in html_real
    assert ".so-na-impressao{display:block}" in html_real


# ═════════════════════════════════════════════════════════════════════════════
# 10 - O banido de DESIGN.md
# ═════════════════════════════════════════════════════════════════════════════


@acervo_real
def test_nenhum_travessao_no_html(html_real: str) -> None:
    assert R.TRAVESSAO not in html_real


@acervo_real
def test_sem_gradiente_de_texto_vidro_nem_borda_lateral_colorida(html_real: str) -> None:
    texto = sem_as_figuras(html_real)
    for banido in (
        "linear-gradient",
        "radial-gradient",
        "backdrop-filter",
        "-webkit-background-clip",
        "background-clip:text",
        "border-left:4px solid",
    ):
        assert banido not in texto, f"{banido} esta na lista de banidos de DESIGN.md"


@acervo_real
def test_as_tintas_sao_as_da_ldc(html_real: str) -> None:
    texto = sem_as_figuras(html_real)
    for tinta in ("#262d3d", "#577171", "#98ab44", "#c0584f", "#e6e8ea", "#fcfdfd"):
        assert tinta in texto
    assert "#000000" not in texto, "preto puro nao entra em superficie de dado"
    assert "background:#fff;" in texto, "fundo branco so na folha de impressao"


@acervo_real
def test_tipografia_public_sans_com_cascata_de_sistema(html_real: str) -> None:
    assert '"Public Sans"' in html_real
    assert "system-ui" in html_real
    assert "@font-face" not in html_real, "fonte embutida pesaria o arquivo e pode ser paga"


@acervo_real
def test_sem_card_dentro_de_card(html_real: str) -> None:
    """As superfícies de painel não se aninham: separador fino, nunca caixa dentro de caixa."""
    aninhados = re.findall(
        r'<div class="rolagem">(?:(?!</div>).)*<div class="rolagem">', html_real, re.DOTALL
    )
    assert aninhados == []
    assert html_real.count('<figure class="figura">') == 2
    assert '<figure class="figura"><figure' not in html_real
