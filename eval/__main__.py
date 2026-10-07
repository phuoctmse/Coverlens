"""`python -m eval --fake`: run the pipeline on the dev data and score it.

Prints 95% bootstrap intervals; `--save` stores the run and `--compare` checks
whether a change against a saved run is a real gain, a real loss, or noise.
Exits 1 if the inputs are bad or the canary fails.
"""

import argparse
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from coverlens.adapters.xlsx_suite import XlsxSuiteAdapter
from coverlens.cli import positive_int
from coverlens.core.pack import load_pack
from coverlens.core.report import Report
from coverlens.pipeline import (
    API_KEY_ENV,
    DEFAULT_CACHE_DIR,
    INPUT_ERRORS,
    JudgeSettings,
    JudgeUnavailableError,
    analyze,
    resolve_api_key,
)
from coverlens.verifiers.ollama import (
    DEFAULT_MODEL,
    DEFAULT_OPTIONS,
    DEFAULT_URL,
    TEMPLATE_VERSION,
)
from eval.answer_key import DATASETS, AnswerKey, dataset_paths, load_key
from eval.bootstrap import (
    Comparison,
    Metric,
    Outcome,
    accuracy,
    bootstrap_interval,
    compare,
    load_label,
    load_outcomes,
    precision,
    recall,
    save_outcomes,
)
from eval.disagreements import format_disagreements
from eval.label_review import (
    apply_reviews,
    changed_count,
    load_reviews,
)
from eval.metrics import evaluate, format_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m eval")
    parser.add_argument(
        "--dataset",
        choices=DATASETS,
        default="ott_web",
        help="dataset whose pack, inputs, key and reviews to use",
    )
    parser.add_argument("--domain", type=Path, help="override the dataset's pack")
    parser.add_argument("--spec", type=Path, help="override the dataset's spec")
    parser.add_argument("--suite", type=Path, help="override the dataset's suite")
    parser.add_argument("--key", type=Path, help="override the dataset's key")
    parser.add_argument("--fake", action="store_true", help="offline fake judge")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_URL)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--num-ctx", type=positive_int, default=DEFAULT_OPTIONS["num_ctx"]
    )
    parser.add_argument(
        "--num-predict",
        type=positive_int,
        default=DEFAULT_OPTIONS["num_predict"],
        help="cap on reply tokens (raise it for thinking models)",
    )
    parser.add_argument(
        "--no-tier2",
        dest="tier2",
        action="store_false",
        help="skip the Tier 2 overlap rule (useful with a strong LLM judge)",
    )
    parser.add_argument(
        "--api-key-file",
        type=Path,
        help=f"file holding an Ollama Cloud key (default: ${API_KEY_ENV})",
    )
    parser.add_argument("--save", type=Path, help="store this run for --compare")
    parser.add_argument("--compare", type=Path, help="a run saved with --save")
    parser.add_argument("--reviews", type=Path, help="override the label reviews")
    parser.add_argument(
        "--disagreements",
        action="store_true",
        help="list where the pipeline and the key disagree, for review",
    )
    return parser


def outcomes_of(report: Report, key: AnswerKey) -> dict[str, Outcome]:
    return {
        row.requirement_id: Outcome(
            predicted=row.status.value,
            gold="covered" if row.requirement_id in key.covered else "gap",
        )
        for row in report.requirements
    }


def format_intervals(outcomes: dict[str, Outcome]) -> str:
    rows = list(outcomes.values())
    metrics: list[tuple[str, Metric]] = [
        ("Accuracy", accuracy),
        ("Gap precision", partial(precision, label="gap")),
        ("Gap recall", partial(recall, label="gap")),
        ("Covered precision", partial(precision, label="covered")),
        ("Covered recall", partial(recall, label="covered")),
    ]
    correct = sum(r.correct for r in rows)
    lines = [f"Accuracy            {correct}/{len(rows)} ({correct / len(rows):.0%})"]
    lines.append("95% CI (bootstrap over requirements):")
    for name, metric in metrics:
        value, interval = metric(rows), bootstrap_interval(rows, metric)
        if value is None or interval is None:
            lines.append(f"  {name:<18}n/a")
        else:
            low, high = interval
            lines.append(f"  {name:<18}{value:.0%}  [{low:.0%}, {high:.0%}]")
    return "\n".join(lines)


def format_comparison(result: Comparison, path: Path) -> str:
    verdict = {
        "gain": "a real gain",
        "loss": "a real loss",
        "noise": "within noise",
    }[result.verdict]
    label = load_label(path)
    lines = [
        f"Compared with {path}" + (f" ({label})" if label else ""),
        (
            f"  accuracy {result.base_accuracy:.0%} -> {result.new_accuracy:.0%},"
            f" change {result.delta:+.1%},"
            f" 95% CI [{result.low:+.1%}, {result.high:+.1%}]: {verdict}"
        ),
        f"  fixed: {', '.join(result.fixed) or '-'}",
        f"  broke: {', '.join(result.broke) or '-'}",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = dataset_paths(args.dataset)
    args.domain = args.domain or paths.pack
    args.spec = args.spec or paths.spec
    args.suite = args.suite or paths.suite
    args.key = args.key or paths.key
    args.reviews = args.reviews or paths.reviews
    try:
        key = load_key(args.key)
        base = load_outcomes(args.compare) if args.compare else None
        judge = JudgeSettings(
            fake=args.fake,
            model=args.model,
            ollama_url=args.ollama_url,
            cache_dir=args.cache_dir,
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
            tier2=args.tier2,
            api_key=resolve_api_key(args.api_key_file),
        )
        analysis = analyze(args.domain, args.spec, args.suite, judge)
        result = evaluate(analysis.report, key)
        outcomes = outcomes_of(analysis.report, key)
        comparison = compare(base, outcomes) if base is not None else None
        reviews = load_reviews(args.reviews, key)
        cases = (
            {
                c.id: c
                for c in XlsxSuiteAdapter().read(args.suite, load_pack(args.domain))
            }
            if args.disagreements
            else {}
        )
    except (*INPUT_ERRORS, JudgeUnavailableError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_result(result))
    print(format_intervals(outcomes))
    if comparison is not None and args.compare is not None:
        print(format_comparison(comparison, args.compare))
    changed = changed_count(reviews)
    if changed:
        reviewed = outcomes_of(analysis.report, apply_reviews(key, reviews))
        plural = "" if changed == 1 else "s"
        print(f"Against the reviewed key ({changed} label{plural} changed):")
        print(format_intervals(reviewed))
    if args.disagreements:
        by_id = {r.requirement_id: r for r in reviews}
        print(
            format_disagreements(
                analysis.report, key, cases, by_id, reviews_path=str(args.reviews)
            )
        )
    if not args.fake:
        print(analysis.cost_line())
    if args.save:
        label = "fake" if args.fake else f"{args.model} {TEMPLATE_VERSION}"
        save_outcomes(args.save, outcomes, label)
        print(f"Saved this run to {args.save}")
    return 0 if result.canary_ok else 1


if __name__ == "__main__":
    sys.exit(main())
