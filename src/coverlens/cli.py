"""Command line: `coverlens run --domain PACK --spec SPEC [--suite SUITE] --out DIR --fake`."""

import argparse
import sys
from collections.abc import Sequence
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
from coverlens.writers.excel_writer import ExcelWriter
from coverlens.writers.json_writer import JsonWriter


class CliError(Exception):
    """A problem the user can fix; printed without a traceback."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coverlens",
        description="Measure whether a test suite covers a feature's requirements.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="write a gap report for one spec")
    run.add_argument("--domain", type=Path, required=True, help="domain pack YAML")
    run.add_argument("--spec", type=Path, required=True, help="spec markdown")
    run.add_argument("--suite", type=Path, help="existing test suite (.xlsx)")
    run.add_argument("--out", type=Path, default=Path("out"), help="output folder")
    run.add_argument(
        "--fake",
        action="store_true",
        help="use the offline fake judge instead of the LLM",
    )
    return parser


def run_pipeline(args: argparse.Namespace) -> tuple[Report, list[Path]]:
    if not args.fake:
        raise CliError("the Ollama judge is not built yet; pass --fake for now")
    try:
        pack = load_pack(args.domain)
        requirements = MarkdownSpecAdapter().read(args.spec, pack)
        cases: list[Case] = (
            XlsxSuiteAdapter().read(args.suite, pack) if args.suite else []
        )
    except (PackError, SpecError, SuiteError) as exc:
        raise CliError(str(exc)) from exc

    verifiers: list[Verifier] = [NoopVerifier(), FakeVerifier(glossary=pack.glossary)]
    result = run_cascade(requirements, cases, pack, verifiers)
    report = build_report(requirements, cases, result, pack.name)
    try:
        written = [
            writer.write(report, args.out) for writer in (ExcelWriter(), JsonWriter())
        ]
    except OSError as exc:
        raise CliError(
            f"cannot write the report to {args.out} (is the file open in Excel?): {exc}"
        ) from exc
    return report, written


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, written = run_pipeline(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    s = report.summary
    for path in written:
        print(f"Wrote {path}")
    print(
        f"Covered {s.covered}/{s.requirements} ({s.coverage:.0%}), gaps {s.gap}"
        f", uncertain {s.uncertain}, orphans {len(report.orphan_case_ids)}"
        f", mis-referenced {len(report.mis_referenced)}"
    )
    return 0
