"""Lists the requirements where the pipeline and the answer key disagree, with
everything a reviewer needs to decide, plus a review entry to fill in."""

import datetime
from collections.abc import Mapping

from coverlens.core.models import Case
from coverlens.core.report import Report
from eval.answer_key import AnswerKey
from eval.label_review import Review, key_label


def format_disagreements(
    report: Report,
    key: AnswerKey,
    cases: Mapping[str, Case],
    reviews: Mapping[str, Review],
    today: datetime.date | None = None,
    reviews_path: str = "the reviews file",
) -> str:
    today = today or datetime.datetime.now().astimezone().date()
    rows = [
        row
        for row in report.requirements
        if row.status.value != key_label(key, row.requirement_id)
    ]
    lines = [f"Disagreements with the answer key: {len(rows)}"]
    for row in rows:
        rid = row.requirement_id
        label = key_label(key, rid)
        gold = key.covered.get(rid, ())
        lines += [
            "",
            f"== {rid} (story {row.story_id})",
            f"Criterion:  {row.text}",
            f"Answer key: {label}" + (f" by {', '.join(gold)}" if gold else ""),
            f"Pipeline:   {row.status.value} (tier {row.tier})"
            + (
                f" citing {', '.join(row.cited_case_ids)}" if row.cited_case_ids else ""
            ),
            f"Rationale:  {row.rationale}",
        ]
        if rid in reviews:
            done = reviews[rid]
            lines.append(
                f"Reviewed:   {done.reviewed_label} by {done.reviewer} on {done.date}"
                + (f" ({done.note})" if done.note else "")
            )
        shown = dict.fromkeys([*row.cited_case_ids, *gold, *row.candidate_ids])
        lines.append("Cases:")
        for case_id in shown:
            if case_id in cases:
                text = cases[case_id].judge_text().replace("\n", "\n    ")
                lines.append(f"  [{case_id}]\n    {text}")
    pending = [row for row in rows if row.requirement_id not in reviews]
    if pending:
        lines += ["", f"# Add under 'reviews:' in {reviews_path}:"]
        for row in pending:
            lines += [
                f"  - requirement_id: {row.requirement_id}",
                f"    key_label: {key_label(key, row.requirement_id)}",
                "    reviewed_label:      # covered or gap",
                "    covered_by: []       # case IDs, when covered",
                '    note: ""',
                '    reviewer: ""',
                f"    date: {today.isoformat()}",
            ]
    return "\n".join(lines)
