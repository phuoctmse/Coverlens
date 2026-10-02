from pathlib import Path


def test_pipeline_never_mentions_answer_key() -> None:
    bad_files: list[str] = []
    for file in Path("src/coverlens").rglob("*.py"):
        text = file.read_text(encoding="utf-8")
        if "answer_key" in text:
            bad_files.append(str(file))
    assert bad_files == [], f"answer_key found in: {bad_files}"
