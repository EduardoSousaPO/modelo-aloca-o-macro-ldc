"""Portão do `docs/product/GUIA-REVISAO-EDU.md` — o roteiro de 30 minutos do Edu.

**Por que este teste existe.** O guia é o único documento do projeto cujo público é **uma pessoa
com 30 minutos**, na véspera do Comitê. Ele não traz número próprio: ele diz **em que ordem** abrir
o que já existe, **o que custa** discordar de cada decisão provisória, **qual linha** mudar em qual
ADR para destravar e **quais comandos** rodar, na ordem. Um guia que perde uma dessas quatro partes
deixa de ser guia e volta a ser "leia o runbook inteiro" — que é exatamente o que ele substitui.

Então o teste trava a **estrutura e as referências**, não a redação:

1. o arquivo existe, é PT-BR, e cabe no orçamento de 120 linhas (se não cabe, não é de 30 min);
2. as 6 seções numeradas estão lá, na ordem;
3. a ordem de leitura cita os **5** artefatos, nessa sequência;
4. os **12** IDs de decisão aparecem — se a §7 de `LIMITACOES-COMITE.md` ganhar ou perder uma
   decisão, este teste cai e alguém tem que olhar os dois documentos juntos;
5. os **5** comandos do gate aparecem, na ordem em que precisam ser rodados;
6. os 6 ADRs têm o caminho **real** do arquivo em disco (caminho errado = o Edu não destrava);
7. os 3 canários aparecem com valor **e** host da fonte viva;
8. a regra "nada sai" está escrita, e o `WhatsApp` nominalmente — é a frase que o guia existe para
   deixar sem ambiguidade.

**Nada aqui roda a guarda de linguagem descritiva de propósito:** o guia *fala sobre* as
recomendações e as previsões que o projeto não faz, e o vocabulário da guarda
(`recomendação`, `previsão`) é o assunto do documento, não uma afirmação dele.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GUIA = RAIZ / "docs" / "product" / "GUIA-REVISAO-EDU.md"

#: As 12 decisões da §7 de `LIMITACOES-COMITE.md`, que a reunião precisa ratificar.
IDS_DAS_DECISOES: tuple[str, ...] = (
    "D1",
    "D3",
    "D5",
    "D6",
    "D12",
    "L1",
    "L2",
    "L4",
    "D-i",
    "D-s",
    "D-t",
    "D-u",
)

#: Os 5 comandos do gate, na ordem obrigatória (`runbooks/entrega-comite.md §1`).
COMANDOS_NA_ORDEM: tuple[str, ...] = (
    "apps.pipeline run --offline",
    "apps.pipeline verify",
    "apps.pipeline freeze --tag comite-2026-10-14",
    "apps.analysis.entrega.montar_pacote --smoke",
    "git tag -a comite-2026-10-14",
)

#: A ordem de leitura de 30 minutos, na sequência em que o guia a impõe.
ORDEM_DE_LEITURA: tuple[str, ...] = (
    "LIMITACOES-COMITE.md",
    "timeline_regimes_revised.png",
    "tabelas/ranking_regime_atual.md",
    "heatmap_v1_revised",
    "entrega_comite_2026-10-14.html",
)

#: `(valor, série, host da fonte viva)` — os 3 que atravessam o pipeline inteiro.
CANARIOS: tuple[tuple[str, str, str], ...] = (
    ("38.484,84", "IBOV", "b3.com.br"),
    ("723,070317", "IMA-B", "amazonaws.com"),
    ("121,3858", "ACWI", "msci.com"),
)


@pytest.fixture(scope="module")
def texto() -> str:
    assert GUIA.is_file(), f"{GUIA} nao existe — o guia do Edu e entregavel de F-031"
    return GUIA.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 1. O arquivo e o orçamento
# ─────────────────────────────────────────────────────────────────────────────


def test_o_guia_cabe_em_120_linhas(texto: str) -> None:
    """Orçamento duro: guia de 30 minutos que não cabe numa leitura não é guia."""
    linhas = texto.splitlines()
    assert len(linhas) <= 120, f"{len(linhas)} linhas — passou do orcamento de 120"


def test_o_guia_e_em_pt_br(texto: str) -> None:
    """Amostra de palavras que só existem em PT-BR, para pegar guia escrito em inglês."""
    for palavra in ("decisões", "comandos", "revisão", "canários"):
        assert palavra in texto, f"'{palavra}' ausente — o guia e PT-BR por contrato"


def test_identifica_o_destinatario_e_a_data(texto: str) -> None:
    assert "Edu" in texto
    assert "2026-10-14" in texto, "a data do Comite tem que estar no guia"
    assert "13/10" in texto, "a data da revisao (terca) tem que estar no guia"


# ─────────────────────────────────────────────────────────────────────────────
# 2. As seções
# ─────────────────────────────────────────────────────────────────────────────


def test_tem_as_seis_secoes_numeradas_na_ordem(texto: str) -> None:
    titulos = re.findall(r"^## (\d)\. (.+)$", texto, flags=re.MULTILINE)
    assert [n for n, _ in titulos] == ["1", "2", "3", "4", "5", "6"], titulos
    assunto = " | ".join(t.lower() for _, t in titulos)
    for esperado in ("ordem de leitura", "decisões", "destravar", "comandos", "caixas", "canários"):
        assert esperado in assunto, f"nenhuma secao trata de '{esperado}' — {assunto}"


def test_a_ordem_de_leitura_tem_os_cinco_artefatos_na_sequencia(texto: str) -> None:
    posicoes = []
    for alvo in ORDEM_DE_LEITURA:
        pos = texto.find(alvo)
        assert pos != -1, f"a ordem de leitura nao cita {alvo}"
        posicoes.append(pos)
    assert posicoes == sorted(posicoes), f"ordem de leitura fora de sequencia: {posicoes}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. As 12 decisões
# ─────────────────────────────────────────────────────────────────────────────


def test_cita_os_doze_ids_de_decisao(texto: str) -> None:
    """Os 12 da §7 de `LIMITACOES-COMITE.md`. Mudou a lista lá? Este teste cai aqui."""
    faltando = [i for i in IDS_DAS_DECISOES if f"**{i}**" not in texto]
    assert not faltando, f"IDs de decisao ausentes do guia: {faltando}"


def test_a_contagem_de_doze_esta_escrita(texto: str) -> None:
    assert "12 decisões" in texto, "o guia tem que dizer QUANTAS decisoes sao"


def test_cada_decisao_traz_a_recomendacao_e_o_custo_de_discordar(texto: str) -> None:
    """A tabela de decisões tem 4 colunas, e as duas últimas são o conteúdo útil."""
    cabecalho = "| # | Decisão | Recomendação adotada | Custo de discordar |"
    assert cabecalho in texto, "a tabela das 12 decisoes perdeu uma das duas colunas que importam"
    linhas = [ln for ln in texto.splitlines() if re.match(r"^\| \*\*(D|L)[-\w]*\*\* \|", ln)]
    assert len(linhas) == 12, f"{len(linhas)} linhas de decisao, esperado 12"
    for linha in linhas:
        celulas = [c.strip() for c in linha.strip("|").split("|")]
        assert len(celulas) == 4, linha
        assert len(celulas[2]) > 10, f"recomendacao vazia: {linha}"
        assert len(celulas[3]) > 20, f"custo de discordar vazio: {linha}"


def test_diz_que_aceitar_as_recomendacoes_destrava_de_uma_vez(texto: str) -> None:
    assert "aceito as recomendações" in texto


# ─────────────────────────────────────────────────────────────────────────────
# 4. Como destravar — os ADRs
# ─────────────────────────────────────────────────────────────────────────────


def test_diz_qual_linha_mudar_em_qual_arquivo(texto: str) -> None:
    assert "`Status:`" in texto or "**Status:**" in texto
    assert "Aceita" in texto
    assert "Proposta" in texto


@pytest.mark.parametrize("numero", ["001", "002", "003", "004", "005", "006"])
def test_o_caminho_de_cada_adr_existe_em_disco(texto: str, numero: str) -> None:
    """Caminho errado = o Edu não destrava. O guia cita o arquivo real, não o nome do ADR."""
    padrao = rf"docs/decisions/adr/ADR-{numero}-[a-z0-9-]+\.md"
    achados = re.findall(padrao, texto)
    assert achados, f"o guia nao cita o caminho de ADR-{numero}"
    for caminho in set(achados):
        assert (RAIZ / caminho).is_file(), f"{caminho} citado no guia e nao existe em disco"


def test_marca_o_adr_001_como_o_gate_duro(texto: str) -> None:
    linha = next(ln for ln in texto.splitlines() if "ADR-001-lente-de-regime-oficial" in ln)
    assert "gate duro" in linha.lower() or "gate duro" in texto.lower()
    assert "**ADR-001**" in texto


# ─────────────────────────────────────────────────────────────────────────────
# 5. Os comandos
# ─────────────────────────────────────────────────────────────────────────────


def test_cita_os_cinco_comandos_na_ordem(texto: str) -> None:
    posicoes = []
    for comando in COMANDOS_NA_ORDEM:
        pos = texto.find(comando)
        assert pos != -1, f"comando ausente do guia: {comando}"
        posicoes.append(pos)
    assert posicoes == sorted(posicoes), f"comandos fora da ordem do gate: {posicoes}"


def test_explica_por_que_o_pacote_vem_depois_do_freeze(texto: str) -> None:
    """A ordem não é arbitrária: o pacote copia o `MANIFEST.json`."""
    assert "MANIFEST.json" in texto
    assert "ordem importa" in texto.lower()


def test_diz_que_a_tag_e_ato_humano(texto: str) -> None:
    assert "não executa" in texto and "git" in texto
    assert "git tag -f" in texto, "a proibicao de forcar a tag tem que estar escrita"


# ─────────────────────────────────────────────────────────────────────────────
# 6. A checklist e os canários
# ─────────────────────────────────────────────────────────────────────────────


def test_linka_a_checklist_de_19_caixas_no_runbook(texto: str) -> None:
    assert "19" in texto
    assert "runbooks/entrega-comite.md" in texto
    runbook = RAIZ / "docs" / "wiki" / "runbooks" / "entrega-comite.md"
    assert runbook.is_file(), "o guia linka um runbook que nao existe"
    corpo = runbook.read_text(encoding="utf-8")
    caixas = re.findall(r"^- \[ \] \*\*\d+\.", corpo, flags=re.MULTILINE)
    assert len(caixas) == 19, f"o runbook tem {len(caixas)} caixas numeradas, o guia promete 19"


@pytest.mark.parametrize(("valor", "serie", "host"), CANARIOS)
def test_cada_canario_traz_valor_serie_e_fonte_viva(
    texto: str, valor: str, serie: str, host: str
) -> None:
    assert valor in texto, f"canario {serie} sem o valor {valor}"
    assert serie in texto, f"canario sem a serie {serie}"
    assert host in texto, f"canario {serie} sem a URL da fonte viva ({host})"


def test_manda_conferir_na_fonte_viva_e_nao_no_parquet(texto: str) -> None:
    assert "fonte viva" in texto
    assert "raw_series.parquet" in texto, "o guia tem que dizer contra o que JA foi conferido"


# ─────────────────────────────────────────────────────────────────────────────
# 7. A regra que o guia existe para deixar sem ambiguidade
# ─────────────────────────────────────────────────────────────────────────────


def test_a_regra_de_nada_sai_esta_no_topo_e_cita_o_whatsapp(texto: str) -> None:
    topo = texto[: texto.find("## 1.")].upper()
    assert "NADA SAI" in topo, "a regra tem que estar ANTES da ordem de leitura"
    assert "WHATSAPP" in topo, "a regra sem o exemplo concreto vira texto de contrato"
    assert "PROPOSTA" in topo


def test_diz_que_nao_existe_classe_a_b_para_publicacao(texto: str) -> None:
    assert "classe A/B" in texto
    assert "10.3.18" in texto, "a referencia da Anti-SPEC torna a regra verificavel"


def test_o_gate_e_lido_do_disco_nao_digitado(texto: str) -> None:
    assert "especificacao_congelada" in texto
    assert "falha fechada" in texto or "lido do disco" in texto
