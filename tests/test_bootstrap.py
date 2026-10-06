import json
from pathlib import Path

import pytest

from eval.__main__ import main
from eval.bootstrap import (
    Outcome,
    accuracy,
    bootstrap_interval,
    compare,
    load_outcomes,
    precision,
    recall,
    save_outcomes,
)


def outcomes(correct: int, wrong: int) -> dict[str, Outcome]:
    """`correct` covered-and-right, then `wrong` covered-but-gap requirements."""
    result = {
        f"R-{n}": Outcome(predicted="covered", gold="covered") for n in range(correct)
    }
    for n in range(correct, correct + wrong):
        result[f"R-{n}"] = Outcome(predicted="gap", gold="covered")
    return result


# --- metrics on outcomes -------------------------------------------------------


def test_outcome_is_correct_when_prediction_matches_gold() -> None:
    assert Outcome(predicted="gap", gold="gap").correct
    assert not Outcome(predicted="uncertain", gold="gap").correct


def test_metric_functions() -> None:
    rows = [
        Outcome(predicted="gap", gold="gap"),
        Outcome(predicted="gap", gold="covered"),
        Outcome(predicted="covered", gold="covered"),
        Outcome(predicted="uncertain", gold="gap"),
    ]
    assert accuracy(rows) == 0.5
    assert precision(rows, "gap") == 0.5
    assert recall(rows, "gap") == 0.5
    assert precision(rows, "covered") == 1.0
    assert recall(rows, "covered") == 0.5


def test_undefined_rates_are_none() -> None:
    rows = [Outcome(predicted="gap", gold="gap")]
    assert precision(rows, "covered") is None
    assert recall(rows, "covered") is None


# --- bootstrap intervals -------------------------------------------------------


def test_interval_is_reproducible_and_contains_the_estimate() -> None:
    rows = list(outcomes(46, 6).values())
    low, high = bootstrap_interval(rows, accuracy, seed=1)
    assert (low, high) == bootstrap_interval(rows, accuracy, seed=1)
    assert low < 46 / 52 < high
    assert high - low > 0.1  # 52 items is a small sample


def test_perfect_results_have_a_degenerate_interval() -> None:
    rows = list(outcomes(10, 0).values())
    assert bootstrap_interval(rows, accuracy) == (1.0, 1.0)


# --- paired comparison ---------------------------------------------------------


def test_identical_runs_are_noise() -> None:
    base = outcomes(46, 6)
    result = compare(base, base)
    assert result.delta == 0
    assert result.verdict == "noise"
    assert (result.fixed, result.broke) == ((), ())


def test_one_flip_in_52_is_noise() -> None:
    base = outcomes(46, 6)
    new = dict(base) | {"R-46": Outcome(predicted="covered", gold="covered")}
    result = compare(base, new)
    assert result.fixed == ("R-46",)
    assert result.verdict == "noise"


def test_many_fixes_are_a_gain_and_the_reverse_a_loss() -> None:
    base, new = outcomes(30, 22), outcomes(50, 2)
    assert compare(base, new).verdict == "gain"
    assert compare(new, base).verdict == "loss"


def test_runs_must_cover_the_same_requirements() -> None:
    with pytest.raises(ValueError, match="R-9"):
        compare(outcomes(3, 0), outcomes(3, 0) | {"R-9": Outcome("gap", "gap")})


# --- saving and loading --------------------------------------------------------


def test_outcomes_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    save_outcomes(path, outcomes(3, 1), label="judge-v1")
    assert load_outcomes(path) == outcomes(3, 1)
    assert json.loads(path.read_text("utf-8"))["label"] == "judge-v1"


def test_loading_a_bad_file_says_which(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.json"):
        load_outcomes(path)


# --- eval command line ---------------------------------------------------------


def test_eval_prints_intervals_saves_and_compares(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    saved = tmp_path / "base.json"
    assert main(["--fake", "--save", str(saved)]) == 0
    out = capsys.readouterr().out
    assert "Accuracy" in out
    assert "95% CI" in out
    assert saved.is_file()

    assert main(["--fake", "--compare", str(saved)]) == 0
    out = capsys.readouterr().out
    assert "Compared with" in out
    assert "within noise" in out


def test_eval_compare_with_a_missing_file_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--fake", "--compare", str(tmp_path / "nope.json")]) == 1
    assert "nope.json" in capsys.readouterr().err
