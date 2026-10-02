import json
import subprocess
import sys
from pathlib import Path

import pytest

from coverlens.cli import main

ROOT = Path(__file__).resolve().parents[1]
PACK = str(ROOT / "domains" / "ott_web" / "pack.yaml")
SPEC = str(ROOT / "data" / "ott_web" / "user_stories.md")
SUITE = str(ROOT / "data" / "ott_web" / "test_cases.xlsx")


def run(*args: str) -> int:
    return main(["run", *args])


def test_fake_run_writes_both_files_and_a_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run(
        "--domain",
        PACK,
        "--spec",
        SPEC,
        "--suite",
        SUITE,
        "--out",
        str(tmp_path),
        "--fake",
    )
    assert code == 0
    assert (tmp_path / "coverage_report.xlsx").is_file()
    report = json.loads((tmp_path / "coverage_report.json").read_text("utf-8"))
    assert report["summary"]["requirements"] == 52
    assert report["summary"]["cases"] == 57
    out = capsys.readouterr().out
    assert "coverage_report.xlsx" in out
    assert "orphans 3" in out


def test_without_a_suite_every_requirement_is_a_gap(tmp_path: Path) -> None:
    assert run("--domain", PACK, "--spec", SPEC, "--out", str(tmp_path), "--fake") == 0
    summary = json.loads((tmp_path / "coverage_report.json").read_text("utf-8"))[
        "summary"
    ]
    assert (summary["cases"], summary["gap"], summary["covered"]) == (0, 52, 0)


def test_llm_run_is_not_available_yet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("--domain", PACK, "--spec", SPEC, "--out", str(tmp_path)) == 1
    assert "--fake" in capsys.readouterr().err
    assert not (tmp_path / "coverage_report.json").exists()


@pytest.mark.parametrize(
    ("flag", "bad"),
    [
        ("--domain", "missing_pack.yaml"),
        ("--spec", "missing_spec.md"),
        ("--suite", "missing.xlsx"),
    ],
)
def test_bad_inputs_exit_1_with_a_clear_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flag: str, bad: str
) -> None:
    paths = {"--domain": PACK, "--spec": SPEC, "--suite": SUITE}
    paths[flag] = str(tmp_path / bad)
    args = [arg for pair in paths.items() for arg in pair]
    assert run(*args, "--out", str(tmp_path / "out"), "--fake") == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert bad in err


def test_unwritable_output_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "file_not_dir"
    blocker.write_text("x", encoding="utf-8")
    assert run("--domain", PACK, "--spec", SPEC, "--out", str(blocker), "--fake") == 1
    assert "cannot write" in capsys.readouterr().err


def test_missing_command_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_module_entry_point_prints_help() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "coverlens", "run", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0
    assert "--fake" in done.stdout
