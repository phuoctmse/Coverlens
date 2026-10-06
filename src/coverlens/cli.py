"""Command line: `coverlens run --domain PACK --spec SPEC [--suite SUITE] --out DIR --fake`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from coverlens.pipeline import (
    DEFAULT_CACHE_DIR,
    INPUT_ERRORS,
    Analysis,
    JudgeSettings,
    JudgeUnavailableError,
    analyze,
)
from coverlens.verifiers.ollama import DEFAULT_MODEL, DEFAULT_URL
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
    run.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag")
    run.add_argument("--ollama-url", default=DEFAULT_URL, help="Ollama server URL")
    run.add_argument(
        "--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="LLM cache folder"
    )
    return parser


def judge_settings(args: argparse.Namespace) -> JudgeSettings:
    return JudgeSettings(
        fake=args.fake,
        model=args.model,
        ollama_url=args.ollama_url,
        cache_dir=args.cache_dir,
    )


def run_pipeline(args: argparse.Namespace) -> tuple[Analysis, list[Path]]:
    try:
        analysis = analyze(args.domain, args.spec, args.suite, judge_settings(args))
    except (*INPUT_ERRORS, JudgeUnavailableError) as exc:
        raise CliError(str(exc)) from exc
    try:
        written = [
            writer.write(analysis.report, args.out)
            for writer in (ExcelWriter(), JsonWriter())
        ]
    except OSError as exc:
        raise CliError(
            f"cannot write the report to {args.out} (is the file open in Excel?): {exc}"
        ) from exc
    return analysis, written


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        analysis, written = run_pipeline(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    report = analysis.report
    s = report.summary
    for path in written:
        print(f"Wrote {path}")
    print(
        f"Covered {s.covered}/{s.requirements} ({s.coverage:.0%}), gaps {s.gap}"
        f", uncertain {s.uncertain}, orphans {len(report.orphan_case_ids)}"
        f", mis-referenced {len(report.mis_referenced)}"
    )
    if report.pairwise is not None:
        pw = report.pairwise
        print(
            f"Dimension pairs {pw.covered}/{pw.required} ({pw.coverage:.0%}),"
            f" {pw.extra_combinations} more combinations would cover the rest"
        )
    if not args.fake:
        print(analysis.cost_line())
    return 0
