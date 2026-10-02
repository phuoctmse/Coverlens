from coverlens.core.models import Case, CoverageResult, Requirement, Status, Verdict
from coverlens.core.report import Report, StoryStatus, build_report


def req(req_id: str) -> Requirement:
    return Requirement(id=req_id, parent_id=req_id.split(".")[0], text=f"text {req_id}")


def case(case_id: str, *refs: str) -> Case:
    return Case(id=case_id, title=case_id, steps="", expected_result="", refs=refs)


def verdict(req_id: str, status: Status, *cited: str, tier: int = 3) -> Verdict:
    return Verdict(
        requirement_id=req_id,
        status=status,
        tier=tier,  # type: ignore[arg-type]
        cited_case_ids=cited,
        rationale=f"why {req_id}",
    )


REQS = [req("A.1"), req("A.2"), req("B.1"), req("B.2"), req("C.1"), req("C.2")]
CASES = [
    case("T-1", "A.1"),  # claim confirmed
    case("T-2", "B.2"),  # claims a gap -> mis-referenced
    case("T-3", "Z.9"),  # claims an unknown requirement -> mis-referenced
    case("T-4", "C.2"),  # claims an uncertain requirement -> not judged
    case("T-5"),
]
RESULT = CoverageResult(
    verdicts=(
        verdict("A.1", Status.COVERED, "T-1"),
        verdict("A.2", Status.COVERED, "T-1"),
        verdict("B.1", Status.COVERED, "T-5"),
        verdict("B.2", Status.GAP, tier=1),
        verdict("C.1", Status.GAP),
        verdict("C.2", Status.UNCERTAIN),
    ),
    orphan_case_ids=("T-5",),
    candidate_ids={"A.1": ("T-1", "T-2"), "B.2": ()},
)


def report() -> Report:
    return build_report(REQS, CASES, RESULT, pack_name="sample")


def test_rows_follow_spec_order_with_story_text_and_verdict() -> None:
    rows = report().requirements
    assert [r.requirement_id for r in rows] == [r.id for r in REQS]
    first = rows[0]
    assert (first.story_id, first.text) == ("A", "text A.1")
    assert (first.status, first.tier) == (Status.COVERED, 3)
    assert first.cited_case_ids == ("T-1",)
    assert first.candidate_ids == ("T-1", "T-2")
    assert first.rationale == "why A.1"
    assert rows[1].candidate_ids == ()  # no screening recorded


def test_story_rollup() -> None:
    stories = {s.story_id: s for s in report().stories}
    assert list(stories) == ["A", "B", "C"]
    assert stories["A"].status is StoryStatus.COVERED
    assert stories["B"].status is StoryStatus.PARTIAL
    assert stories["C"].status is StoryStatus.GAP
    assert (stories["C"].total, stories["C"].gap, stories["C"].uncertain) == (2, 1, 1)


def test_mis_referenced_cases() -> None:
    found = {(m.case_id, m.requirement_id) for m in report().mis_referenced}
    assert found == {("T-2", "B.2"), ("T-3", "Z.9")}
    reasons = {m.case_id: m.reason for m in report().mis_referenced}
    assert "gap" in reasons["T-2"].lower()
    assert "not in the spec" in reasons["T-3"]


def test_orphans_are_carried_over() -> None:
    assert report().orphan_case_ids == ("T-5",)


def test_summary_counts() -> None:
    summary = report().summary
    assert (summary.requirements, summary.cases) == (6, 5)
    assert (summary.covered, summary.gap, summary.uncertain) == (3, 2, 1)
    assert summary.coverage == 0.5
    assert report().pack_name == "sample"


def test_report_round_trips_through_json() -> None:
    original = report()
    assert Report.model_validate_json(original.model_dump_json()) == original
