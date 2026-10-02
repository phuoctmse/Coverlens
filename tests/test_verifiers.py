from coverlens.core.models import Case, Requirement, Status
from coverlens.core.protocols import Verifier
from coverlens.verifiers.fake import FakeVerifier
from coverlens.verifiers.noop import NoopVerifier

REQ = Requirement(id="R-1", parent_id="S-1", text="Export invoices as a PDF file.")


def case(case_id: str, title: str, expected: str = "") -> Case:
    return Case(id=case_id, title=title, steps="", expected_result=expected)


def test_both_verifiers_satisfy_the_protocol() -> None:
    assert isinstance(NoopVerifier(), Verifier)
    assert isinstance(FakeVerifier(), Verifier)


def test_noop_always_passes_on() -> None:
    assert NoopVerifier().judge(REQ, [case("C-1", "Export invoices as PDF")]) is None


def test_fake_covers_with_the_best_overlapping_case() -> None:
    cases = [
        case("C-1", "Export invoices"),
        case("C-2", "Export invoices", expected="A PDF file is saved"),
    ]
    verdict = FakeVerifier().judge(REQ, cases)
    assert verdict is not None
    assert verdict.status is Status.COVERED
    assert verdict.tier == 3
    assert verdict.cited_case_ids == ("C-2",)
    assert "C-2" in verdict.rationale


def test_fake_reports_a_gap_when_overlap_is_low() -> None:
    verdict = FakeVerifier().judge(REQ, [case("C-1", "Change the password")])
    assert verdict is not None
    assert verdict.status is Status.GAP
    assert verdict.cited_case_ids == ()


def test_fake_reports_a_gap_without_candidates() -> None:
    verdict = FakeVerifier().judge(REQ, [])
    assert verdict is not None
    assert verdict.status is Status.GAP


def test_fake_threshold_is_configurable() -> None:
    cases = [case("C-1", "Export invoices")]  # 2 of 4 terms: export, invoic, pdf, fil
    assert FakeVerifier(min_overlap=0.5).judge(REQ, cases).status is Status.COVERED  # type: ignore[union-attr]
    assert FakeVerifier(min_overlap=0.75).judge(REQ, cases).status is Status.GAP  # type: ignore[union-attr]


def test_fake_breaks_ties_by_candidate_order() -> None:
    cases = [
        case("C-1", "Export invoices PDF file"),
        case("C-2", "Export invoices PDF file"),
    ]
    verdict = FakeVerifier().judge(REQ, cases)
    assert verdict is not None
    assert verdict.cited_case_ids == ("C-1",)


def test_fake_uses_the_glossary() -> None:
    req = Requirement(id="R-1", parent_id="S-1", text="On demand titles play")
    cases = [case("C-1", "VOD titles play")]
    assert FakeVerifier().judge(req, cases).status is Status.GAP  # type: ignore[union-attr]
    verdict = FakeVerifier(glossary={"on demand": "vod"}).judge(req, cases)
    assert verdict is not None
    assert verdict.status is Status.COVERED
