"""Domain pack: everything domain-specific, loaded from YAML into typed config."""

from collections.abc import Mapping
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


class Constraint(_Config):
    """When every `if` dimension has its value, each `then` dimension must take
    one of the listed values. Combinations breaking it cannot occur."""

    when: dict[str, str] = Field(alias="if", min_length=1)
    then: dict[str, tuple[str, ...]] = Field(min_length=1)

    def allows(self, row: Mapping[str, str]) -> bool:
        """True unless `row` (possibly partial) is known to break the rule."""
        if any(row.get(dim) != value for dim, value in self.when.items()):
            return True
        return all(
            row[dim] in allowed for dim, allowed in self.then.items() if dim in row
        )


class PairwiseConfig(_Config):
    """The values each dimension can take, and the combinations that cannot occur."""

    values: dict[str, tuple[str, ...]] = Field(min_length=2)
    constraints: tuple[Constraint, ...] = ()

    @model_validator(mode="after")
    def _constraints_use_known_values(self) -> Self:
        for constraint in self.constraints:
            used = [(d, (v,)) for d, v in constraint.when.items()]
            used += list(constraint.then.items())
            for dim, values in used:
                if dim not in self.values:
                    raise ValueError(f"constraint uses unknown dimension {dim!r}")
                unknown = [v for v in values if v not in self.values[dim]]
                if unknown:
                    raise ValueError(f"constraint uses unknown {dim} values {unknown}")
        return self

    def allows(self, row: Mapping[str, str]) -> bool:
        return all(constraint.allows(row) for constraint in self.constraints)


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
    pairwise: PairwiseConfig | None = None

    @model_validator(mode="after")
    def _pairwise_uses_suite_dimensions(self) -> Self:
        if self.pairwise is not None:
            extra = sorted(set(self.pairwise.values) - set(self.suite.dimensions))
            if extra:
                raise ValueError(f"pairwise values for non-dimension columns: {extra}")
        return self


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
