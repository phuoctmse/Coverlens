import re
from pathlib import Path
from typing import Any

import openpyxl
import pytest
import yaml

from coverlens.core.pack import PackConfig, PackError, load_pack

ROOT = Path(__file__).resolve().parents[1]
OTT_PACK = ROOT / "domains" / "ott_web" / "pack.yaml"
OTT_DATA = ROOT / "data" / "ott_web"


def minimal_pack() -> dict[str, Any]:
    return {
        "name": "sample",
        "suite": {
            "sheet": "Cases",
            "columns": {
                "id": "ID",
                "title": "Name",
                "steps": "Steps",
                "expected_result": "Expected",
            },
            "dimensions": ["Axis A", "Axis B"],
        },
        "tag_map": {"login": "S-01"},
        "forbidden_core_terms": ["Widget"],
    }


def write_pack(tmp_path: Path, content: dict[str, Any] | str) -> Path:
    path = tmp_path / "pack.yaml"
    text = content if isinstance(content, str) else yaml.safe_dump(content)
    path.write_text(text, encoding="utf-8")
    return path


# --- loading a pack ------------------------------------------------------------


def test_minimal_pack_loads_with_defaults(tmp_path: Path) -> None:
    pack = load_pack(write_pack(tmp_path, minimal_pack()))
    assert isinstance(pack, PackConfig)
    assert pack.suite.columns.id == "ID"
    assert pack.suite.columns.refs is None
    assert pack.suite.list_separator == ","
    assert pack.suite.dimensions == ("Axis A", "Axis B")


def test_forbidden_terms_are_lowercased(tmp_path: Path) -> None:
    pack = load_pack(write_pack(tmp_path, minimal_pack()))
    assert pack.forbidden_core_terms == ("widget",)


def test_missing_file_raises_pack_error(tmp_path: Path) -> None:
    with pytest.raises(PackError, match="missing.yaml"):
        load_pack(tmp_path / "missing.yaml")


def test_invalid_yaml_raises_pack_error(tmp_path: Path) -> None:
    path = write_pack(tmp_path, "name: [unclosed")
    with pytest.raises(PackError, match="pack.yaml"):
        load_pack(path)


def test_non_mapping_yaml_raises_pack_error(tmp_path: Path) -> None:
    with pytest.raises(PackError, match="mapping"):
        load_pack(write_pack(tmp_path, "- just\n- a list\n"))


def test_missing_required_key_raises_pack_error(tmp_path: Path) -> None:
    content = minimal_pack()
    del content["suite"]["columns"]["steps"]
    with pytest.raises(PackError, match="steps"):
        load_pack(write_pack(tmp_path, content))


def test_unknown_key_raises_pack_error(tmp_path: Path) -> None:
    content = minimal_pack() | {"surprise": 1}
    with pytest.raises(PackError, match="surprise"):
        load_pack(write_pack(tmp_path, content))


def test_dimension_cannot_reuse_a_mapped_column(tmp_path: Path) -> None:
    content = minimal_pack()
    content["suite"]["dimensions"] = ["Axis A", "Steps"]
    with pytest.raises(PackError, match="Steps"):
        load_pack(write_pack(tmp_path, content))


def test_forbidden_terms_must_not_be_empty(tmp_path: Path) -> None:
    content = minimal_pack() | {"forbidden_core_terms": []}
    with pytest.raises(PackError, match="forbidden_core_terms"):
        load_pack(write_pack(tmp_path, content))


# --- the ott_web pack against its data -----------------------------------------


@pytest.fixture(scope="module")
def ott_pack() -> PackConfig:
    return load_pack(OTT_PACK)


@pytest.fixture(scope="module")
def suite_rows(ott_pack: PackConfig) -> list[dict[str, Any]]:
    workbook = openpyxl.load_workbook(OTT_DATA / "test_cases.xlsx", read_only=True)
    rows = workbook[ott_pack.suite.sheet].iter_rows(values_only=True)
    header = [str(cell) for cell in next(rows)]
    records = [dict(zip(header, row, strict=True)) for row in rows]
    workbook.close()
    return records


def test_ott_pack_columns_exist_in_suite(
    ott_pack: PackConfig, suite_rows: list[dict[str, Any]]
) -> None:
    header = set(suite_rows[0])
    mapped = {c for c in ott_pack.suite.columns.model_dump().values() if c}
    missing = (mapped | set(ott_pack.suite.dimensions)) - header
    assert missing == set()


def test_every_suite_tag_is_mapped(
    ott_pack: PackConfig, suite_rows: list[dict[str, Any]]
) -> None:
    tag_column = ott_pack.suite.columns.tags
    assert tag_column is not None
    tags = {row[tag_column] for row in suite_rows if row[tag_column]}
    assert tags - set(ott_pack.tag_map) == set()


def test_tag_map_points_at_stories_in_spec(ott_pack: PackConfig) -> None:
    spec = (OTT_DATA / "user_stories.md").read_text(encoding="utf-8")
    stories = set(re.findall(r"^## (US-\d+)\b", spec, re.MULTILINE))
    assert set(ott_pack.tag_map.values()) <= stories
    assert len(ott_pack.tag_map) == len(stories)
