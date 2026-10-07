"""Repo-wide rules from CLAUDE.md, enforced as tests."""

import ast
import hashlib
import re
from pathlib import Path

from coverlens.core.pack import load_pack

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "src" / "coverlens"
CORE_DIR = PACKAGE_DIR / "core"
DATA_ROOT = ROOT / "data"

# data/ is read-only input; re-pin only if a dataset is deliberately replaced.
# data/claims/ is written once by eval/datasets/build_claims.py.
EXPECTED_SHA256: dict[str, dict[str, str]] = {
    "ott_web": {
        "answer_key.json": "d45aa4a7d79b152a98b1cfd8a818f5f99886e879ff51587d275e96ab4d8210e5",
        "test_cases.xlsx": "386c3039e8ec28ec6d17eca21ea0ab946498bb690245d573b8dc9d06714adb16",
        "user_stories.md": "c7df8e4ce13b0565ccea220d27679fcf6a9256965771e06f14b367c9289bba3f",
    },
    "claims": {
        "answer_key.json": "ad9425a51d493991c7910563d7de09a96a36faa0e354081d98a05e9e2b2f1501",
        "test_cases.xlsx": "7d6f79b9e7ad456c24bb9cf8a729ed65fd58842538ebce3d12ec592aa83020c5",
        "user_stories.md": "96ea2178d397e8acb0c4afc7fd3cf11ad110f72b4156590d6e43795d2c95333f",
    },
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
        f"{dataset}/{name}"
        for dataset, files in EXPECTED_SHA256.items()
        for name, expected in files.items()
        if hashlib.sha256((DATA_ROOT / dataset / name).read_bytes()).hexdigest()
        != expected
    ]
    assert changed == [], f"data/ is read-only, but these files changed: {changed}"


def test_data_dir_has_only_pinned_files() -> None:
    present = {
        p.relative_to(DATA_ROOT).as_posix() for p in DATA_ROOT.rglob("*") if p.is_file()
    }
    pinned = {f"{d}/{name}" for d, files in EXPECTED_SHA256.items() for name in files}
    assert present == pinned


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


ALLOWED_PROTOCOLS = {"InputAdapter", "Verifier", "OutputWriter"}


def test_only_the_three_extension_points_are_protocols() -> None:
    protocols: list[str] = []
    for file in python_files(PACKAGE_DIR):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                ast.unparse(base).split("[")[0].endswith("Protocol")
                for base in node.bases
            ):
                protocols.append(node.name)
    assert set(protocols) <= ALLOWED_PROTOCOLS, f"extra protocols: {protocols}"
    assert len(protocols) == len(set(protocols)), f"duplicates: {protocols}"


def test_pipeline_never_imports_eval() -> None:
    offenders: list[str] = []
    for file in python_files(PACKAGE_DIR):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            if any(m == "eval" or m.startswith("eval.") for m in modules):
                offenders.append(str(file.relative_to(ROOT)))
    assert offenders == [], f"src/ imports eval/: {offenders}"


def test_dotenv_is_never_committed() -> None:
    """The real .env holds the Ollama Cloud key; git must ignore it."""
    import subprocess

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".env"], cwd=ROOT, check=False
    )
    assert ignored.returncode == 0, ".env must be listed in .gitignore"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert tracked.returncode != 0, ".env is tracked by git"
