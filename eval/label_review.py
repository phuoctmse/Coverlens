"""Human review of answer-key labels, applied on top of the key at eval time.

The key in data/ is read-only and was built by an AI. A reviewer records
decisions here only for requirements where the pipeline and the key disagree;
eval then scores against both the raw key and the reviewed key.
"""

import datetime
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eval.answer_key import AnswerKey

Label = Literal["covered", "gap"]


class Review(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str
    key_label: Label  # what the key says; guards against a stale review
    reviewed_label: Label
    covered_by: tuple[str, ...] = ()  # case IDs, when reviewed as covered
    note: str = ""
    reviewer: str = Field(min_length=1)
    date: datetime.date


class _ReviewFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviews: list[Review] = []


def key_label(key: AnswerKey, requirement_id: str) -> Label | None:
    if requirement_id in key.covered:
        return "covered"
    if requirement_id in key.true_gaps:
        return "gap"
    return None


def load_reviews(path: Path, key: AnswerKey) -> list[Review]:
    """Reviews from `path`, checked against `key`. A missing file means none."""
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        reviews = _ReviewFile.model_validate(data).reviews
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ValueError(f"{path}: invalid label review\n{exc}") from exc
    seen: set[str] = set()
    for review in reviews:
        rid = review.requirement_id
        actual = key_label(key, rid)
        if actual is None:
            raise ValueError(f"{path}: {rid} is not in the answer key")
        if actual != review.key_label:
            raise ValueError(
                f"{path}: review of {rid} is stale: it says the key has "
                f"{review.key_label}, the key has {actual}"
            )
        if rid in seen:
            raise ValueError(f"{path}: {rid} is reviewed twice")
        seen.add(rid)
    return reviews


def apply_reviews(key: AnswerKey, reviews: Sequence[Review]) -> AnswerKey:
    covered = dict(key.covered)
    gaps = list(key.true_gaps)
    for review in reviews:
        rid = review.requirement_id
        if review.reviewed_label == review.key_label:
            continue
        if review.reviewed_label == "covered":
            gaps.remove(rid)
            covered[rid] = review.covered_by
        else:
            del covered[rid]
            gaps.append(rid)
    return key.model_copy(
        update={
            "covered": covered,
            "true_gaps": tuple(gaps),
            "decoys_claiming_gap_acs": tuple(
                d for d in key.decoys_claiming_gap_acs if d.claims in gaps
            ),
        }
    )


def changed_count(reviews: Sequence[Review]) -> int:
    return sum(r.reviewed_label != r.key_label for r in reviews)
