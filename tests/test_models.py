import pytest
from pydantic import ValidationError

from coverlens.core.models import Case, Requirement, Status, Verdict


def make_case(**overrides: object) -> Case:
    fields: dict[str, object] = {
        "id": "TC-001",
        "title": "Sign in",
        "steps": "Enter valid credentials",
        "expected_result": "User is signed in",
    }
    return Case.model_validate(fields | overrides)


# --- Requirement -------------------------------------------------------------


def test_requirement_holds_id_parent_and_text() -> None:
    req = Requirement(id="US-01.AC1", parent_id="US-01", text="Valid sign-in works.")
    assert (req.id, req.parent_id) == ("US-01.AC1", "US-01")


def test_requirement_is_immutable() -> None:
    req = Requirement(id="US-01.AC1", parent_id="US-01", text="x")
    with pytest.raises(ValidationError):
        req.text = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("bad_id", ["", "   "])
def test_requirement_rejects_blank_id(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        Requirement(id=bad_id, parent_id="US-01", text="x")


def test_requirement_strips_whitespace_from_ids() -> None:
    req = Requirement(id=" US-01.AC1 ", parent_id=" US-01", text="x")
    assert (req.id, req.parent_id) == ("US-01.AC1", "US-01")


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Requirement.model_validate(
            {"id": "US-01.AC1", "parent_id": "US-01", "text": "x", "extra": 1}
        )


# --- Case --------------------------------------------------------------------


def test_case_optional_fields_default_to_empty() -> None:
    case = make_case()
    assert case.preconditions == ""
    assert case.refs == ()
    assert case.tags == ()
    assert case.dimensions == {}


def test_case_keeps_refs_tags_and_dimensions() -> None:
    case = make_case(refs=["US-01.AC1"], tags=["smoke"], dimensions={"Axis": "value"})
    assert case.refs == ("US-01.AC1",)
    assert case.tags == ("smoke",)
    assert case.dimensions == {"Axis": "value"}


def test_case_judge_text_excludes_refs() -> None:
    case = make_case(preconditions="Has an account", refs=["US-09.AC4"])
    text = case.judge_text()
    for part in ("Sign in", "Has an account", "Enter valid credentials", "signed in"):
        assert part in text
    assert "US-09.AC4" not in text


# --- Verdict -----------------------------------------------------------------


def test_status_values_are_lowercase_strings() -> None:
    assert [s.value for s in Status] == ["covered", "gap", "uncertain"]


def test_covered_verdict_with_citation_is_valid() -> None:
    verdict = Verdict(
        requirement_id="US-01.AC1",
        status=Status.COVERED,
        tier=3,
        cited_case_ids=["TC-001"],
    )
    assert verdict.cited_case_ids == ("TC-001",)
    assert verdict.rationale == ""


def test_covered_verdict_must_cite_a_case() -> None:
    with pytest.raises(ValidationError, match="at least one case"):
        Verdict(requirement_id="US-01.AC1", status=Status.COVERED, tier=3)


def test_tier_1_can_never_conclude_covered() -> None:
    with pytest.raises(ValidationError, match="Tier 1"):
        Verdict(
            requirement_id="US-01.AC1",
            status=Status.COVERED,
            tier=1,
            cited_case_ids=["TC-001"],
        )


@pytest.mark.parametrize("status", [Status.GAP, Status.UNCERTAIN])
def test_only_covered_verdicts_cite_cases(status: Status) -> None:
    with pytest.raises(ValidationError, match="only COVERED"):
        Verdict(
            requirement_id="US-01.AC1",
            status=status,
            tier=3,
            cited_case_ids=["TC-001"],
        )


def test_citations_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        Verdict(
            requirement_id="US-01.AC1",
            status=Status.COVERED,
            tier=3,
            cited_case_ids=["TC-001", "TC-001"],
        )


@pytest.mark.parametrize("tier", [0, 4])
def test_tier_must_be_1_2_or_3(tier: int) -> None:
    with pytest.raises(ValidationError):
        Verdict(requirement_id="US-01.AC1", status=Status.GAP, tier=tier)


def test_verdict_round_trips_through_json() -> None:
    verdict = Verdict(
        requirement_id="US-01.AC1",
        status=Status.COVERED,
        tier=3,
        cited_case_ids=["TC-001", "TC-002"],
        rationale="Both cases sign in with valid credentials.",
    )
    assert Verdict.model_validate_json(verdict.model_dump_json()) == verdict
