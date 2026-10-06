"""Bootstrap confidence intervals and paired comparison of two eval runs.

With 52 requirements one flipped verdict moves accuracy by about 2 points, so a
change only counts as a gain or a loss when the paired 95% interval of the
difference excludes zero.
"""

import json
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

RESAMPLES = 2000
LEVEL = 0.95
Verdict = Literal["gain", "loss", "noise"]


@dataclass(frozen=True)
class Outcome:
    predicted: str  # covered, gap or uncertain
    gold: str  # covered or gap

    @property
    def correct(self) -> bool:
        return self.predicted == self.gold


Metric = Callable[[Sequence[Outcome]], float | None]


def accuracy(rows: Sequence[Outcome]) -> float | None:
    return sum(r.correct for r in rows) / len(rows) if rows else None


def precision(rows: Sequence[Outcome], label: str) -> float | None:
    said = [r for r in rows if r.predicted == label]
    return sum(r.gold == label for r in said) / len(said) if said else None


def recall(rows: Sequence[Outcome], label: str) -> float | None:
    actual = [r for r in rows if r.gold == label]
    return sum(r.predicted == label for r in actual) / len(actual) if actual else None


def _percentiles(values: list[float], level: float) -> tuple[float, float]:
    values.sort()
    tail = (1 - level) / 2
    low = values[int(tail * (len(values) - 1))]
    high = values[round((1 - tail) * (len(values) - 1))]
    return low, high


def bootstrap_interval(
    rows: Sequence[Outcome],
    metric: Metric,
    resamples: int = RESAMPLES,
    seed: int = 0,
    level: float = LEVEL,
) -> tuple[float, float] | None:
    """Percentile interval of `metric` over resampled requirement sets."""
    rng = random.Random(seed)
    values = []
    for _ in range(resamples):
        value = metric(rng.choices(rows, k=len(rows)))
        if value is not None:
            values.append(value)
    return _percentiles(values, level) if values else None


@dataclass(frozen=True)
class Comparison:
    base_accuracy: float
    new_accuracy: float
    delta: float
    low: float
    high: float
    verdict: Verdict
    fixed: tuple[str, ...]  # wrong in base, right now
    broke: tuple[str, ...]  # right in base, wrong now


def compare(
    base: Mapping[str, Outcome],
    new: Mapping[str, Outcome],
    resamples: int = RESAMPLES,
    seed: int = 0,
) -> Comparison:
    """Paired bootstrap of the accuracy difference, resampling requirements."""
    if set(base) != set(new):
        odd = sorted(set(base) ^ set(new))
        raise ValueError(f"runs judge different requirements: {odd}")
    ids = sorted(base)
    diffs = [int(new[i].correct) - int(base[i].correct) for i in ids]
    rng = random.Random(seed)
    samples = [
        sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(resamples)
    ]
    low, high = _percentiles(samples, LEVEL)
    verdict: Verdict = "gain" if low > 0 else "loss" if high < 0 else "noise"
    return Comparison(
        base_accuracy=sum(base[i].correct for i in ids) / len(ids),
        new_accuracy=sum(new[i].correct for i in ids) / len(ids),
        delta=sum(diffs) / len(diffs),
        low=low,
        high=high,
        verdict=verdict,
        fixed=tuple(i for i in ids if new[i].correct and not base[i].correct),
        broke=tuple(i for i in ids if base[i].correct and not new[i].correct),
    )


def save_outcomes(path: Path, outcomes: Mapping[str, Outcome], label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"label": label, "outcomes": {k: asdict(v) for k, v in outcomes.items()}}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_outcomes(path: Path) -> dict[str, Outcome]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: Outcome(**v) for k, v in data["outcomes"].items()}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"{path}: cannot load saved eval run: {exc}") from exc


def load_label(path: Path) -> str:
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("label", ""))
    except OSError, ValueError:
        return ""
