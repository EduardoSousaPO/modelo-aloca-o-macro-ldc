"""Camadas `raw / processed / canonical`: resolução de caminho, arquivamento e hash.

As três camadas e suas regras estão em `CLAUDE.md §4`. Este módulo é a única porta de entrada
delas para o código, e existe para fazer valer quatro coisas que, feitas à mão em cada extrator,
viram dado perdido:

1. **Caminho ancorado na raiz do repositório**, nunca no `cwd`. `uv run pytest` da raiz, `jupyter`
   de dentro de `apps/analysis/` e o job diário disparado de qualquer pasta têm de gravar no mesmo
   lugar.
2. **Nome determinístico** (`<identificador>__<AAAA-MM-DD>.<ext>`): é o que torna o download
   idempotente e o que permite detectar o dia ausente da ANBIMA (R17) olhando a pasta.
3. **Hash + manifesto por arquivo.** `sha256` do corpo bruto é a base da reprodutibilidade
   (CA-121) e guarda `ETag`/`Last-Modified` para o cache condicional (R21: o CSV do Tesouro tem
   14,6 MB e é re-baixado todo dia).
4. **Nada entra em `data/processed/` sem passar por pandera.** `gravar_processado_parquet` valida
   com `ProcessedSeriesSchema` antes de escrever — é a tradução em código do CA-003 ("levanta erro
   explícito e **não grava nada** em `data/processed/`") e de `AGENTS.md §19`.

Anti-SPEC relevante: §10.4.21 (não commitar dado bruto — `data/` está no `.gitignore`),
§10.4.22 (nada em `data/` vem de edição manual), §10.1.4 (ausência não é `0`).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apps.pipeline.common.errors import ConteudoDivergente, ErroDeExtracao, ManifestoAusente
from apps.pipeline.common.logging_setup import obter_logger

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    import pandas as pd

    from packages.shared.schemas import ExtractorConfig

_log = obter_logger(__name__)

#: Arquivos que identificam a raiz do repositório. Procurados de baixo para cima a partir deste
#: módulo — nunca do `cwd`, que varia com quem dispara o processo.
MARCADORES_DA_RAIZ: tuple[str, ...] = ("pyproject.toml", "AGENTS.md")

SUFIXO_MANIFESTO = ".meta.json"
_SLUG_PROIBIDO = re.compile(r"[^A-Za-z0-9._^=-]+")


class Camada(StrEnum):
    """As três camadas de `data/` (`CLAUDE.md §4`). O valor é o nome da pasta."""

    RAW = "raw"
    PROCESSED = "processed"
    CANONICAL = "canonical"


# ─────────────────────────────────────────────────────────────────────────────
# Resolução de caminhos
# ─────────────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def raiz_repo() -> Path:
    """Raiz do repositório, achada subindo de `__file__` até encontrar os marcadores.

    Levanta `ErroDeExtracao` se não achar: é melhor falhar na importação do que gravar 20 anos de
    série numa pasta `data/` criada por acidente dentro de `apps/`.
    """
    atual = Path(__file__).resolve()
    for candidato in (atual, *atual.parents):
        if all((candidato / marcador).is_file() for marcador in MARCADORES_DA_RAIZ):
            return candidato
    msg = (
        f"raiz do repositório não encontrada a partir de {atual}: nenhum ancestral tem "
        f"{' + '.join(MARCADORES_DA_RAIZ)}"
    )
    raise ErroDeExtracao(msg)


def caminho_camada(camada: Camada, *, raiz: Path | None = None) -> Path:
    """`<raiz>/data/<camada>` — a pasta da camada, sem criar nada."""
    return (raiz or raiz_repo()) / "data" / Camada(camada).value


def caminho_raw(fonte: str, *, raiz: Path | None = None) -> Path:
    """`<raiz>/data/raw/<fonte>` — uma subpasta por fonte (`sgs/`, `anbima-ima/`, `b3/`…)."""
    return caminho_camada(Camada.RAW, raiz=raiz) / fonte


def caminho_destino_raw(config: ExtractorConfig, *, raiz: Path | None = None) -> Path:
    """Resolve `ExtractorConfig.destino_raw` (ex.: `data/raw/anbima-ima`) contra a raiz do repo.

    O próprio schema já valida o formato (`^data/raw/[a-z0-9\\-/]+$`), então aqui só se ancora:
    nenhum extrator monta esse caminho na mão.
    """
    return (raiz or raiz_repo()) / Path(config.destino_raw)


def caminho_processed(nome: str, *, raiz: Path | None = None) -> Path:
    """`<raiz>/data/processed/<nome>`."""
    return caminho_camada(Camada.PROCESSED, raiz=raiz) / nome


def caminho_canonical(nome: str, *, raiz: Path | None = None) -> Path:
    """`<raiz>/data/canonical/<nome>`. **Classe C**: escrever aqui exige contrato próprio."""
    return caminho_camada(Camada.CANONICAL, raiz=raiz) / nome


def garantir_diretorio(caminho: Path) -> Path:
    """Cria o diretório (com pais) se não existir e devolve o caminho."""
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


# ─────────────────────────────────────────────────────────────────────────────
# Nome determinístico e hash
# ─────────────────────────────────────────────────────────────────────────────


def _slug(valor: str) -> str:
    """Identificador seguro para nome de arquivo, preservando `^`, `=`, `.` e `-` dos tickers."""
    limpo = _SLUG_PROIBIDO.sub("-", valor.strip()).strip("-")
    if not limpo:
        msg = f"identificador {valor!r} não produz nome de arquivo utilizável"
        raise ErroDeExtracao(msg)
    return limpo


def nome_arquivo_raw(identificador: str, *, data_ref: date, extensao: str) -> str:
    """`<identificador>__<AAAA-MM-DD>.<ext>` — o nome determinístico da camada bruta.

    Mesmo identificador + mesma data de referência ⇒ mesmo nome ⇒ segundo download não duplica
    (é o que CA-027 pede do job diário da ANBIMA). A data é a de **referência do dado**, não a do
    relógio: rodar o job às 23h59 e às 00h01 do dia seguinte para o mesmo `Data Referencia` tem
    de cair no mesmo arquivo.
    """
    ext = extensao.lstrip(".").lower()
    if not ext:
        msg = "extensão vazia em nome_arquivo_raw"
        raise ErroDeExtracao(msg)
    return f"{_slug(identificador)}__{data_ref.isoformat()}.{ext}"


def sha256_de(conteudo: bytes) -> str:
    """`sha256` hexadecimal do corpo bruto — base da reprodutibilidade por hash (CA-121)."""
    return hashlib.sha256(conteudo).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Arquivamento em data/raw/
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoArquivamento:
    """O que aconteceu no arquivamento — o extrator loga isto em vez de adivinhar."""

    caminho: Path
    sha256: str
    bytes_gravados: int
    #: Já havia arquivo com este nome determinístico.
    ja_existia: bool
    #: Houve escrita em disco agora (falso quando o conteúdo era byte-idêntico ao arquivado).
    escreveu: bool

    @property
    def idempotente(self) -> bool:
        """`True` quando a execução não mudou nada em disco — o caso normal da 2ª rodada do dia."""
        return self.ja_existia and not self.escreveu


def _escrever_atomico(destino: Path, conteudo: bytes) -> None:
    """Grava via arquivo temporário + `os.replace`: nunca deixa arquivo meio escrito em `data/`."""
    garantir_diretorio(destino.parent)
    fd, temporario = tempfile.mkstemp(dir=destino.parent, prefix=f".{destino.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as saida:
            saida.write(conteudo)
        os.replace(temporario, destino)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise


def arquivar_bruto(
    conteudo: bytes,
    *,
    destino: Path,
    nome: str,
    origem: str = "",
    obtido_em: datetime | None = None,
    cabecalhos: dict[str, str] | None = None,
    sobrescrever_se_diferente: bool = False,
) -> ResultadoArquivamento:
    """Grava o corpo bruto em `destino/nome` de forma **idempotente** e com manifesto.

    - conteúdo byte-idêntico ao já arquivado → **não escreve** (`idempotente is True`);
    - conteúdo diferente no mesmo nome → `ConteudoDivergente`, salvo
      `sobrescrever_se_diferente=True`. Sobrescrever em silêncio apagaria dado de janela rolante
      (R8), que não se recupera;
    - sempre escreve/atualiza `<nome>.meta.json` com `sha256`, tamanho, `origem`, `obtido_em`,
      `ETag` e `Last-Modified` — o insumo do cache condicional (R21) e da conferência por hash.

    Corpo vazio é gravado se quem chama pediu: dia sem divulgação da ANBIMA é caso **normal**
    (R17, `ExtractorConfig.ausencia_e_caso_normal`), e a decisão de aceitá-lo é do extrator.
    """
    alvo = Path(destino) / nome
    digest = sha256_de(conteudo)
    ja_existia = alvo.is_file()
    escreveu = True

    if ja_existia:
        atual = sha256_de(alvo.read_bytes())
        if atual == digest:
            escreveu = False
            _log.info("arquivamento idempotente: %s (sha256=%s…)", alvo.name, digest[:12])
        elif not sobrescrever_se_diferente:
            msg = (
                f"{alvo} já existe com conteúdo diferente (sha256 em disco {atual[:12]}… vs "
                f"{digest[:12]}… agora). Sobrescrever apagaria dado que a fonte pode não servir de "
                f"novo (janela rolante, R8): use outro nome ou sobrescrever_se_diferente=True"
            )
            raise ConteudoDivergente(msg)

    if escreveu:
        _escrever_atomico(alvo, conteudo)
        _log.info("arquivado %s (%d bytes, sha256=%s…)", alvo.name, len(conteudo), digest[:12])

    _escrever_manifesto(
        alvo,
        sha256=digest,
        tamanho=len(conteudo),
        origem=origem,
        obtido_em=obtido_em,
        cabecalhos=cabecalhos or {},
    )
    return ResultadoArquivamento(
        caminho=alvo,
        sha256=digest,
        bytes_gravados=len(conteudo),
        ja_existia=ja_existia,
        escreveu=escreveu,
    )


def _escrever_manifesto(
    alvo: Path,
    *,
    sha256: str,
    tamanho: int,
    origem: str,
    obtido_em: datetime | None,
    cabecalhos: dict[str, str],
) -> Path:
    normalizados = {chave.lower(): valor for chave, valor in cabecalhos.items()}
    manifesto = {
        "arquivo": alvo.name,
        "sha256": sha256,
        "bytes": tamanho,
        "origem": origem,
        "obtido_em": (obtido_em.isoformat() if obtido_em else None),
        "etag": normalizados.get("etag"),
        "last_modified": normalizados.get("last-modified"),
        "content_type": normalizados.get("content-type"),
    }
    caminho = alvo.with_name(alvo.name + SUFIXO_MANIFESTO)
    # `sort_keys` + `ensure_ascii=False` + encoding explícito: manifesto idêntico entre execuções.
    caminho.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return caminho


def ler_manifesto(alvo: Path) -> dict[str, Any] | None:
    """Manifesto de um arquivo arquivado, ou `None` se ainda não existe.

    É daqui que o cache condicional tira `ETag`/`Last-Modified` para a próxima requisição.
    """
    caminho = Path(alvo).with_name(Path(alvo).name + SUFIXO_MANIFESTO)
    if not caminho.is_file():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def obtido_em_arquivado(alvo: Path) -> datetime | None:
    """`obtido_em` do manifesto do bruto — a **única** origem de `collected_at`/`vintage`.

    Convenção da Onda 1 (D-b, `docs/plans/DECISIONS_LOG.md §2`): `collected_at` da camada
    processada sai daqui, não do relógio da rodada, e `vintage` é a **data** (sem hora) desse
    `collected_at`. É o que torna `--offline` reprodutível: reprocessar o mesmo bruto duas vezes
    produz o mesmo Parquet, byte a byte, porque nenhum dos dois valores depende de quando o
    reprocessamento aconteceu.

    Devolve `None` quando não há manifesto, quando o campo está vazio ou quando a string não é
    ISO-8601 (manifesto de outra versão) — quem chama decide o fallback.
    """
    manifesto = ler_manifesto(alvo)
    if not manifesto:
        return None
    bruto = manifesto.get("obtido_em")
    if not bruto:
        return None
    try:
        return datetime.fromisoformat(str(bruto))
    except ValueError:
        _log.warning("manifesto de %s com obtido_em inválido: %r", Path(alvo).name, bruto)
        return None


def collected_at_do_bruto(alvo: Path, *, collected_at: datetime | None = None) -> datetime:
    """`collected_at` de um bruto arquivado — do manifesto, ou **recusa**.

    É `obtido_em_arquivado` com o fallback fechado. Existe porque o idioma
    `obtido_em_arquivado(alvo) or datetime.now(tz=UTC)` apareceu em todos os extratores e tem um
    modo de falha silencioso: bruto sem `.meta.json` (uma amostra de pesquisa copiada à mão, um
    arquivo recuperado de backup, uma fixture passada por `caminho=`) faz `collected_at` — e
    portanto `vintage` — sair do **relógio da rodada**. Aí D-b deixa de valer e duas execuções
    `--offline` sobre o mesmo bruto gravam Parquets diferentes (CA-121, Anti-SPEC §10.4.22).

    `collected_at` explícito tem precedência: é como o teste e o reprocessamento deliberado
    assumem a safra por escrito, em vez de herdá-la do relógio por omissão.
    """
    if collected_at is not None:
        return collected_at
    obtido = obtido_em_arquivado(alvo)
    if obtido is not None:
        return obtido
    alvo = Path(alvo)
    msg = (
        f"{alvo.name}: bruto sem manifesto legível ({alvo.name}{SUFIXO_MANIFESTO}) — sem ele "
        f"`collected_at`/`vintage` sairiam do relógio desta rodada e o Parquet deixaria de ser "
        f"reproduzível (D-b, CA-121). Rode a extração **online** uma vez (o manifesto nasce aí) "
        f"ou passe `collected_at=` explicitamente."
    )
    raise ManifestoAusente(msg)


def validadores_condicionais(alvo: Path) -> tuple[str | None, str | None]:
    """`(etag, last_modified)` do que já está arquivado — entrada de `ClienteHTTP.get`."""
    manifesto = ler_manifesto(alvo)
    if not manifesto:
        return (None, None)
    return (manifesto.get("etag"), manifesto.get("last_modified"))


# ─────────────────────────────────────────────────────────────────────────────
# Escrita em data/processed/
# ─────────────────────────────────────────────────────────────────────────────


def gravar_processado_parquet(
    quadro: pd.DataFrame,
    *,
    nome: str,
    raiz: Path | None = None,
) -> Path:
    """Valida com `ProcessedSeriesSchema` (pandera) e **só então** grava em `data/processed/`.

    Inverter a ordem é o que CA-003 proíbe: resposta inválida não deixa rastro na camada
    processada. A validação é importada aqui dentro para que `io_layers` continue importável sem
    pandas/pandera (o `ClienteHTTP` não precisa deles).
    """
    from packages.shared.schemas import ProcessedSeriesSchema

    validado = ProcessedSeriesSchema.validate(quadro, lazy=True)
    destino = caminho_processed(nome, raiz=raiz)
    garantir_diretorio(destino.parent)
    validado.to_parquet(destino, index=False)
    _log.info("gravado %s (%d linhas)", destino.name, len(validado))
    return destino
