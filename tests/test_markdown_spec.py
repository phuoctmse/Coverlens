from pathlib import Path

import pytest

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter, SpecError, parse_spec
from coverlens.core.pack import PackConfig, load_pack
from coverlens.core.protocols import InputAdapter

ROOT = Path(__file__).resolve().parents[1]
OTT_SPEC = ROOT / "data" / "ott_web" / "user_stories.md"

SAMPLE = """\
# Title

Intro text that is not a requirement.

## S-1 First story

As a user, I want things.

Acceptance criteria:

- **S-1.AC1** First criterion.
- **S-1.AC2** Second criterion with **bold** words.

## S-2 Second story

* **S-2.AC1** Star bullets work too.
"""


@pytest.fixture(scope="module")
def ott_pack() -> PackConfig:
    return load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")


def test_adapter_is_an_input_adapter() -> None:
    assert isinstance(MarkdownSpecAdapter(), InputAdapter)


def test_parse_reads_requirements_in_order_with_parents() -> None:
    reqs = parse_spec(SAMPLE)
    assert [(r.id, r.parent_id) for r in reqs] == [
        ("S-1.AC1", "S-1"),
        ("S-1.AC2", "S-1"),
        ("S-2.AC1", "S-2"),
    ]
    assert reqs[0].text == "First criterion."
    assert reqs[1].text == "Second criterion with **bold** words."


def test_parse_handles_crlf_line_endings() -> None:
    reqs = parse_spec(SAMPLE.replace("\n", "\r\n"))
    assert reqs[2].text == "Star bullets work too."


def test_requirement_before_any_story_is_rejected() -> None:
    with pytest.raises(SpecError, match=r"<spec>:1: .*X\.AC1.* not under a story"):
        parse_spec("- **X.AC1** Orphan line.\n")


def test_requirement_under_the_wrong_story_is_rejected() -> None:
    text = "## S-1 Story\n\n- **S-2.AC1** Misplaced.\n"
    with pytest.raises(SpecError, match=r":3: .*S-2\.AC1.*story S-1"):
        parse_spec(text)


def test_duplicate_requirement_ids_are_rejected() -> None:
    text = "## S-1 Story\n- **S-1.AC1** One.\n- **S-1.AC1** Again.\n"
    with pytest.raises(SpecError, match=r"duplicate.*S-1\.AC1"):
        parse_spec(text)


def test_spec_without_requirements_is_rejected() -> None:
    with pytest.raises(SpecError, match="no requirements"):
        parse_spec("# Just a title\n\nSome prose.\n")


def test_missing_spec_file_raises_spec_error(
    tmp_path: Path, ott_pack: PackConfig
) -> None:
    with pytest.raises(SpecError, match="missing.md"):
        MarkdownSpecAdapter().read(tmp_path / "missing.md", ott_pack)


def test_ott_spec_has_52_requirements_in_13_stories(ott_pack: PackConfig) -> None:
    reqs = MarkdownSpecAdapter().read(OTT_SPEC, ott_pack)
    assert len(reqs) == 52
    assert len({r.parent_id for r in reqs}) == 13
    assert reqs[0].id == "US-01.AC1"
    assert reqs[0].text.startswith("A user with valid credentials signs in")
    assert reqs[-1].id == "US-13.AC4"
    assert all(r.id.startswith(f"{r.parent_id}.") for r in reqs)
