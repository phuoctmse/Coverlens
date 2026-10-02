"""Offline Tier 3 stand-in: a deterministic word-overlap judge, no LLM.

Used by `--fake` runs and tests. Its verdicts are plausible, not trustworthy.
"""

from collections.abc import Mapping, Sequence

from coverlens.core.bm25 import Tokenizer
from coverlens.core.models import Case, Requirement, Status, Verdict


class FakeVerifier:
    def __init__(
        self, min_overlap: float = 0.75, glossary: Mapping[str, str] | None = None
    ) -> None:
        self._min_overlap = min_overlap
        self._tokenize = Tokenizer(glossary)

    def _overlap(self, wanted: set[str], case: Case) -> float:
        text = f"{case.title} {case.preconditions} {case.steps} {case.expected_result}"
        return len(wanted & set(self._tokenize(text))) / len(wanted)

    def judge(
        self, requirement: Requirement, candidates: Sequence[Case]
    ) -> Verdict | None:
        wanted = set(self._tokenize(requirement.text))
        best: Case | None = None
        best_overlap = 0.0
        if wanted:
            for case in candidates:
                overlap = self._overlap(wanted, case)
                if overlap > best_overlap:
                    best, best_overlap = case, overlap
        if best is not None and best_overlap >= self._min_overlap:
            return Verdict(
                requirement_id=requirement.id,
                status=Status.COVERED,
                tier=3,
                cited_case_ids=(best.id,),
                rationale=f"Fake judge: {best_overlap:.0%} of the terms appear in {best.id}.",
            )
        return Verdict(
            requirement_id=requirement.id,
            status=Status.GAP,
            tier=3,
            rationale=f"Fake judge: best term overlap {best_overlap:.0%} is too low.",
        )
