from pathlib import Path
from typing import Any

import pytest
import yaml

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter
from coverlens.adapters.xlsx_suite import XlsxSuiteAdapter
from coverlens.core.cascade import run_cascade
from coverlens.core.models import Case, Requirement, Status
from coverlens.core.pack import PackError, load_pack
from coverlens.core.protocols import Verifier
from coverlens.pipeline import JudgeSettings, analyze
from coverlens.verifiers.fake import FakeVerifier
from coverlens.verifiers.overlap import OverlapVerifier, best_overlap

ROOT = Path(__file__).resolve().parents[1]
REQ = Requirement(id="R-1", parent_id="S-1", text="Export invoices as a PDF file.")


def case(case_id: str, title: str, expected: str = "") -> Case:
    return Case(id=case_id, title=title, steps="", expected_result=expected)


# --- scoring -------------------------------------------------------------------


def test_best_overlap_picks_the_case_sharing_most_terms() -> None:
    cases = [case("C-1", "Export invoices"), case("C-2", "Export invoices PDF file")]
    best, share = best_overlap(REQ, cases)
    assert best is not None
    assert (best.id, share) == ("C-2", 1.0)


def test_best_overlap_breaks_ties_by_candidate_order() -> None:
    cases = [
        case("C-1", "Export invoices PDF file"),
        case("C-2", "Export PDF file invoices"),
    ]
    best, _ = best_overlap(REQ, cases)
    assert best is not None
    assert best.id == "C-1"


def test_best_overlap_of_nothing_is_none() -> None:
    assert best_overlap(REQ, []) == (None, 0.0)
    assert best_overlap(REQ, [case("C-1", "Change the password")]) == (None, 0.0)


# --- OverlapVerifier (Tier 2) ----------------------------------------------------


def test_is_a_verifier() -> None:
    assert isinstance(OverlapVerifier(), Verifier)


def test_high_overlap_is_covered_at_tier_2() -> None:
    verdict = OverlapVerifier().judge(REQ, [case("C-1", "Export invoices", "PDF file")])
    assert verdict is not None
    assert (verdict.status, verdict.tier) == (Status.COVERED, 2)
    assert verdict.cited_case_ids == ("C-1",)
    assert "100%" in verdict.rationale


@pytest.mark.parametrize(
    "cases",
    [
        [],
        [case("C-1", "Change the password")],
        [case("C-1", "Export invoices")],  # 2 of 4 terms, below 0.75
    ],
)
def test_otherwise_it_passes_on_and_never_says_gap(cases: list[Case]) -> None:
    assert OverlapVerifier().judge(REQ, cases) is None


def test_threshold_and_glossary_are_used() -> None:
    req = Requirement(id="R-1", parent_id="S-1", text="On demand titles play")
    cases = [case("C-1", "VOD titles play")]
    assert OverlapVerifier(min_overlap=0.75).judge(req, cases) is None
    assert OverlapVerifier(min_overlap=0.6).judge(req, cases) is not None
    assert OverlapVerifier(glossary={"on demand": "vod"}).judge(req, cases) is not None


def test_fake_judge_agrees_with_tier_2_on_covered() -> None:
    cases = [case("C-1", "Export invoices", "PDF file")]
    tier2, fake = OverlapVerifier().judge(REQ, cases), FakeVerifier().judge(REQ, cases)
    assert tier2 is not None and fake is not None
    assert (fake.status, fake.cited_case_ids) == (tier2.status, tier2.cited_case_ids)


# --- pack ----------------------------------------------------------------------


def write_pack(tmp_path: Path, tier2: Any) -> Path:
    text = (ROOT / "domains" / "ott_web" / "pack.yaml").read_text("utf-8")
    data = yaml.safe_load(text)
    data["tier2"] = tier2
    path = tmp_path / "pack.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_ott_pack_sets_the_tier_2_threshold() -> None:
    pack = load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")
    assert pack.tier2 is not None
    assert pack.tier2.min_overlap == 0.75


@pytest.mark.parametrize("bad", [0, -0.1, 1.5])
def test_tier_2_threshold_must_be_in_0_1(tmp_path: Path, bad: float) -> None:
    with pytest.raises(PackError, match="min_overlap"):
        load_pack(write_pack(tmp_path, {"min_overlap": bad}))


# --- the ott_web data ----------------------------------------------------------


def test_ott_tier_2_settles_part_of_the_suite_and_only_as_covered() -> None:
    pack = load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")
    assert pack.tier2 is not None
    data = ROOT / "data" / "ott_web"
    reqs = MarkdownSpecAdapter().read(data / "user_stories.md", pack)
    cases = XlsxSuiteAdapter().read(data / "test_cases.xlsx", pack)
    tier2 = OverlapVerifier(pack.tier2.min_overlap, pack.glossary)
    result = run_cascade(
        reqs, cases, pack, [tier2, FakeVerifier(glossary=pack.glossary)]
    )
    settled = [v for v in result.verdicts if v.tier == 2]
    assert len(settled) >= 20
    assert {v.status for v in settled} == {Status.COVERED}


def test_pipeline_puts_overlap_in_the_tier_2_slot() -> None:
    data = ROOT / "data" / "ott_web"
    analysis = analyze(
        ROOT / "domains" / "ott_web" / "pack.yaml",
        data / "user_stories.md",
        data / "test_cases.xlsx",
        JudgeSettings(fake=True),
    )
    tiers = {row.tier for row in analysis.report.requirements}
    assert tiers == {1, 2, 3}


def test_tier_2_can_be_switched_off() -> None:
    data = ROOT / "data" / "ott_web"
    analysis = analyze(
        ROOT / "domains" / "ott_web" / "pack.yaml",
        data / "user_stories.md",
        data / "test_cases.xlsx",
        JudgeSettings(fake=True, tier2=False),
    )
    assert {row.tier for row in analysis.report.requirements} == {1, 3}
