from pathlib import Path

import pytest

from eval.__main__ import main
from eval.answer_key import AnswerKey, Decoy
from eval.label_review import Review, apply_reviews, load_reviews

KEY = AnswerKey(
    covered={"A.1": ("T-1",), "A.2": ("T-2",)},
    true_gaps=("A.3",),
    decoys_claiming_gap_acs=(Decoy(id="T-9", claims="A.3"),),
    orphan_cases=(),
)

VALID = """\
reviews:
  - requirement_id: A.3
    key_label: gap
    reviewed_label: covered
    covered_by: [T-3]
    note: T-3 checks it on two browsers.
    reviewer: phuoctmse
    date: 2026-10-07
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "label_review.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_review_file_loads(tmp_path: Path) -> None:
    [review] = load_reviews(write(tmp_path, VALID), KEY)
    assert (review.requirement_id, review.reviewed_label) == ("A.3", "covered")
    assert review.covered_by == ("T-3",)


def test_missing_or_empty_file_means_no_reviews(tmp_path: Path) -> None:
    assert load_reviews(tmp_path / "absent.yaml", KEY) == []
    assert load_reviews(write(tmp_path, "reviews: []\n"), KEY) == []


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("requirement_id: A.3", "requirement_id: Z.9"), "Z.9"),
        (("key_label: gap", "key_label: covered"), "stale"),
        (("reviewed_label: covered", "reviewed_label: maybe"), "reviewed_label"),
        (("reviewer: phuoctmse", "reviewer: ''"), "reviewer"),
    ],
)
def test_bad_reviews_are_rejected(
    tmp_path: Path, change: tuple[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        load_reviews(write(tmp_path, VALID.replace(*change)), KEY)


def test_reviewing_a_gap_as_covered_moves_it() -> None:
    review = Review(
        requirement_id="A.3",
        key_label="gap",
        reviewed_label="covered",
        covered_by=("T-3",),
        reviewer="r",
        date="2026-10-07",
    )
    reviewed = apply_reviews(KEY, [review])
    assert reviewed.covered["A.3"] == ("T-3",)
    assert "A.3" not in reviewed.true_gaps
    assert reviewed.decoys_claiming_gap_acs == ()  # T-9 no longer claims a gap


def test_reviewing_covered_as_gap_moves_it() -> None:
    review = Review(
        requirement_id="A.1",
        key_label="covered",
        reviewed_label="gap",
        reviewer="r",
        date="2026-10-07",
    )
    reviewed = apply_reviews(KEY, [review])
    assert "A.1" not in reviewed.covered
    assert reviewed.true_gaps == ("A.3", "A.1")


def test_confirming_a_label_changes_nothing() -> None:
    review = Review(
        requirement_id="A.3",
        key_label="gap",
        reviewed_label="gap",
        reviewer="r",
        date="2026-10-07",
    )
    assert apply_reviews(KEY, [review]) == KEY


# --- command line --------------------------------------------------------------


def test_disagreements_lists_each_with_its_evidence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--fake", "--disagreements"]) == 0
    out = capsys.readouterr().out
    assert "Disagreements with the answer key" in out
    assert "US-01.AC2" in out  # the fake judge calls it a gap; the key says covered
    assert "Invalid credentials show an error message" in out
    assert "[TC-003]" in out  # candidate case text is shown
    assert "reviewed_label:" in out  # a template to fill in


def test_reviewed_key_is_scored_next_to_the_raw_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reviews = write(
        tmp_path,
        """\
reviews:
  - requirement_id: US-10.AC4
    key_label: gap
    reviewed_label: covered
    covered_by: [TC-040]
    reviewer: tester
    date: 2026-10-07
""",
    )
    assert main(["--fake", "--reviews", str(reviews)]) == 0
    out = capsys.readouterr().out
    assert "Against the reviewed key (1 label changed)" in out


def test_without_reviews_there_is_no_reviewed_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--fake", "--reviews", str(tmp_path / "none.yaml")]) == 0
    assert "reviewed key" not in capsys.readouterr().out
