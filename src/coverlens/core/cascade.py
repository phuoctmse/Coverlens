"""Runs Tier 1, then each verifier in order, and checks what they return."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from coverlens.core.bm25 import Tokenizer
from coverlens.core.models import Case, Requirement, Status, Verdict
from coverlens.core.pack import PackConfig
from coverlens.core.protocols import Verifier
from coverlens.core.tier1 import screen


class CoverageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdicts: tuple[Verdict, ...]  # one per requirement, in spec order
    orphan_case_ids: tuple[str, ...]
    candidate_ids: dict[str, tuple[str, ...]]  # requirement ID -> cases shown


def _uncertain(requirement_id: str, tier: int, reason: str) -> Verdict:
    return Verdict(
        requirement_id=requirement_id,
        status=Status.UNCERTAIN,
        tier=tier,  # type: ignore[arg-type]
        rationale=reason,
    )


def _checked(verdict: Verdict, requirement_id: str, allowed: Sequence[str]) -> Verdict:
    """Accept a verifier's verdict, or replace it with UNCERTAIN saying why."""
    tier = max(verdict.tier, 2)
    if verdict.requirement_id != requirement_id:
        return _uncertain(
            requirement_id,
            tier,
            f"Verifier answered for {verdict.requirement_id}, not {requirement_id}.",
        )
    if verdict.tier == 1:
        return _uncertain(requirement_id, tier, "A verifier may not claim Tier 1.")
    invalid = [cid for cid in verdict.cited_case_ids if cid not in allowed]
    if invalid:
        return _uncertain(
            requirement_id,
            tier,
            f"Cited cases {invalid} were not among the candidates shown.",
        )
    return verdict


def run_cascade(
    requirements: Sequence[Requirement],
    cases: Sequence[Case],
    pack: PackConfig,
    verifiers: Sequence[Verifier],
) -> CoverageResult:
    tier1 = screen(
        requirements, cases, pack.tier1, Tokenizer(pack.glossary), pack.tag_map
    )
    cases_by_id = {case.id: case for case in cases}
    verdicts: list[Verdict] = []
    for requirement, screening in zip(requirements, tier1.screenings, strict=True):
        if screening.verdict is not None:
            verdicts.append(screening.verdict)
            continue
        candidates = [cases_by_id[cid] for cid in screening.candidate_ids]
        verdict: Verdict | None = None
        for verifier in verifiers:
            answer = verifier.judge(requirement, candidates)
            if answer is not None:
                verdict = _checked(answer, requirement.id, screening.candidate_ids)
                break
        verdicts.append(
            verdict or _uncertain(requirement.id, 3, "No tier reached a verdict.")
        )
    return CoverageResult(
        verdicts=tuple(verdicts),
        orphan_case_ids=tier1.orphan_case_ids,
        candidate_ids={s.requirement_id: s.candidate_ids for s in tier1.screenings},
    )
