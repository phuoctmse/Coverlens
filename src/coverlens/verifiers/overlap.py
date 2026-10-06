"""Tier 2: a rule-based judge that settles clear coverage without the LLM.

If one candidate case contains at least `min_overlap` of the requirement's
terms, the requirement is COVERED by that case. Otherwise the verifier passes
on to Tier 3. It never concludes GAP: low overlap does not prove a gap (on the
dev set the overlap rule's "covered" calls were 25/25 right, its "gap" calls
18/27 wrong).
"""

from collections.abc import Mapping, Sequence

from coverlens.core.bm25 import Tokenizer
from coverlens.core.models import Case, Requirement, Status, Verdict

DEFAULT_MIN_OVERLAP = 0.75


def case_text(case: Case) -> str:
    return f"{case.title} {case.preconditions} {case.steps} {case.expected_result}"


def best_overlap(
    requirement: Requirement,
    candidates: Sequence[Case],
    tokenize: Tokenizer | None = None,
) -> tuple[Case | None, float]:
    """The candidate sharing the largest share of the requirement's terms.

    Ties go to the earlier candidate; (None, 0.0) when nothing overlaps.
    """
    tokenize = tokenize or Tokenizer()
    wanted = set(tokenize(requirement.text))
    best: Case | None = None
    best_share = 0.0
    if wanted:
        for case in candidates:
            share = len(wanted & set(tokenize(case_text(case)))) / len(wanted)
            if share > best_share:
                best, best_share = case, share
    return best, best_share


class OverlapVerifier:
    def __init__(
        self,
        min_overlap: float = DEFAULT_MIN_OVERLAP,
        glossary: Mapping[str, str] | None = None,
    ) -> None:
        self._min_overlap = min_overlap
        self._tokenize = Tokenizer(glossary)

    def judge(
        self, requirement: Requirement, candidates: Sequence[Case]
    ) -> Verdict | None:
        best, share = best_overlap(requirement, candidates, self._tokenize)
        if best is None or share < self._min_overlap:
            return None
        return Verdict(
            requirement_id=requirement.id,
            status=Status.COVERED,
            tier=2,
            cited_case_ids=(best.id,),
            rationale=f"Tier 2: {share:.0%} of the criterion's terms appear in {best.id}.",
        )
