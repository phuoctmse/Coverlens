"""The gap report: per-requirement rows, story rollup and case findings.

Writers only format a Report; every judgement about the results is made here.
"""

from collections import Counter
from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from coverlens.core.models import Case, CoverageResult, Requirement, Status


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class StoryStatus(StrEnum):
    COVERED = "covered"
    PARTIAL = "partial"
    GAP = "gap"


class RequirementRow(_Frozen):
    requirement_id: str
    story_id: str
    text: str
    status: Status
    tier: int
    cited_case_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    rationale: str


class StoryRollup(_Frozen):
    story_id: str
    total: int
    covered: int
    gap: int
    uncertain: int
    status: StoryStatus


class MisReference(_Frozen):
    """A case that names a requirement it does not cover."""

    case_id: str
    requirement_id: str
    reason: str


class Summary(_Frozen):
    requirements: int
    cases: int
    covered: int
    gap: int
    uncertain: int
    coverage: float  # covered / requirements


class Report(_Frozen):
    pack_name: str
    summary: Summary
    requirements: tuple[RequirementRow, ...]
    stories: tuple[StoryRollup, ...]
    orphan_case_ids: tuple[str, ...]
    mis_referenced: tuple[MisReference, ...]


def _rollup(rows: Sequence[RequirementRow]) -> tuple[StoryRollup, ...]:
    by_story: dict[str, Counter[Status]] = {}
    for row in rows:
        by_story.setdefault(row.story_id, Counter())[row.status] += 1
    rollups = []
    for story_id, counts in by_story.items():
        total = counts.total()
        covered = counts[Status.COVERED]
        if covered == total:
            status = StoryStatus.COVERED
        elif covered:
            status = StoryStatus.PARTIAL
        else:
            status = StoryStatus.GAP
        rollups.append(
            StoryRollup(
                story_id=story_id,
                total=total,
                covered=covered,
                gap=counts[Status.GAP],
                uncertain=counts[Status.UNCERTAIN],
                status=status,
            )
        )
    return tuple(rollups)


def _mis_referenced(
    cases: Sequence[Case], status_of: dict[str, Status]
) -> tuple[MisReference, ...]:
    """Refs that the results contradict. Refs to uncertain requirements are skipped."""
    found = []
    for case in cases:
        for ref in case.refs:
            if ref not in status_of:
                reason = f"{ref} is not in the spec."
            elif status_of[ref] is Status.GAP:
                reason = f"{ref} was judged a gap: no case covers it."
            else:
                continue
            found.append(
                MisReference(case_id=case.id, requirement_id=ref, reason=reason)
            )
    return tuple(found)


def build_report(
    requirements: Sequence[Requirement],
    cases: Sequence[Case],
    result: CoverageResult,
    pack_name: str,
) -> Report:
    verdicts = {v.requirement_id: v for v in result.verdicts}
    rows = tuple(
        RequirementRow(
            requirement_id=req.id,
            story_id=req.parent_id,
            text=req.text,
            status=verdicts[req.id].status,
            tier=verdicts[req.id].tier,
            cited_case_ids=verdicts[req.id].cited_case_ids,
            candidate_ids=result.candidate_ids.get(req.id, ()),
            rationale=verdicts[req.id].rationale,
        )
        for req in requirements
    )
    counts = Counter(row.status for row in rows)
    summary = Summary(
        requirements=len(rows),
        cases=len(cases),
        covered=counts[Status.COVERED],
        gap=counts[Status.GAP],
        uncertain=counts[Status.UNCERTAIN],
        coverage=counts[Status.COVERED] / len(rows) if rows else 0.0,
    )
    return Report(
        pack_name=pack_name,
        summary=summary,
        requirements=rows,
        stories=_rollup(rows),
        orphan_case_ids=result.orphan_case_ids,
        mis_referenced=_mis_referenced(
            cases, {row.requirement_id: row.status for row in rows}
        ),
    )
