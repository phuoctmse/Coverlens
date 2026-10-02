"""Tier 2 placeholder: never decides, so every requirement passes to Tier 3."""

from collections.abc import Sequence

from coverlens.core.models import Case, Requirement, Verdict


class NoopVerifier:
    def judge(
        self, requirement: Requirement, candidates: Sequence[Case]
    ) -> Verdict | None:
        return None
