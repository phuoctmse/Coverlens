from pathlib import Path

import openpyxl
import pytest

from coverlens.adapters.xlsx_suite import SuiteError, XlsxSuiteAdapter, parse_rows
from coverlens.core.models import Case
from coverlens.core.pack import ColumnMap, PackConfig, SuiteConfig, load_pack
from coverlens.core.protocols import InputAdapter

ROOT = Path(__file__).resolve().parents[1]
OTT_SUITE = ROOT / "data" / "ott_web" / "test_cases.xlsx"

SUITE = SuiteConfig(
    sheet="Cases",
    columns=ColumnMap(
        id="ID",
        title="Name",
        steps="Steps",
        expected_result="Expected",
        refs="Refs",
        tags="Tags",
    ),
    dimensions=("Axis",),
)
HEADER = ["ID", "Name", "Steps", "Expected", "Refs", "Tags", "Axis"]


def row(case_id: object = "C-1", **cells: object) -> list[object]:
    values: dict[str, object] = {
        "ID": case_id,
        "Name": "Name",
        "Steps": "Do it",
        "Expected": "It works",
    }
    values.update(cells)
    return [values.get(column) for column in HEADER]


@pytest.fixture(scope="module")
def ott_pack() -> PackConfig:
    return load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")


# --- parse_rows ----------------------------------------------------------------


def test_row_becomes_a_case() -> None:
    [case] = parse_rows(HEADER, [row(Refs="R-1", Tags="smoke", Axis="a")], SUITE)
    assert case.id == "C-1"
    assert (case.title, case.steps, case.expected_result) == (
        "Name",
        "Do it",
        "It works",
    )
    assert case.preconditions == ""  # column not mapped
    assert (case.refs, case.tags) == (("R-1",), ("smoke",))
    assert case.dimensions == {"Axis": "a"}


def test_list_cells_are_split_and_stripped() -> None:
    [case] = parse_rows(HEADER, [row(Refs=" R-1 , R-2,,", Tags=None)], SUITE)
    assert case.refs == ("R-1", "R-2")
    assert case.tags == ()


def test_empty_dimension_cells_are_left_out() -> None:
    [case] = parse_rows(HEADER, [row(Axis=None)], SUITE)
    assert case.dimensions == {}


def test_the_text_none_is_a_real_value() -> None:
    [case] = parse_rows(HEADER, [row(Axis="None")], SUITE)
    assert case.dimensions == {"Axis": "None"}


def test_non_text_cells_are_converted_to_text() -> None:
    [case] = parse_rows(HEADER, [row(case_id=42, Name="  padded  ")], SUITE)
    assert (case.id, case.title) == ("42", "padded")


def test_blank_rows_are_skipped() -> None:
    blank = [None] * len(HEADER)
    cases = parse_rows(
        HEADER, [row("C-1"), blank, ["", " "] + blank[2:], row("C-2")], SUITE
    )
    assert [c.id for c in cases] == ["C-1", "C-2"]


def test_short_rows_are_padded() -> None:
    [case] = parse_rows(HEADER, [["C-1", "Name", "Do it", "It works"]], SUITE)
    assert case.refs == ()


def test_row_without_id_is_rejected_with_its_row_number() -> None:
    with pytest.raises(SuiteError, match=r"row 3: .*ID"):
        parse_rows(HEADER, [row("C-1"), row(None)], SUITE)


def test_duplicate_ids_are_rejected() -> None:
    with pytest.raises(SuiteError, match=r"row 3: duplicate .*C-1"):
        parse_rows(HEADER, [row("C-1"), row("C-1")], SUITE)


def test_missing_columns_are_named() -> None:
    header = ["ID", "Name", "Steps", "Refs", "Tags"]
    with pytest.raises(SuiteError, match=r"missing columns: \['Axis', 'Expected'\]"):
        parse_rows(header, [], SUITE)


def test_duplicate_header_names_are_rejected() -> None:
    with pytest.raises(SuiteError, match="duplicate column.*Name"):
        parse_rows([*HEADER, "Name"], [], SUITE)


def test_suite_without_cases_is_rejected() -> None:
    with pytest.raises(SuiteError, match="no cases"):
        parse_rows(HEADER, [[None] * len(HEADER)], SUITE)


# --- XlsxSuiteAdapter ----------------------------------------------------------


def test_adapter_is_an_input_adapter() -> None:
    assert isinstance(XlsxSuiteAdapter(), InputAdapter)


def write_workbook(path: Path, sheet: str, rows: list[list[object]]) -> Path:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = sheet
    for values in rows:
        worksheet.append(values)
    workbook.save(path)
    return path


def test_adapter_reads_the_mapped_sheet(tmp_path: Path, ott_pack: PackConfig) -> None:
    pack = ott_pack.model_copy(update={"suite": SUITE})
    path = write_workbook(tmp_path / "suite.xlsx", "Cases", [HEADER, row("C-9")])
    assert [c.id for c in XlsxSuiteAdapter().read(path, pack)] == ["C-9"]


def test_missing_sheet_lists_the_sheets_found(
    tmp_path: Path, ott_pack: PackConfig
) -> None:
    path = write_workbook(tmp_path / "suite.xlsx", "Other", [HEADER])
    with pytest.raises(SuiteError, match=r"no sheet 'Test cases'.*\['Other'\]"):
        XlsxSuiteAdapter().read(path, ott_pack)


def test_empty_sheet_is_rejected(tmp_path: Path, ott_pack: PackConfig) -> None:
    path = write_workbook(tmp_path / "suite.xlsx", "Test cases", [])
    with pytest.raises(SuiteError, match="empty"):
        XlsxSuiteAdapter().read(path, ott_pack)


@pytest.mark.parametrize("name", ["missing.xlsx", "not_excel.xlsx"])
def test_unreadable_file_raises_suite_error(
    tmp_path: Path, ott_pack: PackConfig, name: str
) -> None:
    (tmp_path / "not_excel.xlsx").write_text("plain text", encoding="utf-8")
    with pytest.raises(SuiteError, match=name):
        XlsxSuiteAdapter().read(tmp_path / name, ott_pack)


# --- the ott_web suite ---------------------------------------------------------


@pytest.fixture(scope="module")
def ott_cases(ott_pack: PackConfig) -> list[Case]:
    return XlsxSuiteAdapter().read(OTT_SUITE, ott_pack)


@pytest.fixture(scope="module")
def ott_by_id(ott_cases: list[Case]) -> dict[str, Case]:
    return {c.id: c for c in ott_cases}


def test_ott_suite_has_57_unique_cases(ott_cases: list[Case]) -> None:
    ids = [c.id for c in ott_cases]
    assert len(set(ids)) == 57
    assert (ids[0], ids[-1]) == ("TC-001", "TC-057")


def test_ott_suite_refs_tags_and_dimensions(
    ott_cases: list[Case], ott_pack: PackConfig
) -> None:
    assert sum(1 for c in ott_cases if c.refs) == 22
    assert sum(1 for c in ott_cases if c.tags) == 36
    dims = set(ott_pack.suite.dimensions)
    assert all(set(c.dimensions) == dims for c in ott_cases)


def test_ott_decoy_case_keeps_its_claimed_ref(ott_by_id: dict[str, Case]) -> None:
    decoy = ott_by_id["TC-017"]
    assert decoy.refs == ("US-04.AC3",)
    assert decoy.tags == ("live",)
    assert "US-04.AC3" not in decoy.judge_text()


def test_ott_no_drm_value_is_kept(ott_by_id: dict[str, Case]) -> None:
    assert ott_by_id["TC-051"].dimensions["Protocol / DRM"] == "None"
