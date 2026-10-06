"""Wires the concrete adapters and verifiers into one analysis run."""

import time
from dataclasses import dataclass, field
from pathlib import Path

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter, SpecError
from coverlens.adapters.xlsx_suite import SuiteError, XlsxSuiteAdapter
from coverlens.cache.llm_cache import CachedClient, DiskCache, LlmUsage
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
    DEFAULT_OPTIONS,
    DEFAULT_URL,
    OllamaError,
    OllamaTransport,
    OllamaVerifier,
)
from coverlens.verifiers.overlap import OverlapVerifier

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
    num_ctx: int = DEFAULT_OPTIONS["num_ctx"]


@dataclass(frozen=True)
class Analysis:
    report: Report
    llm_calls: int = 0  # real calls to the LLM in this run
    cache_hits: int = 0
    usage: LlmUsage = field(default_factory=LlmUsage)  # spent on real calls in this run
    cached_usage: LlmUsage = field(
        default_factory=LlmUsage
    )  # avoided thanks to the cache
    seconds: float = 0.0  # wall time of the whole analysis

    def cost_line(self) -> str:
        spent, saved = self.usage, self.cached_usage
        line = (
            f"LLM calls {self.llm_calls}, cache hits {self.cache_hits}"
            f" | tokens {spent.prompt_tokens:,} in / {spent.output_tokens:,} out"
            f" | LLM {spent.seconds:.1f} s | run {self.seconds:.1f} s"
        )
        if self.cache_hits:
            line += (
                f" | cache saved {saved.prompt_tokens:,} in"
                f" / {saved.output_tokens:,} out, {saved.seconds:.1f} s"
            )
        return line


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
    options = {**DEFAULT_OPTIONS, "num_ctx": judge.num_ctx}
    return OllamaVerifier(client, judge.model, digest, options), client


def analyze(
    domain: Path, spec: Path, suite: Path | None, judge: JudgeSettings
) -> Analysis:
    """Read the inputs, run the cascade and build the report.

    Raises one of INPUT_ERRORS for bad inputs, JudgeUnavailableError when the
    Ollama model cannot be used.
    """
    started = time.perf_counter()
    pack = load_pack(domain)
    requirements = MarkdownSpecAdapter().read(spec, pack)
    cases: list[Case] = XlsxSuiteAdapter().read(suite, pack) if suite else []
    tier3, client = _tier3(judge, pack)
    tier2: Verifier = (
        OverlapVerifier(pack.tier2.min_overlap, pack.glossary)
        if pack.tier2
        else NoopVerifier()
    )
    result = run_cascade(requirements, cases, pack, [tier2, tier3])
    pairwise = measure(pack.pairwise, cases) if pack.pairwise and cases else None
    report = build_report(requirements, cases, result, pack.name, pairwise)
    if client is None:
        return Analysis(report, seconds=time.perf_counter() - started)
    return Analysis(
        report,
        llm_calls=client.calls,
        cache_hits=client.hits,
        usage=client.usage,
        cached_usage=client.cached_usage,
        seconds=time.perf_counter() - started,
    )
