import itertools
from pathlib import Path
from typing import Any

import pytest

from coverlens.adapters.xlsx_suite import XlsxSuiteAdapter
from coverlens.core.models import Case
from coverlens.core.pack import PackConfig, PackError, PairwiseConfig, load_pack
from coverlens.core.pairwise import Pair, measure, required_pairs

ROOT = Path(__file__).resolve().parents[1]

CONFIG = PairwiseConfig.model_validate(
    {
        "values": {
            "OS": ["mac", "win"],
            "App": ["web", "desktop"],
            "Net": ["fast", "slow"],
        },
        "constraints": [{"if": {"OS": "mac"}, "then": {"App": ["web"]}}],
    }
)


def case(case_id: str, **dims: str) -> Case:
    return Case(id=case_id, title="t", steps="", expected_result="", dimensions=dims)


def brute_force(config: PairwiseConfig) -> set[Pair]:
    """Every pair that appears in at least one valid full combination."""
    dims = list(config.values)
    found: set[Pair] = set()
    for combo in itertools.product(*config.values.values()):
        row = dict(zip(dims, combo, strict=True))
        if not config.allows(row):
            continue
        for a, b in itertools.combinations(dims, 2):
            found.add(
                Pair(dimension_a=a, value_a=row[a], dimension_b=b, value_b=row[b])
            )
    return found


# --- required pairs ------------------------------------------------------------


def test_required_pairs_without_constraints_are_every_cross_pair() -> None:
    config = PairwiseConfig.model_validate(
        {"values": {"A": ["1", "2"], "B": ["x", "y", "z"], "C": ["p", "q"]}}
    )
    assert len(required_pairs(config)) == 2 * 3 + 2 * 2 + 3 * 2


def test_constraints_remove_impossible_pairs() -> None:
    pairs = required_pairs(CONFIG)
    assert (
        Pair(dimension_a="OS", value_a="mac", dimension_b="App", value_b="desktop")
        not in pairs
    )
    assert (
        Pair(dimension_a="OS", value_a="win", dimension_b="App", value_b="desktop")
        in pairs
    )


@pytest.mark.parametrize(
    "config",
    [
        CONFIG,
        PairwiseConfig.model_validate(
            {
                "values": {"A": ["1", "2", "3"], "B": ["x", "y"], "C": ["p", "q", "r"]},
                "constraints": [
                    {"if": {"A": "1"}, "then": {"B": ["x"]}},
                    {"if": {"B": "x"}, "then": {"C": ["p", "q"]}},
                ],
            }
        ),
    ],
)
def test_required_pairs_match_brute_force(config: PairwiseConfig) -> None:
    assert required_pairs(config) == brute_force(config)


# --- measuring a suite ---------------------------------------------------------


def test_suite_pairs_are_counted_and_missing_ones_listed() -> None:
    cases = [case("C-1", OS="win", App="web", Net="fast")]
    result = measure(CONFIG, cases)
    assert result.required == len(required_pairs(CONFIG))
    assert result.covered == 3
    assert len(result.missing) == result.required - 3
    assert (
        Pair(dimension_a="OS", value_a="win", dimension_b="App", value_b="web")
        not in result.missing
    )
    assert result.coverage == pytest.approx(3 / result.required)


def test_full_coverage_needs_no_extra_combinations() -> None:
    rows = [r for r in itertools.product(*CONFIG.values.values())]
    dims = list(CONFIG.values)
    cases = [
        case(f"C-{n}", **dict(zip(dims, row, strict=True)))
        for n, row in enumerate(rows)
        if CONFIG.allows(dict(zip(dims, row, strict=True)))
    ]
    result = measure(CONFIG, cases)
    assert result.missing == ()
    assert result.extra_combinations == 0


def test_empty_suite_needs_a_whole_pairwise_set() -> None:
    result = measure(CONFIG, [])
    assert result.covered == 0
    assert result.extra_combinations > 0


def test_unknown_values_are_reported_not_counted() -> None:
    result = measure(CONFIG, [case("C-1", OS="linux", App="web", Net="fast")])
    assert result.unknown_values == ("OS=linux",)
    assert result.covered == 1  # only App=web / Net=fast


