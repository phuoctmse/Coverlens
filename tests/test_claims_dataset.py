"""The claims dataset in data/claims/ must match its generator."""

import json
from pathlib import Path

import openpyxl

from eval.datasets import build_claims

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "claims"


def cells(path: Path) -> list[tuple[object, ...]]:
    workbook = openpyxl.load_workbook(path, read_only=True)
    rows = list(workbook.active.iter_rows(values_only=True))  # type: ignore[union-attr]
    workbook.close()
    return rows


def test_labels_are_consistent() -> None:
    build_claims.check()


def test_data_matches_a_fresh_build(tmp_path: Path) -> None:
    build_claims.build(tmp_path)
    for name in ("user_stories.md", "answer_key.json"):
        assert (tmp_path / name).read_text("utf-8") == (DATA / name).read_text("utf-8")
    assert cells(tmp_path / "test_cases.xlsx") == cells(DATA / "test_cases.xlsx")


def test_key_shape() -> None:
    key = json.loads((DATA / "answer_key.json").read_text("utf-8"))
    assert key["requirements"] == 100
    assert key["cases"] == 120
    assert len(key["covered"]) + len(key["true_gaps"]) == 100
    assert len(key["orphan_cases"]) == 4
    assert len(key["decoys_claiming_gap_acs"]) == 7
