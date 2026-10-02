"""Wires the concrete adapters and verifiers into one analysis run."""

from pathlib import Path

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter, SpecError
from coverlens.adapters.xlsx_suite import SuiteError, XlsxSuiteAdapter
from coverlens.core.cascade import run_cascade
from coverlens.core.models import Case
from coverlens.core.pack import PackError, load_pack
from coverlens.core.protocols import Verifier
from coverlens.core.report import Report, build_report
from coverlens.verifiers.fake import FakeVerifier
from coverlens.verifiers.noop import NoopVerifier

INPUT_ERRORS = (PackError, SpecError, SuiteError)


class JudgeUnavailableError(Exception):
    """The requested Tier 3 judge cannot be used."""


def analyze(domain: Path, spec: Path, suite: Path | None, *, fake: bool) -> Report:
    """Read the inputs, run the cascade and build the report.

    Raises one of INPUT_ERRORS for bad inputs, JudgeUnavailableError without --fake.
    """
    if not fake:
        raise JudgeUnavailableError(
            "the Ollama judge is not built yet; pass --fake for now"
        )
    pack = load_pack(domain)
    requirements = MarkdownSpecAdapter().read(spec, pack)
    cases: list[Case] = XlsxSuiteAdapter().read(suite, pack) if suite else []
    verifiers: list[Verifier] = [NoopVerifier(), FakeVerifier(glossary=pack.glossary)]
    result = run_cascade(requirements, cases, pack, verifiers)
    return build_report(requirements, cases, result, pack.name)
