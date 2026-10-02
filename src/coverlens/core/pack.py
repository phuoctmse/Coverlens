"""Domain pack: everything domain-specific, loaded from YAML into typed config."""

from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)


class PackError(ValueError):
    """The domain pack is missing, unreadable or invalid."""


class _Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ColumnMap(_Config):
    """Suite header names for each `Case` field. None means the suite has no such column."""

    id: str
    title: str
    preconditions: str | None = None
    steps: str
    expected_result: str
    refs: str | None = None
    tags: str | None = None


class SuiteConfig(_Config):
    sheet: str
    columns: ColumnMap
    dimensions: tuple[str, ...] = ()
    list_separator: str = Field(default=",", min_length=1)

    @model_validator(mode="after")
    def _dimensions_are_separate_columns(self) -> Self:
        mapped = {c for c in self.columns.model_dump().values() if c}
        reused = sorted(mapped & set(self.dimensions))
        if reused:
            raise ValueError(f"dimensions reuse mapped columns: {reused}")
        return self


class Tier1Config(_Config):
    """Tier 1 thresholds. BM25 scores depend on the corpus, so they are per pack."""

    top_k: int = Field(ge=1)
    gap_threshold: float = Field(ge=0)  # tau_gap
    orphan_threshold: float = Field(ge=0)  # tau_orphan


def _lowercase(terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term.lower() for term in terms)


class PackConfig(_Config):
    name: str
    suite: SuiteConfig
    tag_map: dict[str, str] = {}
    tier1: Tier1Config
    glossary: dict[str, str] = {}  # phrase -> canonical term, for matching
    forbidden_core_terms: Annotated[
        tuple[str, ...], Field(min_length=1), AfterValidator(_lowercase)
    ]


def load_pack(path: Path) -> PackConfig:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PackError(f"{path}: cannot read domain pack: {exc}") from exc
    if not isinstance(data, dict):
        raise PackError(f"{path}: domain pack must be a YAML mapping")
    try:
        return PackConfig.model_validate(data)
    except ValidationError as exc:
        raise PackError(f"{path}: invalid domain pack\n{exc}") from exc
