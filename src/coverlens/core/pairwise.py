"""Pairwise coverage of the suite's dimensions. Measures only; never writes cases.

The required pairs are every value pair that occurs in at least one combination
the pack's constraints allow, found by enumerating all combinations (exact, and
cheap at pack sizes). allpairspy is not used for this: with a constraint filter
its greedy search can miss valid pairs. It is used only to estimate how many
more combinations would cover the pairs the suite misses.
"""

import itertools
from collections.abc import Callable, Iterable, Mapping, Sequence

from allpairspy import AllPairs
from pydantic import BaseModel, ConfigDict

from coverlens.core.models import Case
from coverlens.core.pack import PairwiseConfig


class Pair(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension_a: str
    value_a: str
    dimension_b: str
    value_b: str


class PairwiseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    required: int  # value pairs that can occur under the constraints
    covered: int  # of those, pairs some case exercises
    coverage: float
    missing: tuple[Pair, ...]  # in dimension, then value, order
    unknown_values: tuple[str, ...]  # "Dimension=value" not declared in the pack
    extra_combinations: int  # pairwise rows needed on top of the suite


def _pairs_of(row: Mapping[str, str], dimensions: Sequence[str]) -> set[Pair]:
    present = [d for d in dimensions if d in row]
    return {
        Pair(dimension_a=a, value_a=row[a], dimension_b=b, value_b=row[b])
        for a, b in itertools.combinations(present, 2)
    }


def _pairwise_rows(
    config: PairwiseConfig, already_tested: Iterable[Sequence[str]] = ()
) -> list[list[str]]:
    dimensions = list(config.values)

    def valid(partial: Sequence[str]) -> bool:
        return config.allows(dict(zip(dimensions, partial, strict=False)))

    return [
        list(row)
        for row in AllPairs(
            [list(values) for values in config.values.values()],
            filter_func=valid,
            previously_tested=[list(r) for r in already_tested] or None,
        )
    ]


def required_pairs(config: PairwiseConfig) -> set[Pair]:
    dimensions = list(config.values)
    found: set[Pair] = set()
    for combination in itertools.product(*config.values.values()):
        row = dict(zip(dimensions, combination, strict=True))
        if config.allows(row):
            found |= _pairs_of(row, dimensions)
    return found


def _sort_key(config: PairwiseConfig) -> Callable[[Pair], tuple[int, int, int, int]]:
    dims = list(config.values)

    def key(pair: Pair) -> tuple[int, int, int, int]:
        return (
            dims.index(pair.dimension_a),
            config.values[pair.dimension_a].index(pair.value_a),
            dims.index(pair.dimension_b),
            config.values[pair.dimension_b].index(pair.value_b),
        )

    return key


def measure(config: PairwiseConfig, cases: Sequence[Case]) -> PairwiseResult:
    dimensions = list(config.values)
    exercised: set[Pair] = set()
    unknown: dict[str, None] = {}
    full_rows: list[list[str]] = []
    for case in cases:
        row: dict[str, str] = {}
        for dim in dimensions:
            value = case.dimensions.get(dim)
            if value is None:
                continue
            if value in config.values[dim]:
                row[dim] = value
            else:
                unknown[f"{dim}={value}"] = None
        exercised |= _pairs_of(row, dimensions)
        if len(row) == len(dimensions) and config.allows(row):
            full_rows.append([row[d] for d in dimensions])

    required = required_pairs(config)
    covered = required & exercised
    missing = sorted(required - exercised, key=_sort_key(config))
    return PairwiseResult(
        required=len(required),
        covered=len(covered),
        coverage=len(covered) / len(required) if required else 1.0,
        missing=tuple(missing),
        unknown_values=tuple(unknown),
        extra_combinations=len(_pairwise_rows(config, full_rows)) if missing else 0,
    )
