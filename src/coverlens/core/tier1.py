"""Tier 1: cheap screening with refs, tags and BM25. Never concludes COVERED.

For each requirement it either concludes a certain gap or hands the next tier a
short list of candidate cases. It also flags cases that look like orphans.
"""

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from coverlens.core.bm25 import Bm25Index, Tokenizer
from coverlens.core.models import Case, Requirement, Status, Verdict
from coverlens.core.pack import Tier1Config


class Screening(BaseModel):
    model_config = ConfigDict(frozen=True)

    requirement_id: str
    top_score: float  # best BM25 score against any case; 0.0 if nothing matched
    candidate_ids: tuple[str, ...]  # empty when verdict is set
    verdict: Verdict | None = None  # a Tier 1 GAP, or None to pass on


class Tier1Result(BaseModel):
    model_config = ConfigDict(frozen=True)

    screenings: tuple[Screening, ...]
    orphan_case_ids: tuple[str, ...]


def search_text(case: Case) -> str:
    """Text used for matching. Preconditions are left out: they mostly restate
    the dimension columns and blur the gap between covered and uncovered."""
    return f"{case.title} {case.steps} {case.expected_result}"


def _screen_one(
    requirement: Requirement,
    case_index: Bm25Index,
    tokenize: Tokenizer,
    referencing: Sequence[str],
    tagged: Sequence[str],
    config: Tier1Config,
) -> Screening:
    ranked = case_index.top_k(tokenize(requirement.text), config.top_k)
    top_score = ranked[0][1] if ranked else 0.0

    if not referencing and top_score < config.gap_threshold:
        verdict = Verdict(
            requirement_id=requirement.id,
            status=Status.GAP,
            tier=1,
            rationale=(
                f"No case references {requirement.id} and the best text match "
                f"scores {top_score:.2f}, below {config.gap_threshold}."
            ),
        )
        return Screening(
            requirement_id=requirement.id,
            top_score=top_score,
            candidate_ids=(),
            verdict=verdict,
        )

    candidates = dict.fromkeys([case_id for case_id, _ in ranked])
    candidates.update(dict.fromkeys(referencing))
    candidates.update(dict.fromkeys(tagged))
    return Screening(
        requirement_id=requirement.id,
        top_score=top_score,
        candidate_ids=tuple(candidates),
    )


def _orphans(
    requirements: Sequence[Requirement],
    cases: Sequence[Case],
    tokenize: Tokenizer,
    config: Tier1Config,
) -> tuple[str, ...]:
    requirement_index = Bm25Index({r.id: tokenize(r.text) for r in requirements})
    orphans: list[str] = []
    for case in cases:
        if case.refs or case.tags:
            continue
        best = requirement_index.top_k(tokenize(search_text(case)), 1)
        if not best or best[0][1] < config.orphan_threshold:
            orphans.append(case.id)
    return tuple(orphans)


def screen(
    requirements: Sequence[Requirement],
    cases: Sequence[Case],
    config: Tier1Config,
    tokenize: Tokenizer,
    tag_map: Mapping[str, str],
) -> Tier1Result:
    """Screen every requirement against the suite.

    `tag_map` maps a case tag to a requirement parent ID; tagged cases only
    become extra candidates for that parent's requirements.
    """
    case_index = Bm25Index({c.id: tokenize(search_text(c)) for c in cases})
    referencing: dict[str, list[str]] = {}
    tagged: dict[str, list[str]] = {}
    for case in cases:
        for ref in case.refs:
            referencing.setdefault(ref, []).append(case.id)
        for tag in case.tags:
            if parent := tag_map.get(tag):
                tagged.setdefault(parent, []).append(case.id)

    screenings = tuple(
        _screen_one(
            requirement,
            case_index,
            tokenize,
            referencing.get(requirement.id, []),
            tagged.get(requirement.parent_id, []),
            config,
        )
        for requirement in requirements
    )
    return Tier1Result(
        screenings=screenings,
        orphan_case_ids=_orphans(requirements, cases, tokenize, config),
    )