def test_cases_missing_a_dimension_still_count_the_rest() -> None:
    result = measure(CONFIG, [case("C-1", OS="win", App="web")])
    assert result.covered == 1


# --- pack config ---------------------------------------------------------------


def base_pack() -> dict[str, Any]:
    return {
        "name": "sample",
        "suite": {
            "sheet": "S",
            "columns": {"id": "ID", "title": "T", "steps": "S", "expected_result": "E"},
            "dimensions": ["OS", "App"],
        },
        "tier1": {"top_k": 3, "gap_threshold": 1, "orphan_threshold": 1},
        "forbidden_core_terms": ["widget"],
    }


def test_pairwise_is_optional() -> None:
    assert PackConfig.model_validate(base_pack()).pairwise is None


@pytest.mark.parametrize(
    ("pairwise", "message"),
    [
        ({"values": {"OS": ["mac"], "Other": ["x"]}}, "Other"),
        (
            {
                "values": {"OS": ["mac"], "App": ["web"]},
                "constraints": [{"if": {"OS": "linux"}, "then": {"App": ["web"]}}],
            },
            "linux",
        ),
        (
            {
                "values": {"OS": ["mac"], "App": ["web"]},
                "constraints": [{"if": {"OS": "mac"}, "then": {"Net": ["fast"]}}],
            },
            "Net",
        ),
    ],
)
def test_pairwise_config_must_match_the_dimensions(
    tmp_path: Path, pairwise: dict[str, Any], message: str
) -> None:
    import yaml

    path = tmp_path / "pack.yaml"
    path.write_text(yaml.safe_dump(base_pack() | {"pairwise": pairwise}), "utf-8")
    with pytest.raises(PackError, match=message):
        load_pack(path)


# --- the ott_web pack and suite ------------------------------------------------


@pytest.fixture(scope="module")
def ott() -> tuple[PackConfig, list[Case]]:
    pack = load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")
    suite = XlsxSuiteAdapter().read(ROOT / "data" / "ott_web" / "test_cases.xlsx", pack)
    return pack, suite


def test_ott_pack_declares_every_dimension(ott: tuple[PackConfig, list[Case]]) -> None:
    pack, _ = ott
    assert pack.pairwise is not None
    assert tuple(pack.pairwise.values) == pack.suite.dimensions


def test_ott_suite_uses_only_declared_values(
    ott: tuple[PackConfig, list[Case]],
) -> None:
    pack, cases = ott
    assert pack.pairwise is not None
    assert measure(pack.pairwise, cases).unknown_values == ()


def test_ott_browser_drm_constraints_hold(ott: tuple[PackConfig, list[Case]]) -> None:
    pack, cases = ott
    assert pack.pairwise is not None
    pairs = required_pairs(pack.pairwise)
    safari_widevine = Pair(
        dimension_a="Browser",
        value_a="Safari",
        dimension_b="Protocol / DRM",
        value_b="DASH+Widevine",
    )
    chrome_widevine = Pair(
        dimension_a="Browser",
        value_a="Chrome",
        dimension_b="Protocol / DRM",
        value_b="DASH+Widevine",
    )
    assert safari_widevine not in pairs
    assert chrome_widevine in pairs
    assert chrome_widevine not in measure(pack.pairwise, cases).missing


def test_ott_extra_combinations_close_every_missing_pair(
    ott: tuple[PackConfig, list[Case]],
) -> None:
    from coverlens.core.pairwise import _pairs_of, _pairwise_rows

    pack, cases = ott
    assert pack.pairwise is not None
    dims = list(pack.pairwise.values)
    result = measure(pack.pairwise, cases)
    suite_rows = [[c.dimensions[d] for d in dims] for c in cases]
    extra = _pairwise_rows(pack.pairwise, suite_rows)
    assert len(extra) == result.extra_combinations
    closed = set().union(
        *(_pairs_of(dict(zip(dims, r, strict=True)), dims) for r in extra)
    )
    assert set(result.missing) <= closed
