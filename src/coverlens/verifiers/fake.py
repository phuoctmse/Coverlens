"""Offline Tier 3 stand-in: a deterministic word-overlap judge, no LLM.

Used by `--fake` runs and tests. Its verdicts are plausible, not trustworthy.
It shares its scoring with the Tier 2 overlap rule, but also answers GAP.
"""

from collections.abc import Mapping, Sequence

from coverlens.core.bm25 import Tokenizer
from coverlens.core.models import Case, Requirement, Status, Verdict
from coverlens.verifiers.overlap import DEFAULT_MIN_OVERLAP, best_overlap


class FakeVerifier:
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
        if best is not None and share >= self._min_overlap:
            return Verdict(
                requirement_id=requirement.id,
                status=Status.COVERED,
                tier=3,
                cited_case_ids=(best.id,),
                rationale=f"Fake judge: {share:.0%} of the terms appear in {best.id}.",
            )
        return Verdict(
            requirement_id=requirement.id,
            status=Status.GAP,
            tier=3,
            rationale=f"Fake judge: best term overlap {share:.0%} is too low.",
        )
