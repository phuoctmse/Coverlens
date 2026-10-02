"""The answer key: ground truth for evaluation. Only eval/ may read it."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "ott_web"
DEFAULT_KEY = DATA_DIR / "answer_key.json"


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
