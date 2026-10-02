"""Repo-wide rules from CLAUDE.md, enforced as tests."""

import hashlib
import re
from pathlib import Path

from coverlens.core.pack import load_pack

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "src" / "coverlens"
CORE_DIR = PACKAGE_DIR / "core"
DATA_DIR = ROOT / "data" / "ott_web"

# data/ is read-only input; re-pin only if the dataset is deliberately replaced.
EXPECTED_SHA256: dict[str, str] = {
    "answer_key.json": "d45aa4a7d79b152a98b1cfd8a818f5f99886e879ff51587d275e96ab4d8210e5",
    "test_cases.xlsx": "386c3039e8ec28ec6d17eca21ea0ab946498bb690245d573b8dc9d06714adb16",
    "user_stories.md": "c7df8e4ce13b0565ccea220d27679fcf6a9256965771e06f14b367c9289bba3f",
}

PACK_FILES = sorted((ROOT / "domains").glob("*/pack.yaml"))

# The examples named in CLAUDE.md, plus every pack's own list.
FORBIDDEN_CORE_TERMS = sorted(
    {"region", "drm", "browser", "entitlement"}.union(
        *(load_pack(path).forbidden_core_terms for path in PACK_FILES)
    )
)


def python_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def test_data_files_unchanged() -> None:
    changed = [
        name
        for name, expected in EXPECTED_SHA256.items()
        if hashlib.sha256((DATA_DIR / name).read_bytes()).hexdigest() != expected
    ]
    assert changed == [], f"data/ is read-only, but these files changed: {changed}"


def test_data_dir_has_only_pinned_files() -> None:
    present = sorted(p.name for p in DATA_DIR.iterdir())
    assert present == sorted(EXPECTED_SHA256)


def test_pipeline_never_mentions_answer_key() -> None:
    bad_files = [
        str(file.relative_to(ROOT))
        for file in python_files(PACKAGE_DIR)
        if "answer_key" in file.read_text(encoding="utf-8")
    ]
    assert bad_files == [], f"answer_key found in: {bad_files}"


def test_domain_packs_are_found() -> None:
    assert PACK_FILES, "no domains/*/pack.yaml found"
    assert "widevine" in FORBIDDEN_CORE_TERMS


def test_core_has_no_domain_words() -> None:
    hits: list[str] = []
    for file in python_files(CORE_DIR):
        text = file.read_text(encoding="utf-8")
        for term in FORBIDDEN_CORE_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                hits.append(f"{file.relative_to(ROOT)}: {term}")
    assert hits == [], f"domain words in core: {hits}"
