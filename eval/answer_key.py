"""The answer key: ground truth for evaluation. Only eval/ may read it."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "ott_web"
DEFAULT_KEY = DATA_DIR / "answer_key.json"
DATASETS = ("ott_web", "claims")


@dataclass(frozen=True)
class DatasetPaths:
    pack: Path
    spec: Path
    suite: Path
    key: Path
    reviews: Path


def dataset_paths(name: str) -> DatasetPaths:
    """Where a dataset's pack, inputs, answer key and label reviews live."""
    data = ROOT / "data" / name
    return DatasetPaths(
        pack=ROOT / "domains" / name / "pack.yaml",
        spec=data / "user_stories.md",
        suite=data / "test_cases.xlsx",
        key=data / "answer_key.json",
        reviews=ROOT / "eval" / "reviews" / f"{name}.yaml",
    )


class Decoy(BaseModel):
    """A case that references a requirement nothing actually covers."""

    model_config = ConfigDict(frozen=True)

    id: str
    claims: str


class AnswerKey(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    covered: dict[str, tuple[str, ...]]  # requirement -> cases that cover it
    true_gaps: tuple[str, ...]
    decoys_claiming_gap_acs: tuple[Decoy, ...]
    orphan_cases: tuple[str, ...]


def load_key(path: Path = DEFAULT_KEY) -> AnswerKey:
    try:
        return AnswerKey.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"{path}: cannot load answer key: {exc}") from exc
