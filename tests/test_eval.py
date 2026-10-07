from pathlib import Path

import pytest

from coverlens.core.models import Case, CoverageResult, Requirement, Status, Verdict
from coverlens.core.report import Report, build_report
from eval.__main__ import main
from eval.answer_key import AnswerKey, Decoy, load_key
from eval.metrics import EvalResult, Rate, evaluate, format_result

REQS = [Requirement(id=f"A.{n}", parent_id="A", text=f"r{n}") for n in range(1, 6)]
CASES = [
    Case(id="T-1", title="t", steps="", expected_result=""),
    Case(id="T-2", title="t", steps="", expected_result=""),
    Case(id="T-3", title="t", steps="", expected_result="", refs=("A.4",)),  # decoy
    Case(id="T-4", title="t", steps="", expected_result=""),
]
KEY = AnswerKey(
    covered={"A.1": ("T-1",), "A.2": ("T-2",), "A.3": ("T-1",)},
    true_gaps=("A.4", "A.5"),
    decoys_claiming_gap_acs=(Decoy(id="T-3", claims="A.4"),),
    orphan_cases=("T-4",),
)


def verdict(req_id: str, status: Status, *cited: str, tier: int = 3) -> Verdict:
    return Verdict(
        requirement_id=req_id,
        status=status,
        tier=tier,  # type: ignore[arg-type]
        cited_case_ids=cited,
    )


def make_report(*verdicts: Verdict, orphans: tuple[str, ...] = ("T-4",)) -> Report:
    result = CoverageResult(
        verdicts=verdicts,
        orphan_case_ids=orphans,
        candidate_ids={
            "A.1": ("T-1", "T-2"),
            "A.2": ("T-1",),  # gold T-2 missing from candidates
            "A.3": ("T-1",),
            "A.4": ("T-3",),
        },
    )
    return build_report(REQS, CASES, result, pack_name="sample")


GOOD = make_report(
    verdict("A.1", Status.COVERED, "T-1"),  # right, right citation
    verdict("A.2", Status.COVERED, "T-1"),  # right status, wrong citation
    verdict("A.3", Status.GAP),  # missed coverage
    verdict("A.4", Status.GAP),  # right gap
    verdict("A.5", Status.UNCERTAIN),
)


def test_rate_value_and_empty_rate() -> None:
    assert Rate(hit=1, total=4).value == 0.25
    assert Rate(hit=0, total=0).value is None


def test_gap_and_covered_rates() -> None:
    result = evaluate(GOOD, KEY)
    assert result.gap_precision == Rate(hit=1, total=2)  # A.3 is a false gap
    assert result.gap_recall == Rate(hit=1, total=2)  # A.5 uncertain, not a gap
    assert result.covered_precision == Rate(hit=2, total=2)
    assert result.covered_recall == Rate(hit=2, total=3)
    assert result.uncertain == 1


def test_citations_and_candidate_recall() -> None:
    result = evaluate(GOOD, KEY)
    assert result.citation_accuracy == Rate(hit=1, total=2)
    assert result.candidate_recall == Rate(hit=2, total=3)


def test_orphans_and_decoys() -> None:
    result = evaluate(GOOD, KEY)
    assert result.orphan_precision == Rate(hit=1, total=1)
    assert result.orphan_recall == Rate(hit=1, total=1)
    assert result.decoys_flagged == Rate(hit=1, total=1)  # A.4 judged a gap


def test_canary_passes_without_tier1_false_gaps() -> None:
    result = evaluate(GOOD, KEY)
    assert result.tier1_false_gaps == ()
    assert result.canary_ok
    assert "Canary" in format_result(result)
    assert "PASS" in format_result(result)


def test_canary_fails_on_a_tier1_gap_for_a_covered_requirement() -> None:
    report = make_report(
        verdict("A.1", Status.GAP, tier=1),
        verdict("A.2", Status.COVERED, "T-2"),
        verdict("A.3", Status.COVERED, "T-1"),
        verdict("A.4", Status.GAP, tier=1),
        verdict("A.5", Status.GAP),
    )
    result = evaluate(report, KEY)
    assert result.tier1_false_gaps == ("A.1",)
    assert not result.canary_ok
    assert "FAIL" in format_result(result)


def test_key_and_report_must_describe_the_same_requirements() -> None:
    key = KEY.model_copy(update={"true_gaps": ("A.4", "A.5", "Z.9")})
    with pytest.raises(ValueError, match="Z.9"):
        evaluate(GOOD, key)


def test_result_round_trips_through_json() -> None:
    result = evaluate(GOOD, KEY)
    assert EvalResult.model_validate_json(result.model_dump_json()) == result


# --- the ott_web answer key ----------------------------------------------------


def test_ott_key_loads() -> None:
    key = load_key()
    assert len(key.covered) == 43
    assert len(key.true_gaps) == 9
    assert len(key.orphan_cases) == 3
    assert {d.id for d in key.decoys_claiming_gap_acs} == {"TC-017", "TC-039", "TC-047"}


def test_ott_fake_eval_passes_the_canary(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--fake"]) == 0
    out = capsys.readouterr().out
    assert "Canary" in out
    assert "PASS" in out
    assert "43/43" in out  # candidate recall


def test_eval_without_a_reachable_ollama_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--ollama-url", "http://127.0.0.1:9"]) == 1
    assert "--fake" in capsys.readouterr().err


def test_missing_key_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--fake", "--key", str(tmp_path / "nope.json")]) == 1
    assert "nope.json" in capsys.readouterr().err


# --- datasets ------------------------------------------------------------------


def test_dataset_paths_follow_the_layout() -> None:
    from eval.answer_key import dataset_paths

    paths = dataset_paths("claims")
    assert paths.pack.as_posix().endswith("domains/claims/pack.yaml")
    assert paths.spec.as_posix().endswith("data/claims/user_stories.md")
    assert paths.key.as_posix().endswith("data/claims/answer_key.json")
    assert paths.reviews.as_posix().endswith("eval/reviews/claims.yaml")


def test_eval_runs_on_the_claims_dataset(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--fake", "--dataset", "claims"]) == 0
    out = capsys.readouterr().out
    assert "/100 (" in out  # accuracy over the 100 claims criteria
    assert "Canary" in out


def test_unknown_dataset_is_a_usage_error() -> None:
    with pytest.raises(SystemExit):
        main(["--fake", "--dataset", "nope"])
