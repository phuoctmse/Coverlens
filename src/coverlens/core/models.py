"""Core data models exchanged between adapters, verifiers and writers.

The unit of coverage is a single requirement (an acceptance criterion); its
parent (a story) is only used to roll results up.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Id = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Requirement(_Model):
    id: Id
    parent_id: Id
    text: str


class Case(_Model):
    """One case from the existing suite."""

    id: Id
    title: str
    preconditions: str = ""
    steps: str
    expected_result: str
    refs: tuple[Id, ...] = ()
    tags: tuple[str, ...] = ()
    dimensions: dict[str, str] = {}

    def judge_text(self) -> str:
        """The content a judge may see. Refs are claims, not evidence, so omitted."""
        return (
            f"Title: {self.title}\n"
            f"Preconditions: {self.preconditions}\n"
            f"Steps: {self.steps}\n"
            f"Expected result: {self.expected_result}"
        )


class Status(StrEnum):
    COVERED = "covered"
    GAP = "gap"
    UNCERTAIN = "uncertain"


class Verdict(_Model):
    requirement_id: Id
    status: Status
    tier: Literal[1, 2, 3]
    cited_case_ids: tuple[Id, ...] = ()
    rationale: str = ""

    @model_validator(mode="after")
    def _check_citations(self) -> Self:
        cited = self.cited_case_ids
        if self.status is Status.COVERED:
            if self.tier == 1:
                raise ValueError("Tier 1 may never conclude COVERED")
            if not cited:
                raise ValueError("a COVERED verdict must cite at least one case")
        elif cited:
            raise ValueError("only COVERED verdicts may cite cases")
        if len(set(cited)) != len(cited):
            raise ValueError(f"duplicate case IDs cited: {cited}")
        return self
