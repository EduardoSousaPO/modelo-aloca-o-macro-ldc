"""F-029 — reprodutibilidade por hash: duas execuções `--offline` dão o mesmo `sha256` (CA-121).

**O que este arquivo mede.** O pipeline roda duas vezes, do mesmo `data/processed/`, numa árvore
limpa em `tmp_path`, e os artefatos de `data/canonical/` têm de sair **byte a byte iguais** —
inclusive o `MANIFEST.json`, que é o que o `verify` e o gate da classe D consultam. É o nível
**N3** de `AGENTS.md §6` na forma executável.

**Por que vai até `build_raw_series` e não até o fim.** O insumo versionado é
`tests/fixtures/processed/` — 7 séries + o painel do Tesouro (ver o README de lá). Da terceira
etapa em diante o pipeline exige séries que a fixture não tem e **para** com
`BLOQUEADO — FONTE INDISPONÍVEL` (`exigir_series`, CA-076), que é o comportamento correto: a
alternativa seria preencher a lacuna. Então o que roda no CI é o trecho que a fixture sustenta
(`curva` -> `build_raw_series`), e `test_pipeline_para_na_etapa_sem_insumo` fixa justamente a
parada. A reprodutibilidade da **camada inteira** (29 artefatos) é medida fora do CI, sobre
`data/processed/` real, e a evidência fica em `docs/wiki/context/F-029.md`.

**Sem marker novo:** `pyproject.toml` está congelado nesta onda e usa `--strict-markers`, então
estes testes rodam em `pytest tests/e2e` sem marca própria. Fixture ausente é **falha**, não
`skip` (`tests/fixtures/processed/README.md`).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from apps.pipeline.run import (
    NOME_MANIFESTO,
    FalhaDeEtapa,
    caminho_do_manifesto,
    executar,
    inventariar,
    main,
    verificar,
)

#: Até onde a fixture de `data/processed/` sustenta a cadeia (ver o docstring do módulo).
ETAPA_FINAL = "build_raw_series"


@pytest.fixture
def arvore_offline(tmp_path: Path, raiz_repo: Path) -> Path:
    """Uma árvore de repositório com `data/processed/` vindo de `tests/fixtures/processed/`."""
    origem = raiz_repo / "tests" / "fixtures" / "processed"
    assert origem.is_dir(), f"fixture obrigatória ausente: {origem} (nao e caso de skip)"
    destino = tmp_path / "data" / "processed"
    destino.parent.mkdir(parents=True)
    shutil.copytree(origem, destino)
    return tmp_path


def _hashes(raiz: Path) -> dict[str, str | None]:
    """`{arquivo: sha256}` do canônico — `None` no derivado declarado não determinístico."""
    return {
        artefato.arquivo: (artefato.sha256 if artefato.determinista else None)
        for artefato in inventariar(raiz=raiz)
    }


def test_duas_execucoes_offline_produzem_o_mesmo_hash(arvore_offline: Path) -> None:
    primeira = executar(raiz=arvore_offline, online=False, ate=ETAPA_FINAL)
    hashes_1 = _hashes(arvore_offline)
    manifesto_1 = caminho_do_manifesto(raiz=arvore_offline).read_bytes()

    segunda = executar(raiz=arvore_offline, online=False, ate=ETAPA_FINAL)
    hashes_2 = _hashes(arvore_offline)
    manifesto_2 = caminho_do_manifesto(raiz=arvore_offline).read_bytes()

    assert [e.situacao for e in primeira.executadas] == ["ok", "ok"]
    assert [e.nome for e in primeira.executadas] == ["curva", ETAPA_FINAL]
    assert hashes_1 == hashes_2, "artefato com hash diferente entre duas execucoes (CA-121)"
    assert primeira.agregado == segunda.agregado
    assert manifesto_1 == manifesto_2, "o MANIFEST.json tambem tem de ser byte-identico"
    # o agregado tem de cobrir algo: teste que passasse com 0 artefato não mediria nada.
    assert len([h for h in hashes_1.values() if h is not None]) >= 3


def test_o_que_a_rodada_produziu_bate_com_o_esperado(arvore_offline: Path) -> None:
    executar(raiz=arvore_offline, online=False, ate=ETAPA_FINAL)
    artefatos = {a.arquivo: a for a in inventariar(raiz=arvore_offline)}
    assert {"raw_series.parquet", "series_catalog.parquet", "relatorio_build.json"} <= set(
        artefatos
    )
    raw = artefatos["raw_series.parquet"]
    assert raw.linhas and raw.linhas > 500, "a fixture tem 7 series + painel; 0 linha seria bug"
    assert raw.date_min is not None and raw.date_max is not None
    assert artefatos["series_catalog.parquet"].linhas == 138
    # as 11 séries de curva saem para `data/processed/curva/`, não para o canônico
    assert (arvore_offline / "data" / "processed" / "curva").is_dir()


def test_verify_aprova_a_rodada_e_reprova_um_byte(arvore_offline: Path) -> None:
    executar(raiz=arvore_offline, online=False, ate=ETAPA_FINAL)
    assert verificar(raiz=arvore_offline).ok
    assert main(["verify", "--raiz", str(arvore_offline)]) == 0

    alvo = arvore_offline / "data" / "canonical" / "raw_series.parquet"
    corpo = bytearray(alvo.read_bytes())
    posicao = len(corpo) // 2
    corpo[posicao] = (corpo[posicao] + 1) % 256
    alvo.write_bytes(bytes(corpo))

    assert main(["verify", "--raiz", str(arvore_offline)]) == 1


def test_pipeline_para_na_etapa_sem_insumo(arvore_offline: Path) -> None:
    """A 3ª etapa exige séries que a fixture não tem: tem de **parar** e nomear a etapa."""
    with pytest.raises(FalhaDeEtapa) as capturado:
        executar(raiz=arvore_offline, online=False, ate="alinhamento")
    mensagem = str(capturado.value)
    assert "'alinhamento'" in mensagem
    assert "FONTE INDISPON" in mensagem
    assert "--so alinhamento" in mensagem
    assert not (arvore_offline / "data" / "canonical" / "alinhado_trimestral.parquet").exists(), (
        "etapa que falhou nao pode deixar artefato pela metade"
    )


def test_nada_e_escrito_fora_de_data(arvore_offline: Path) -> None:
    executar(raiz=arvore_offline, online=False, ate=ETAPA_FINAL)
    main(["verify", "--raiz", str(arvore_offline)])
    fora = [
        caminho.relative_to(arvore_offline).as_posix()
        for caminho in arvore_offline.rglob("*")
        if caminho.is_file() and caminho.relative_to(arvore_offline).parts[0] != "data"
    ]
    assert fora == [], f"o orquestrador escreveu fora de data/: {fora}"


def test_cli_offline_roda_de_ponta_a_ponta(arvore_offline: Path) -> None:
    codigo = main(
        ["run", "--offline", "--ate", ETAPA_FINAL, "--raiz", str(arvore_offline), "--sem-duckdb"]
    )
    assert codigo == 0
    assert (arvore_offline / "data" / "canonical" / NOME_MANIFESTO).is_file()
    assert not (arvore_offline / "data" / "canonical" / "ldc.duckdb").exists(), (
        "--sem-duckdb nao pode gravar o derivado"
    )
    # sem o derivado, TODO artefato do diretório entra no agregado
    assert all(artefato.determinista for artefato in inventariar(raiz=arvore_offline))
