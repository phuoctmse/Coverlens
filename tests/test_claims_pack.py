"""The claims pack against its data, and an end-to-end offline run."""

import re
from pathlib import Path

import pytest

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter
from coverlens.adapters.xlsx_suite import XlsxSuiteAdapter
from coverlens.core.models import Case
from coverlens.core.pack import PackConfig, load_pack
from coverlens.core.pairwise import measure
from coverlens.pipeline import JudgeSettings, analyze

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "domains" / "claims" / "pack.yaml"
DATA = ROOT / "data" / "claims"


@pytest.fixture(scope="module")
def pack() -> PackConfig:
    return load_pack(PACK)


@pytest.fixture(scope="module")
def cases(pack: PackConfig) -> list[Case]:
    return XlsxSuiteAdapter().read(DATA / "test_cases.xlsx", pack)


def test_suite_reads_through_the_pack(cases: list[Case], pack: PackConfig) -> None:
    assert len(cases) == 120
    assert all(set(c.dimensions) == set(pack.suite.dimensions) for c in cases)


def test_every_suite_label_is_mapped(cases: list[Case], pack: PackConfig) -> None:
    tags = {t for c in cases for t in c.tags}
    assert tags <= set(pack.tag_map)


def test_tag_map_points_at_the_spec_stories(pack: PackConfig) -> None:
    spec = (DATA / "user_stories.md").read_text(encoding="utf-8")
    stories = set(re.findall(r"^## (CL-\d+)\b", spec, re.MULTILINE))
    assert set(pack.tag_map.values()) == stories


def test_pairwise_declares_every_value_used(
    cases: list[Case], pack: PackConfig
) -> None:
    assert pack.pairwise is not None
    assert measure(pack.pairwise, cases).unknown_values == ()


def test_tier1_never_concludes_a_gap_on_the_held_out_domain(pack: PackConfig) -> None:
    assert pack.tier1.gap_threshold == 0


def test_offline_end_to_end_run() -> None:
    reqs = MarkdownSpecAdapter().read(DATA / "user_stories.md", load_pack(PACK))
    analysis = analyze(
        PACK,
        DATA / "user_stories.md",
        DATA / "test_cases.xlsx",
        JudgeSettings(fake=True),
    )
    rows = analysis.report.requirements
    assert len(rows) == len(reqs) == 100
    assert not any(r.tier == 1 for r in rows)  # gap_threshold 0
    assert analysis.report.pairwise is not None
