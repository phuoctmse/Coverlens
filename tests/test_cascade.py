from collections.abc import Sequence
from pathlib import Path

import pytest

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter
from coverlens.adapters.xlsx_suite import XlsxSuiteAdapter
from coverlens.core.cascade import CoverageResult, run_cascade
from coverlens.core.models import Case, Requirement, Status, Verdict
from coverlens.core.pack import PackConfig, load_pack
from coverlens.verifiers.fake import FakeVerifier
from coverlens.verifiers.noop import NoopVerifier

ROOT = Path(__file__).resolve().parents[1]

PACK = PackConfig.model_validate(
    {
        "name": "sample",
        "suite": {
            "sheet": "Cases",
            "columns": {
                "id": "ID",
                "title": "Name",
                "steps": "Steps",
                "expected_result": "Expected",
            },
        },
        "tier1": {"top_k": 3, "gap_threshold": 0.1, "orphan_threshold": 0.1},
        "forbidden_core_terms": ["widget"],
    }
)

MATCHED = Requirement(id="R-1", parent_id="S-1", text="export invoices as pdf")
UNMATCHED = Requirement(id="R-2", parent_id="S-1", text="reset forgotten password")
CASES = [
    Case(id="C-1", title="export invoices as pdf", steps="", expected_result=""),
    Case(id="C-2", title="export invoices", steps="", expected_result=""),
]


class Scripted:
    """A verifier that returns a fixed answer and records what it was shown."""

    def __init__(self, answer: Verdict | None) -> None:
        self.answer = answer
        self.seen: list[tuple[str, tuple[str, ...]]] = []

    def judge(
        self, requirement: Requirement, candidates: Sequence[Case]
    ) -> Verdict | None:
        self.seen.append((requirement.id, tuple(c.id for c in candidates)))
        return self.answer


def covered(*case_ids: str, req_id: str = "R-1", tier: int = 3) -> Verdict:
    return Verdict(
        requirement_id=req_id,
        status=Status.COVERED,
        tier=tier,  # type: ignore[arg-type]
        cited_case_ids=case_ids,
    )


def only(result: CoverageResult, req_id: str = "R-1") -> Verdict:
    return next(v for v in result.verdicts if v.requirement_id == req_id)


def test_tier1_gaps_skip_the_verifiers() -> None:
    verifier = Scripted(covered("C-1", req_id="R-2"))
    result = run_cascade([UNMATCHED], CASES, PACK, [verifier])
    verdict = only(result, "R-2")
    assert (verdict.status, verdict.tier) == (Status.GAP, 1)
    assert verifier.seen == []


def test_verifiers_see_the_tier1_candidates_in_order() -> None:
    verifier = Scripted(covered("C-1"))
    run_cascade([MATCHED], CASES, PACK, [verifier])
    assert verifier.seen == [("R-1", ("C-1", "C-2"))]


def test_first_non_none_verdict_wins() -> None:
    later = Scripted(covered("C-2"))
    result = run_cascade(
        [MATCHED], CASES, PACK, [NoopVerifier(), Scripted(covered("C-1")), later]
    )
    assert only(result).cited_case_ids == ("C-1",)
    assert later.seen == []


def test_no_verdict_from_any_tier_is_uncertain() -> None:
    result = run_cascade([MATCHED], CASES, PACK, [NoopVerifier()])
    assert only(result).status is Status.UNCERTAIN
    assert "no tier" in only(result).rationale.lower()


def test_citing_a_case_outside_the_candidates_is_uncertain() -> None:
    result = run_cascade([MATCHED], CASES, PACK, [Scripted(covered("C-1", "C-9"))])
    verdict = only(result)
    assert verdict.status is Status.UNCERTAIN
    assert verdict.tier == 3
    assert verdict.cited_case_ids == ()
    assert "C-9" in verdict.rationale


def test_a_verdict_for_another_requirement_is_uncertain() -> None:
    result = run_cascade(
        [MATCHED], CASES, PACK, [Scripted(covered("C-1", req_id="R-other"))]
    )
    assert only(result).status is Status.UNCERTAIN
    assert "R-other" in only(result).rationale


def test_a_verifier_may_not_claim_tier_1() -> None:
    gap = Verdict(requirement_id="R-1", status=Status.GAP, tier=1)
    result = run_cascade([MATCHED], CASES, PACK, [Scripted(gap)])
    assert only(result).status is Status.UNCERTAIN


def test_gap_verdicts_from_a_verifier_are_kept() -> None:
    gap = Verdict(requirement_id="R-1", status=Status.GAP, tier=3, rationale="no")
    result = run_cascade([MATCHED], CASES, PACK, [Scripted(gap)])
    assert only(result) == gap


def test_result_keeps_requirement_order_and_candidates() -> None:
    result = run_cascade([UNMATCHED, MATCHED], CASES, PACK, [FakeVerifier()])
    assert [v.requirement_id for v in result.verdicts] == ["R-2", "R-1"]
    assert result.candidate_ids == {"R-2": (), "R-1": ("C-1", "C-2")}


# --- the ott_web data, offline -------------------------------------------------


@pytest.fixture(scope="module")
def ott_result() -> CoverageResult:
    pack = load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")
    data = ROOT / "data" / "ott_web"
    reqs = MarkdownSpecAdapter().read(data / "user_stories.md", pack)
    cases = XlsxSuiteAdapter().read(data / "test_cases.xlsx", pack)
    verifiers = [NoopVerifier(), FakeVerifier(glossary=pack.glossary)]
    return run_cascade(reqs, cases, pack, verifiers)


def test_ott_offline_run_gives_one_verdict_per_requirement(
    ott_result: CoverageResult,
) -> None:
    assert len(ott_result.verdicts) == 52
    assert len({v.requirement_id for v in ott_result.verdicts}) == 52


def test_ott_covered_verdicts_cite_only_candidates(ott_result: CoverageResult) -> None:
    for verdict in ott_result.verdicts:
        allowed = set(ott_result.candidate_ids[verdict.requirement_id])
        assert set(verdict.cited_case_ids) <= allowed


def test_ott_tier_1_gap_is_kept(ott_result: CoverageResult) -> None:
    tier1 = [v.requirement_id for v in ott_result.verdicts if v.tier == 1]
    assert tier1 == ["US-08.AC3"]
    assert ott_result.orphan_case_ids == ("TC-055", "TC-056", "TC-057")
