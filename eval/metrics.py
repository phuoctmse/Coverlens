"""Scores a report against the answer key."""

from pydantic import BaseModel, ConfigDict

from coverlens.core.models import Status
from coverlens.core.report import Report
from eval.answer_key import AnswerKey


class Rate(BaseModel):
    model_config = ConfigDict(frozen=True)

    hit: int
    total: int

    @property
    def value(self) -> float | None:
        return self.hit / self.total if self.total else None

    def __str__(self) -> str:
        value = self.value
        share = "n/a" if value is None else f"{value:.0%}"
        return f"{self.hit}/{self.total} ({share})"


def _rate(found: set[str], relevant: set[str]) -> Rate:
    return Rate(hit=len(found & relevant), total=len(found))


class EvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    gap_precision: Rate
    gap_recall: Rate
    covered_precision: Rate
    covered_recall: Rate
    citation_accuracy: (
        Rate  # covered verdicts on covered requirements citing a gold case
    )
    candidate_recall: Rate  # covered requirements with a gold case among candidates
    orphan_precision: Rate
    orphan_recall: Rate
    decoys_flagged: Rate  # decoys reported as mis-referenced
    uncertain: int
    tier1_false_gaps: tuple[str, ...]  # canary: must stay empty

    @property
    def canary_ok(self) -> bool:
        return not self.tier1_false_gaps


def evaluate(report: Report, key: AnswerKey) -> EvalResult:
    rows = {row.requirement_id: row for row in report.requirements}
    known = set(key.covered) | set(key.true_gaps)
    if known != set(rows):
        raise ValueError(
            "answer key and report disagree on requirements: "
            f"only in key {sorted(known - set(rows))}, "
            f"only in report {sorted(set(rows) - known)}"
        )

    covered = set(key.covered)
    gaps = set(key.true_gaps)
    said_gap = {rid for rid, row in rows.items() if row.status is Status.GAP}
    said_covered = {rid for rid, row in rows.items() if row.status is Status.COVERED}
    orphans_found = set(report.orphan_case_ids)
    orphans_true = set(key.orphan_cases)
    flagged = {(m.case_id, m.requirement_id) for m in report.mis_referenced}

    cited_right = sum(
        1
        for rid in said_covered & covered
        if set(rows[rid].cited_case_ids) & set(key.covered[rid])
    )
    candidates_right = sum(
        1 for rid in covered if set(rows[rid].candidate_ids) & set(key.covered[rid])
    )
    return EvalResult(
        gap_precision=_rate(said_gap, gaps),
        gap_recall=_rate(gaps, said_gap),
        covered_precision=_rate(said_covered, covered),
        covered_recall=_rate(covered, said_covered),
        citation_accuracy=Rate(hit=cited_right, total=len(said_covered & covered)),
        candidate_recall=Rate(hit=candidates_right, total=len(covered)),
        orphan_precision=_rate(orphans_found, orphans_true),
        orphan_recall=_rate(orphans_true, orphans_found),
        decoys_flagged=Rate(
            hit=sum(
                1 for d in key.decoys_claiming_gap_acs if (d.id, d.claims) in flagged
            ),
            total=len(key.decoys_claiming_gap_acs),
        ),
        uncertain=sum(1 for row in rows.values() if row.status is Status.UNCERTAIN),
        tier1_false_gaps=tuple(
            rid
            for rid, row in rows.items()
            if row.tier == 1 and row.status is Status.GAP and rid in covered
        ),
    )


def format_result(result: EvalResult) -> str:
    lines = [
        f"Gap precision       {result.gap_precision}",
        f"Gap recall          {result.gap_recall}",
        f"Covered precision   {result.covered_precision}",
        f"Covered recall      {result.covered_recall}",
        f"Citation accuracy   {result.citation_accuracy}",
        f"Candidate recall    {result.candidate_recall}",
        f"Orphan precision    {result.orphan_precision}",
        f"Orphan recall       {result.orphan_recall}",
        f"Decoys flagged      {result.decoys_flagged}",
        f"Uncertain           {result.uncertain}",
    ]
    if result.canary_ok:
        lines.append("Canary              PASS (no Tier 1 false gaps)")
    else:
        lines.append(
            f"Canary              FAIL: Tier 1 called covered requirements gaps: "
            f"{', '.join(result.tier1_false_gaps)}"
        )
    return "\n".join(lines)
