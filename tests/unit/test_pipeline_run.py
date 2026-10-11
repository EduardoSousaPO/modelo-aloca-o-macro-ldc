"""F-029 — orquestrador: ordem das etapas, parada no erro, `verify` e `freeze`.

O que estes testes protegem, e por quê:

- **A ordem é o contrato.** `etapas()` é a única declaração de "quem roda quando". Uma etapa
  trocada de lugar não levanta exceção: `macro_quarterly` antes de `alinhamento` lê o
  `alinhado_trimestral` da rodada **anterior** e produz número plausível e errado. O teste fixa a
  tupla inteira, não "contém".
- **Parada no primeiro erro.** A etapa seguinte à que falhou nunca roda — é o que impede o
  pipeline de concluir em silêncio sobre insumo faltando.
- **`verify` tem de reprovar 1 byte.** Testado com um byte alterado dentro de `tmp_path`, que é a
  forma mínima de "o arquivo publicado não é o que o manifesto diz".
- **O manifesto e o `freeze` são determinísticos.** Dois `montar_manifesto` seguidos têm de dar o
  **mesmo arquivo byte a byte**; se algum campo viesse do relógio, este teste pegaria.

`tmp_path` em todo lugar: nenhum teste escreve em `data/` do repositório (Anti-SPEC §10.4.22).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from apps.pipeline.common.errors import ErroDeExtracao
from apps.pipeline.run import (
    ARTEFATOS_NAO_PUBLICAVEIS,
    MOTIVO_ILEGIVEL,
    NAO_DETERMINISTICOS,
    NOME_FROZEN,
    NOME_MANIFESTO,
    Contexto,
    ErroDeOrquestracao,
    Etapa,
    EtapaNaoChamavel,
    FalhaDeEtapa,
    Fase,
    congelar,
    executar,
    gravar_manifesto,
    hash_agregado,
    inventariar,
    main,
    montar_manifesto,
    nomes_das_etapas,
    para_ascii,
    selecionar_etapas,
    verificar,
)

#: A ordem completa, escrita à mão: se `etapas()` mudar, este teste é o lugar de justificar.
ORDEM_ESPERADA: tuple[str, ...] = (
    "extract_sgs",
    "extract_sidra",
    "extract_focus",
    "extract_calendario",
    "extract_anbima",
    "extract_tesouro",
    "extract_b3",
    "extract_yahoo",
    "extract_msci",
    "curva",
    "build_raw_series",
    "alinhamento",
    "macro_quarterly",
    "asof",
    "retornos",
    "regimes_v1",
    "regimes_v1_asof",
    "regimes_v3",
    "metricas_regime",
    "internacional",
    "figuras",
    "tabelas",
)


# ─────────────────────────────────────────────────────────────────────────────
# A. Ordem das etapas
# ─────────────────────────────────────────────────────────────────────────────


def test_ordem_das_etapas_e_exatamente_a_declarada() -> None:
    assert nomes_das_etapas() == ORDEM_ESPERADA


def test_dependencias_de_ordem_que_nao_podem_inverter() -> None:
    ordem = list(nomes_das_etapas())
    # `curva` grava em data/processed/, logo precede quem lê a camada processada.
    assert ordem.index("curva") < ordem.index("build_raw_series")
    # `calendario` dá a grade de dias úteis que `alinhamento` consome.
    assert ordem.index("extract_calendario") < ordem.index("alinhamento")
    # o SGS traz a PTAX de F-003, que a conversão a BRL de yahoo/msci usa (D-g).
    assert ordem.index("extract_sgs") < ordem.index("extract_yahoo")
    assert ordem.index("extract_sgs") < ordem.index("extract_msci")
    # cadeia canônica: raw -> alinhado -> macro -> asof -> retornos -> regimes -> metricas.
    cadeia = [
        "build_raw_series",
        "alinhamento",
        "macro_quarterly",
        "asof",
        "retornos",
        "regimes_v1",
        "regimes_v3",
        "metricas_regime",
        "internacional",
    ]
    assert [ordem.index(nome) for nome in cadeia] == sorted(ordem.index(n) for n in cadeia)
    # F-026 lê as métricas de F-022 (`metricas_da_celula`) e os vizinhos da lente canônica.
    assert ordem.index("metricas_regime") < ordem.index("internacional")
    # as figuras e as tabelas leem o canônico inteiro, logo fecham a lista.
    assert ordem.index("internacional") < ordem.index("figuras") < ordem.index("tabelas")


def test_offline_nao_seleciona_extracao() -> None:
    nomes = [etapa.nome for etapa in selecionar_etapas(online=False)]
    assert not [nome for nome in nomes if nome.startswith("extract_")]
    assert nomes[0] == "curva"


def test_online_seleciona_os_nove_extratores() -> None:
    fases = [etapa.fase for etapa in selecionar_etapas(online=True)]
    assert fases.count(Fase.EXTRACAO) == 9


def test_reprocessar_traz_a_extracao_de_volta_no_offline() -> None:
    nomes = [etapa.nome for etapa in selecionar_etapas(online=False, reprocessar=True)]
    assert nomes[0] == "extract_sgs"


def test_ate_corta_a_lista_no_ponto_pedido() -> None:
    nomes = [etapa.nome for etapa in selecionar_etapas(online=False, ate="alinhamento")]
    assert nomes == ["curva", "build_raw_series", "alinhamento"]


def test_so_roda_uma_etapa_e_tem_precedencia_sobre_ate() -> None:
    selecao = selecionar_etapas(online=False, ate="alinhamento", so="regimes_v3")
    assert [etapa.nome for etapa in selecao] == ["regimes_v3"]


def test_sem_opcionais_remove_as_quatro_etapas_opcionais() -> None:
    """`--sem-opcionais` tira F-022, F-026, as figuras (F-023/F-025) e as tabelas (F-024)."""
    nomes = [etapa.nome for etapa in selecionar_etapas(online=False, com_opcionais=False)]
    for opcional in ("metricas_regime", "internacional", "figuras", "tabelas"):
        assert opcional not in nomes


def test_etapa_inexistente_lista_as_validas_na_mensagem() -> None:
    with pytest.raises(ErroDeOrquestracao) as capturado:
        selecionar_etapas(online=False, so="regimes_v2")
    mensagem = str(capturado.value)
    assert "regimes_v2" in mensagem
    assert "build_raw_series" in mensagem and "figuras" in mensagem


def test_ate_em_etapa_fora_da_selecao_explica_a_fase() -> None:
    with pytest.raises(ErroDeOrquestracao) as capturado:
        selecionar_etapas(online=False, ate="extract_sgs")
    assert "extracao" in str(capturado.value)


# ─────────────────────────────────────────────────────────────────────────────
# B. Parada no primeiro erro
# ─────────────────────────────────────────────────────────────────────────────


def _etapa(nome: str, acao) -> Etapa:  # noqa: ANN001 - callable de teste
    return Etapa(nome=nome, fase=Fase.CANONICO, descricao=f"teste {nome}", executar=acao)


def test_para_na_primeira_falha_e_nao_roda_a_seguinte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rodaram: list[str] = []

    def quebra(_: Contexto) -> None:
        rodaram.append("segunda")
        raise ErroDeExtracao("BLOQUEADO — FONTE INDISPONÍVEL: série exigida ausente")

    falsas = (
        _etapa("primeira", lambda _: rodaram.append("primeira")),
        _etapa("segunda", quebra),
        _etapa("terceira", lambda _: rodaram.append("terceira")),
    )
    monkeypatch.setattr("apps.pipeline.run.etapas", lambda: falsas)
    with pytest.raises(FalhaDeEtapa) as capturado:
        executar(raiz=tmp_path, online=False)
    assert rodaram == ["primeira", "segunda"], "a etapa seguinte à falha não pode rodar"
    mensagem = str(capturado.value)
    assert "'segunda'" in mensagem, "a mensagem tem de nomear a etapa"
    assert "--so segunda" in mensagem, "a mensagem tem de dar o comando de retomada"
    assert "terceira" in mensagem, "a mensagem tem de dizer o que não rodou"
    assert "FONTE INDISPON" in mensagem, "a causa original não pode ser engolida"


def test_etapa_opcional_sem_modulo_e_pulada_sem_falhar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    falsas = (
        Etapa(
            nome="opcional_ausente",
            fase=Fase.ANALISE,
            descricao="feature vizinha que ainda não existe",
            executar=lambda _: pytest.fail("não devia ser chamada"),
            modulo_opcional="apps.analysis.modulo_que_nao_existe",
        ),
    )
    monkeypatch.setattr("apps.pipeline.run.etapas", lambda: falsas)
    resultado = executar(raiz=tmp_path, online=False)
    assert [e.situacao for e in resultado.executadas] == ["pulada"]


def test_etapa_opcional_sem_ponto_de_entrada_e_pulada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sem_ponte(_: Contexto) -> None:
        raise EtapaNaoChamavel("pacote existe, construir() ainda não")

    falsas = (
        Etapa(
            nome="meia_feature",
            fase=Fase.ANALISE,
            descricao="pacote no disco, sem construir()",
            executar=sem_ponte,
            modulo_opcional="apps.pipeline.run",
        ),
    )
    monkeypatch.setattr("apps.pipeline.run.etapas", lambda: falsas)
    resultado = executar(raiz=tmp_path, online=False)
    assert resultado.executadas[0].situacao == "pulada"


def test_etapa_obrigatoria_sem_ponto_de_entrada_falha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sem_ponte(_: Contexto) -> None:
        raise EtapaNaoChamavel("sem construir()")

    monkeypatch.setattr("apps.pipeline.run.etapas", lambda: (_etapa("obrigatoria", sem_ponte),))
    with pytest.raises(FalhaDeEtapa):
        executar(raiz=tmp_path, online=False)


def test_extracao_recusa_raiz_alternativa(tmp_path: Path) -> None:
    with pytest.raises(ErroDeOrquestracao) as capturado:
        executar(raiz=tmp_path, online=True, so="extract_sgs")
    assert "data/raw" in str(capturado.value)


def test_reprocessar_com_online_e_recusado(tmp_path: Path) -> None:
    assert main(["run", "--online", "--reprocessar", "--raiz", str(tmp_path)]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# C. Inventário, manifesto e determinismo
# ─────────────────────────────────────────────────────────────────────────────


def _canonical_de_teste(raiz: Path) -> Path:
    """Um `data/canonical/` mínimo em `tmp_path`: 1 Parquet, 1 relatório, 1 derivado, 1 .gitkeep.

    Valores sintéticos e **só** em `tmp_path` (`CLAUDE.md §4`): a pergunta destes testes é sobre
    hash e manifesto, não sobre o número — nenhuma linha daqui chega a `data/`.
    """
    pasta = raiz / "data" / "canonical"
    pasta.mkdir(parents=True)
    quadro = pd.DataFrame(
        {
            "quarter": ["2006Q1", "2006Q2", "2006Q3"],
            "valor": [1.0, None, 3.0],
            "rotulo": ["a", "b", "c"],
        }
    )
    quadro.to_parquet(pasta / "tabela_sintetica.parquet", index=False)
    (pasta / "relatorio_build.json").write_text(
        json.dumps(
            {
                "raw_series": {
                    "date_min": "2006-01-02",
                    "date_max": "2026-10-10",
                    "vintages": ["2026-10-10", "2026-10-11"],
                },
                "versao_build": "f" * 64,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (pasta / "ldc.duckdb").write_bytes(b"derivado-1")
    (pasta / ".gitkeep").write_bytes(b"")
    return pasta


def test_inventario_ignora_gitkeep_e_perfila_o_parquet(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    artefatos = {a.arquivo: a for a in inventariar(raiz=tmp_path)}
    assert ".gitkeep" not in artefatos
    assert set(artefatos) == {"tabela_sintetica.parquet", "relatorio_build.json", "ldc.duckdb"}
    tabela = artefatos["tabela_sintetica.parquet"]
    assert tabela.linhas == 3
    assert tabela.colunas == 3
    assert (tabela.date_min, tabela.date_max) == ("2006Q1", "2006Q3")
    assert tabela.nulos_por_coluna == {"valor": pytest.approx(33.333333, abs=1e-5)}
    assert artefatos["ldc.duckdb"].determinista is False


def test_inventario_e_recursivo_e_usa_caminho_posix(tmp_path: Path) -> None:
    pasta = _canonical_de_teste(tmp_path)
    (pasta / "figuras").mkdir()
    (pasta / "figuras" / "timeline.svg").write_text("<svg/>", encoding="utf-8")
    nomes = [a.arquivo for a in inventariar(raiz=tmp_path)]
    assert "figuras/timeline.svg" in nomes


def test_manifesto_e_byte_identico_em_duas_montagens(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    primeiro = gravar_manifesto(montar_manifesto(raiz=tmp_path), destino=tmp_path / "m1.json")
    segundo = gravar_manifesto(montar_manifesto(raiz=tmp_path), destino=tmp_path / "m2.json")
    assert primeiro.read_bytes() == segundo.read_bytes()


def test_manifesto_nao_guarda_hash_do_derivado(tmp_path: Path) -> None:
    pasta = _canonical_de_teste(tmp_path)
    manifesto = montar_manifesto(raiz=tmp_path)
    entradas = {item["arquivo"]: item for item in manifesto["artefatos"]}
    assert entradas["ldc.duckdb"]["sha256"] is None
    antes = manifesto["agregado"]["sha256"]
    (pasta / "ldc.duckdb").write_bytes(b"derivado-2-outro-conteudo")
    assert montar_manifesto(raiz=tmp_path)["agregado"]["sha256"] == antes


def test_manifesto_registra_versao_build_e_data_do_dado(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    manifesto = montar_manifesto(raiz=tmp_path)
    assert manifesto["versao_build"]["relatorio_build.json"] == "f" * 64
    assert manifesto["data_do_dado"]["date_max_raw_series"] == "2026-10-10"
    assert manifesto["data_do_dado"]["vintage_max"] == "2026-10-11"


def test_agregado_muda_quando_um_artefato_muda(tmp_path: Path) -> None:
    pasta = _canonical_de_teste(tmp_path)
    antes = hash_agregado(inventariar(raiz=tmp_path))
    (pasta / "relatorio_build.json").write_text("{}\n", encoding="utf-8")
    assert hash_agregado(inventariar(raiz=tmp_path)) != antes


def test_inventario_em_pasta_inexistente_e_erro_acionavel(tmp_path: Path) -> None:
    with pytest.raises(ErroDeOrquestracao) as capturado:
        inventariar(raiz=tmp_path)
    assert "run --offline" in str(capturado.value)


# ─────────────────────────────────────────────────────────────────────────────
# D. verify
# ─────────────────────────────────────────────────────────────────────────────


def test_verify_aprova_o_que_o_manifesto_declara(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    gravar_manifesto(
        montar_manifesto(raiz=tmp_path), destino=tmp_path / "data" / "canonical" / NOME_MANIFESTO
    )
    resultado = verificar(raiz=tmp_path)
    assert resultado.ok
    assert resultado.agregado_esperado == resultado.agregado_obtido
    assert main(["verify", "--raiz", str(tmp_path)]) == 0


def test_verify_reprova_um_byte_alterado(tmp_path: Path) -> None:
    pasta = _canonical_de_teste(tmp_path)
    gravar_manifesto(montar_manifesto(raiz=tmp_path), destino=pasta / NOME_MANIFESTO)
    alvo = pasta / "tabela_sintetica.parquet"
    corpo = bytearray(alvo.read_bytes())
    posicao = len(corpo) // 2
    corpo[posicao] = (corpo[posicao] + 1) % 256  # exatamente 1 byte
    alvo.write_bytes(bytes(corpo))

    resultado = verificar(raiz=tmp_path)
    assert not resultado.ok
    graves = {d.arquivo: d for d in resultado.graves}
    assert "tabela_sintetica.parquet" in graves
    assert graves["tabela_sintetica.parquet"].situacao == "sha256 divergente"
    assert "<agregado>" in graves
    assert main(["verify", "--raiz", str(tmp_path)]) == 1


def test_verify_reprova_artefato_ausente(tmp_path: Path) -> None:
    pasta = _canonical_de_teste(tmp_path)
    gravar_manifesto(montar_manifesto(raiz=tmp_path), destino=pasta / NOME_MANIFESTO)
    (pasta / "tabela_sintetica.parquet").unlink()
    resultado = verificar(raiz=tmp_path)
    assert not resultado.ok
    assert {d.situacao for d in resultado.graves} >= {"ausente em disco"}


def test_verify_reprova_artefato_novo_nao_listado(tmp_path: Path) -> None:
    pasta = _canonical_de_teste(tmp_path)
    gravar_manifesto(montar_manifesto(raiz=tmp_path), destino=pasta / NOME_MANIFESTO)
    (pasta / "intruso.json").write_text("{}\n", encoding="utf-8")
    resultado = verificar(raiz=tmp_path)
    assert not resultado.ok
    assert any(d.arquivo == "intruso.json" for d in resultado.graves)


def test_verify_nao_reprova_o_derivado_nao_deterministico(tmp_path: Path) -> None:
    pasta = _canonical_de_teste(tmp_path)
    gravar_manifesto(montar_manifesto(raiz=tmp_path), destino=pasta / NOME_MANIFESTO)
    (pasta / "ldc.duckdb").write_bytes(b"outro-conteudo-do-derivado")
    resultado = verificar(raiz=tmp_path)
    assert resultado.ok, "ldc.duckdb é derivado e declarado não reprodutível"
    assert any(d.arquivo in NAO_DETERMINISTICOS and d.informativa for d in resultado.divergencias)


def test_verify_reprova_parquet_ilegivel_sem_estourar_traceback(tmp_path: Path) -> None:
    """**P1-1 do QA da Onda 4.** *Bit-rot* / arquivo truncado é o caso que o selo existe para
    pegar, e era o único em que o `verify` **estourava**: `inventariar` chamava
    `_perfil_do_parquet` (→ `pd.read_parquet`) **antes** de comparar hash, e um `.parquet` que não
    é Parquet levantava `OSError`/`ArrowInvalid` como traceback cru — sem nomear o arquivo nem o
    agregado (encosta em Anti-SPEC §10.4.26).

    Agora: perfil vazio + `ilegivel` preenchido, divergência de `sha256` reportada, `rc = 1`.
    """
    pasta = _canonical_de_teste(tmp_path)
    gravar_manifesto(montar_manifesto(raiz=tmp_path), destino=pasta / NOME_MANIFESTO)
    alvo = pasta / "tabela_sintetica.parquet"
    alvo.write_bytes(b"nao sou parquet")

    resultado = verificar(raiz=tmp_path)  # não levanta

    assert not resultado.ok
    graves = {d.arquivo: d for d in resultado.graves}
    assert "tabela_sintetica.parquet" in graves
    assert "<agregado>" in graves
    situacoes = {d.situacao for d in resultado.graves if d.arquivo == "tabela_sintetica.parquet"}
    assert "sha256 divergente" in situacoes
    assert any(MOTIVO_ILEGIVEL in s for s in situacoes)
    assert main(["verify", "--raiz", str(tmp_path)]) == 1


def test_inventario_de_parquet_ilegivel_nao_levanta_e_marca_o_motivo(tmp_path: Path) -> None:
    """O inventário descreve o disco; "não consigo abrir" é **informação**, não exceção."""
    pasta = _canonical_de_teste(tmp_path)
    (pasta / "tabela_sintetica.parquet").write_bytes(b"xxx")
    artefatos = {a.arquivo: a for a in inventariar(raiz=tmp_path)}
    quebrado = artefatos["tabela_sintetica.parquet"]
    assert quebrado.ilegivel is not None
    assert MOTIVO_ILEGIVEL in quebrado.ilegivel
    assert quebrado.linhas is None
    assert len(quebrado.sha256) == 64, "o hash dos bytes em disco continua sendo calculado"


def test_verify_ilegivel_reprova_mesmo_com_hash_batendo(tmp_path: Path) -> None:
    """Hash igual só diz "não mudou **desde o manifesto**" — e o manifesto pode ter nascido sobre o
    arquivo já corrompido. Nesse caso o `verify` **ainda** reprova, nomeando o arquivo."""
    pasta = _canonical_de_teste(tmp_path)
    (pasta / "tabela_sintetica.parquet").write_bytes(b"corrompido desde o inicio")
    gravar_manifesto(montar_manifesto(raiz=tmp_path), destino=pasta / NOME_MANIFESTO)
    resultado = verificar(raiz=tmp_path)
    assert not resultado.ok
    assert any(
        d.arquivo == "tabela_sintetica.parquet" and MOTIVO_ILEGIVEL in d.situacao
        for d in resultado.graves
    )


def test_manifesto_marca_o_nao_publicavel_e_frozen_o_lista(tmp_path: Path) -> None:
    """**D-af.** `internacional_pesos.parquet` é construído e conferido, mas **não** vai ao Comitê
    (Anti-SPEC §10.3.16/§10.5 → F-035). O manifesto diz `publicavel: false` **na entrada** e o
    `FROZEN.txt` o lista como excluído do pacote — é essa lista que F-031 lê, não o nome do
    arquivo. Ele **continua** no agregado: o `DATASET_SHA256` descreve o que foi construído.
    """
    pasta = _canonical_de_teste(tmp_path)
    nome = next(iter(ARTEFATOS_NAO_PUBLICAVEIS))
    pd.DataFrame({"quarter": ["2006Q1"], "peso": [0.2]}).to_parquet(pasta / nome, index=False)

    manifesto = montar_manifesto(raiz=tmp_path)
    por_arquivo = {a["arquivo"]: a for a in manifesto["artefatos"]}
    assert por_arquivo[nome]["publicavel"] is False
    assert por_arquivo[nome]["motivo_nao_publicavel"] == ARTEFATOS_NAO_PUBLICAVEIS[nome]
    assert por_arquivo["tabela_sintetica.parquet"]["publicavel"] is True
    assert nome in [a["arquivo"] for a in manifesto["artefatos"] if a.get("sha256")], (
        "o nao publicavel continua tendo hash e entrando no agregado"
    )

    resultado = congelar(tag="teste-d-af", raiz=tmp_path)
    frozen = resultado.caminho_frozen.read_text(encoding="utf-8")
    assert "EXCLUIDOS DO PACOTE DE ENTREGA" in frozen
    assert nome in frozen
    assert "publicavel" in frozen


def test_verify_sem_manifesto_e_erro_acionavel(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    with pytest.raises(ErroDeOrquestracao) as capturado:
        verificar(raiz=tmp_path)
    assert "freeze" in str(capturado.value) or "run --offline" in str(capturado.value)


# ─────────────────────────────────────────────────────────────────────────────
# E. freeze
# ─────────────────────────────────────────────────────────────────────────────


def test_freeze_grava_manifesto_e_frozen_deterministicos(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    primeiro = congelar(tag="comite-2026-10-14", raiz=tmp_path)
    bytes_manifesto = primeiro.caminho_manifesto.read_bytes()
    bytes_frozen = primeiro.caminho_frozen.read_bytes()
    segundo = congelar(tag="comite-2026-10-14", raiz=tmp_path)
    assert segundo.caminho_manifesto.read_bytes() == bytes_manifesto
    assert segundo.caminho_frozen.read_bytes() == bytes_frozen
    assert segundo.agregado == primeiro.agregado


def test_frozen_tem_tag_data_do_dado_e_rollback(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    congelado = congelar(tag="teste", raiz=tmp_path)
    texto = congelado.caminho_frozen.read_text(encoding="utf-8")
    assert texto.isascii(), "FROZEN.txt tem de ser ASCII puro (Anti-SPEC §10.4.26)"
    assert "tag                 : teste" in texto
    assert "2026-10-10" in texto, "a data do DADO (nao do relogio) tem de aparecer"
    assert "ROLLBACK" in texto and "verify" in texto
    assert congelado.manifesto["congelamento"]["tag"] == "teste"
    assert congelado.agregado in congelado.manifesto["congelamento"]["instrucao_de_tag"]


def test_freeze_nao_escreve_fora_de_data(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    with pytest.raises(ErroDeOrquestracao) as capturado:
        congelar(tag="teste", raiz=tmp_path, saida=tmp_path / "entrega")
    assert "fora de" in str(capturado.value)


def test_freeze_aceita_saida_dentro_de_data(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    congelado = congelar(tag="teste", raiz=tmp_path, saida=tmp_path / "data" / "entrega")
    assert congelado.caminho_manifesto == tmp_path / "data" / "entrega" / NOME_MANIFESTO
    assert (tmp_path / "data" / "entrega" / NOME_FROZEN).is_file()
    # o manifesto do canonical não foi tocado
    assert not (tmp_path / "data" / "canonical" / NOME_MANIFESTO).exists()


def test_freeze_recusa_tag_com_caractere_proibido(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    for tag in ("", "comitê-2026", "tag com espaco", "a/b"):
        with pytest.raises(ErroDeOrquestracao):
            congelar(tag=tag, raiz=tmp_path)


def test_freeze_registra_commit_sem_executar_git(tmp_path: Path) -> None:
    _canonical_de_teste(tmp_path)
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text("a" * 40 + "\n", encoding="utf-8")
    congelado = congelar(tag="teste", raiz=tmp_path)
    assert congelado.manifesto["congelamento"]["git_commit"] == "a" * 40
    assert congelado.manifesto["congelamento"]["git_ref"] == "refs/heads/main"


# ─────────────────────────────────────────────────────────────────────────────
# F. ASCII e CLI
# ─────────────────────────────────────────────────────────────────────────────


def test_para_ascii_translitera_sem_perder_palavra() -> None:
    assert para_ascii("BLOQUEADO — FONTE INDISPONÍVEL") == "BLOQUEADO - FONTE INDISPONIVEL"
    assert para_ascii("não expõe · série") == "nao expoe | serie"
    assert para_ascii("2006Q1 → 2026Q3") == "2006Q1 -> 2026Q3"
    assert para_ascii("±1 pp ≤ 5%") == "+/-1 pp <= 5%"


def test_listar_etapas_nao_roda_nada(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--offline", "--listar-etapas", "--raiz", str(tmp_path)]) == 0
    saida = capsys.readouterr().out
    assert "build_raw_series" in saida
    assert not (tmp_path / "data").exists(), "--listar-etapas não pode criar nada"


def test_cli_exige_modo_explicito() -> None:
    with pytest.raises(SystemExit):
        main(["run"])
