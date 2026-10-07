"""Command line: `coverlens run --domain PACK --spec SPEC [--suite SUITE] --out DIR --fake`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from coverlens.pipeline import (
    API_KEY_ENV,
    DEFAULT_CACHE_DIR,
    INPUT_ERRORS,
    Analysis,
    JudgeSettings,
    JudgeUnavailableError,
    analyze,
    resolve_api_key,
)
from coverlens.verifiers.ollama import DEFAULT_MODEL, DEFAULT_OPTIONS, DEFAULT_URL
from coverlens.writers.excel_writer import ExcelWriter
from coverlens.writers.json_writer import JsonWriter


class CliError(Exception):
    """A problem the user can fix; printed without a traceback."""


def safe_stdout() -> None:
    """Replace characters the console cannot encode instead of crashing.

    LLM rationales can hold characters such as U+202F that a Windows console or
    a redirected cp1252 stream cannot encode.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value}")
    return value


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
    run.add_argument(
        "--num-ctx",
        type=positive_int,
        default=DEFAULT_OPTIONS["num_ctx"],
        help="LLM context window in tokens",
    )
    run.add_argument(
        "--num-predict",
        type=positive_int,
        default=DEFAULT_OPTIONS["num_predict"],
        help="cap on reply tokens (raise it for thinking models)",
    )
    run.add_argument(
        "--no-tier2",
        dest="tier2",
        action="store_false",
        help="skip the Tier 2 overlap rule (useful with a strong LLM judge)",
    )
    run.add_argument(
        "--api-key-file",
        type=Path,
        help=f"file holding an Ollama Cloud key (default: ${API_KEY_ENV})",
    )
    return parser


def judge_settings(args: argparse.Namespace) -> JudgeSettings:
    return JudgeSettings(
        fake=args.fake,
        model=args.model,
        ollama_url=args.ollama_url,
        cache_dir=args.cache_dir,
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
        tier2=args.tier2,
        api_key=resolve_api_key(args.api_key_file),
    )


def run_pipeline(args: argparse.Namespace) -> tuple[Analysis, list[Path]]:
    try:
        analysis = analyze(args.domain, args.spec, args.suite, judge_settings(args))
    except (*INPUT_ERRORS, JudgeUnavailableError, ValueError) as exc:
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
    safe_stdout()
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
