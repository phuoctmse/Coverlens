"""Wires the concrete adapters and verifiers into one analysis run."""

from dataclasses import dataclass
from pathlib import Path

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter, SpecError
from coverlens.adapters.xlsx_suite import SuiteError, XlsxSuiteAdapter
from coverlens.cache.llm_cache import CachedClient, DiskCache
from coverlens.core.cascade import run_cascade
from coverlens.core.models import Case
from coverlens.core.pack import PackConfig, PackError, load_pack
from coverlens.core.pairwise import measure
from coverlens.core.protocols import Verifier
from coverlens.core.report import Report, build_report
from coverlens.verifiers.fake import FakeVerifier
from coverlens.verifiers.noop import NoopVerifier
from coverlens.verifiers.ollama import (
    DEFAULT_MODEL,
    DEFAULT_URL,
    OllamaError,
    OllamaTransport,
    OllamaVerifier,
)

INPUT_ERRORS = (PackError, SpecError, SuiteError)
DEFAULT_CACHE_DIR = Path(".coverlens_cache")


class JudgeUnavailableError(Exception):
    """The requested Tier 3 judge cannot be used."""


@dataclass(frozen=True)
class JudgeSettings:
    fake: bool = False
    model: str = DEFAULT_MODEL
    ollama_url: str = DEFAULT_URL
    cache_dir: Path = DEFAULT_CACHE_DIR


@dataclass(frozen=True)
class Analysis:
    report: Report
    llm_calls: int = 0  # real calls to the LLM in this run
    cache_hits: int = 0


def _tier3(
    judge: JudgeSettings, pack: PackConfig
) -> tuple[Verifier, CachedClient | None]:
    if judge.fake:
        return FakeVerifier(glossary=pack.glossary), None
    transport = OllamaTransport(judge.ollama_url)
    try:
        digest = transport.model_digest(judge.model)
    except OllamaError as exc:
        raise JudgeUnavailableError(f"{exc} (or pass --fake)") from exc
    client = CachedClient(transport, DiskCache(judge.cache_dir))
    return OllamaVerifier(client, judge.model, digest), client


def analyze(
    domain: Path, spec: Path, suite: Path | None, judge: JudgeSettings
) -> Analysis:
    """Read the inputs, run the cascade and build the report.

    Raises one of INPUT_ERRORS for bad inputs, JudgeUnavailableError when the
    Ollama model cannot be used.
    """
    pack = load_pack(domain)
    requirements = MarkdownSpecAdapter().read(spec, pack)
    cases: list[Case] = XlsxSuiteAdapter().read(suite, pack) if suite else []
    tier3, client = _tier3(judge, pack)
    result = run_cascade(requirements, cases, pack, [NoopVerifier(), tier3])
    pairwise = measure(pack.pairwise, cases) if pack.pairwise and cases else None
    report = build_report(requirements, cases, result, pack.name, pairwise)
    if client is None:
        return Analysis(report)
    return Analysis(report, llm_calls=client.calls, cache_hits=client.hits)
