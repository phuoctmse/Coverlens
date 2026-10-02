"""`python -m eval --fake`: run the pipeline on the dev data and score it.

Exits 1 if the inputs are bad or the canary fails.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from coverlens.pipeline import INPUT_ERRORS, JudgeUnavailableError, analyze
from eval.answer_key import DATA_DIR, DEFAULT_KEY, load_key
from eval.metrics import evaluate, format_result

DEFAULT_PACK = DATA_DIR.parents[1] / "domains" / "ott_web" / "pack.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m eval")
    parser.add_argument("--domain", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--spec", type=Path, default=DATA_DIR / "user_stories.md")
    parser.add_argument("--suite", type=Path, default=DATA_DIR / "test_cases.xlsx")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--fake", action="store_true", help="offline fake judge")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        key = load_key(args.key)
        report = analyze(args.domain, args.spec, args.suite, fake=args.fake)
        result = evaluate(report, key)
    except (*INPUT_ERRORS, JudgeUnavailableError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_result(result))
    return 0 if result.canary_ok else 1


if __name__ == "__main__":
    sys.exit(main())
