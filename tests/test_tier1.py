from pathlib import Path

import pytest
from pydantic import ValidationError

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter
from coverlens.adapters.xlsx_suite import XlsxSuiteAdapter
from coverlens.core.bm25 import Tokenizer
from coverlens.core.models import Case, Requirement, Status
from coverlens.core.pack import Tier1Config, load_pack
from coverlens.core.tier1 import Tier1Result, screen

ROOT = Path(__file__).resolve().parents[1]

CONFIG = Tier1Config(top_k=2, gap_threshold=1.0, orphan_threshold=0.5)


def req(req_id: str, text: str, parent: str = "S-1") -> Requirement:
    return Requirement(id=req_id, parent_id=parent, text=text)


def case(
    case_id: str,
    text: str,
    refs: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
) -> Case:
    return Case(
        id=case_id, title=text, steps="", expected_result="", refs=refs, tags=tags
    )


def run(
    reqs: list[Requirement],
    cases: list[Case],
    tag_map: dict[str, str] | None = None,
    config: Tier1Config = CONFIG,
) -> Tier1Result:
    return screen(reqs, cases, config, Tokenizer(), tag_map or {})


# --- certain gaps --------------------------------------------------------------


def test_unmatched_unreferenced_requirement_is_a_certain_gap() -> None:
    result = run([req("R-1", "export invoices as pdf")], [case("C-1", "login works")])
    [screening] = result.screenings
    assert screening.verdict is not None
    assert screening.verdict.status is Status.GAP
    assert screening.verdict.tier == 1
    assert screening.candidate_ids == ()


def test_a_ref_prevents_a_certain_gap_and_makes_the_case_a_candidate() -> None:
    result = run(
        [req("R-1", "export invoices as pdf")],
        [case("C-1", "login works", refs=("R-1",))],
    )
    [screening] = result.screenings
    assert screening.verdict is None
    assert screening.candidate_ids == ("C-1",)


def test_a_strong_text_match_is_a_candidate_not_a_gap() -> None:
    result = run(
        [req("R-1", "export invoices as pdf")],
        [case("C-1", "export invoices as pdf"), case("C-2", "login works")],
    )
    [screening] = result.screenings
    assert screening.verdict is None
    assert screening.candidate_ids == ("C-1",)
    assert screening.top_score >= CONFIG.gap_threshold


def test_tier1_never_concludes_covered() -> None:
    result = run(
        [req("R-1", "export invoices"), req("R-2", "unrelated words")],
        [case("C-1", "export invoices", refs=("R-1",))],
    )
    statuses = {s.verdict.status for s in result.screenings if s.verdict}
    assert statuses <= {Status.GAP}


# --- candidates ----------------------------------------------------------------


def test_text_candidates_are_limited_to_top_k_best_first() -> None:
    cases = [
        case("C-1", "export"),
        case("C-2", "export invoices"),
        case("C-3", "export invoices pdf"),
    ]
    result = run([req("R-1", "export invoices pdf")], cases)
    assert result.screenings[0].candidate_ids == ("C-3", "C-2")


def test_refs_and_tags_add_candidates_after_text_matches() -> None:
    cases = [
        case("C-1", "export invoices pdf"),
        case("C-2", "unrelated", refs=("R-1",)),
        case("C-3", "also unrelated", tags=("billing",)),
        case("C-4", "other story", tags=("auth",)),
    ]
    result = run(
        [req("R-1", "export invoices pdf", parent="S-1")],
        cases,
        tag_map={"billing": "S-1", "auth": "S-2"},
    )
    assert result.screenings[0].candidate_ids == ("C-1", "C-2", "C-3")


def test_candidates_are_not_duplicated() -> None:
    cases = [case("C-1", "export invoices", refs=("R-1",), tags=("billing",))]
    result = run([req("R-1", "export invoices")], cases, tag_map={"billing": "S-1"})
    assert result.screenings[0].candidate_ids == ("C-1",)


def test_screenings_keep_requirement_order() -> None:
    reqs = [req("R-2", "b words"), req("R-1", "a words")]
    result = run(reqs, [case("C-1", "x")])
    assert [s.requirement_id for s in result.screenings] == ["R-2", "R-1"]


# --- orphans -------------------------------------------------------------------


def test_case_without_ref_tag_or_matching_text_is_an_orphan() -> None:
    result = run(
        [req("R-1", "export invoices pdf")],
        [case("C-1", "export invoices pdf"), case("C-2", "toggle dark theme")],
    )
    assert result.orphan_case_ids == ("C-2",)


@pytest.mark.parametrize(
    "unrelated",
    [
        case("C-2", "toggle dark theme", refs=("R-1",)),
        case("C-2", "toggle dark theme", tags=("billing",)),
    ],
)
def test_a_ref_or_tag_means_not_an_orphan(unrelated: Case) -> None:
    result = run([req("R-1", "export invoices pdf")], [unrelated])
    assert result.orphan_case_ids == ()


# --- config --------------------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"top_k": 0, "gap_threshold": 1, "orphan_threshold": 1},
        {"top_k": 5, "gap_threshold": -1, "orphan_threshold": 1},
        {"top_k": 5, "gap_threshold": 1, "orphan_threshold": -1},
    ],
)
def test_tier1_config_rejects_bad_values(fields: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        Tier1Config.model_validate(fields)


# --- the ott_web data ----------------------------------------------------------


@pytest.fixture(scope="module")
def ott_result() -> Tier1Result:
    pack = load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")
    data = ROOT / "data" / "ott_web"
    reqs = MarkdownSpecAdapter().read(data / "user_stories.md", pack)
    cases = XlsxSuiteAdapter().read(data / "test_cases.xlsx", pack)
    return screen(reqs, cases, pack.tier1, Tokenizer(pack.glossary), pack.tag_map)


def test_ott_every_requirement_is_screened(ott_result: Tier1Result) -> None:
    assert len(ott_result.screenings) == 52


def test_ott_every_open_requirement_has_candidates(ott_result: Tier1Result) -> None:
    open_ = [s for s in ott_result.screenings if s.verdict is None]
    assert open_
    assert all(s.candidate_ids for s in open_)


def test_ott_referenced_requirements_are_never_certain_gaps(
    ott_result: Tier1Result,
) -> None:
    pack = load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")
    cases = XlsxSuiteAdapter().read(ROOT / "data" / "ott_web" / "test_cases.xlsx", pack)
    referenced = {ref for c in cases for ref in c.refs}
    gaps = {s.requirement_id for s in ott_result.screenings if s.verdict}
    assert gaps.isdisjoint(referenced)
