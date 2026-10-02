from pathlib import Path

import pytest

from coverlens.adapters.markdown_spec import MarkdownSpecAdapter
from coverlens.adapters.xlsx_suite import XlsxSuiteAdapter
from coverlens.core.bm25 import Bm25Index, Tokenizer, stem
from coverlens.core.pack import load_pack

ROOT = Path(__file__).resolve().parents[1]

# --- stem ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("plays", "play"),
        ("playing", "play"),
        ("played", "play"),
        ("titles", "titl"),
        ("title", "titl"),
        ("saved", "sav"),
        ("save", "sav"),
        ("stories", "story"),
        ("matches", "match"),
        ("class", "class"),
        ("is", "is"),
        ("red", "red"),
        ("sing", "sing"),
        ("95", "95"),
    ],
)
def test_stem(word: str, expected: str) -> None:
    assert stem(word) == expected


# --- Tokenizer -----------------------------------------------------------------


def test_tokenizer_lowercases_splits_stems_and_drops_stopwords() -> None:
    tokens = Tokenizer()("The user signs in to the Home page!")
    assert tokens == ["user", "sign", "hom", "pag"]


def test_tokenizer_keeps_numbers() -> None:
    assert Tokenizer()("Watched past 95% within 60 seconds") == [
        "watch",
        "past",
        "95",
        "within",
        "60",
        "second",
    ]


def test_glossary_rewrites_whole_phrases_case_insensitively() -> None:
    tokenize = Tokenizer({"on demand": "vod"})
    assert tokenize("On demand titles") == ["vod", "titl"]
    assert tokenize("On-demand titles") == ["vod", "titl"]
    assert tokenize("Ondemand titles") == ["ondemand", "titl"]


def test_glossary_prefers_the_longest_phrase() -> None:
    tokenize = Tokenizer({"on demand": "short", "video on demand": "vod"})
    assert tokenize("video on demand") == ["vod"]


def test_glossary_does_not_match_inside_words() -> None:
    assert Tokenizer({"hd": "high"})("HDR on HD") == ["hdr", "high"]


# --- Bm25Index -----------------------------------------------------------------


def index(**docs: str) -> Bm25Index:
    return Bm25Index({key: text.split() for key, text in docs.items()})


def test_only_documents_sharing_a_term_are_returned() -> None:
    idx = index(a="red apple", b="green pear", c="red car")
    assert {key for key, _ in idx.top_k(["red"], k=10)} == {"a", "c"}


def test_rare_terms_weigh_more_than_common_ones() -> None:
    idx = index(a="common rare", b="common", c="common", d="common other")
    scores = dict(idx.top_k(["common", "rare"], k=10))
    assert scores["a"] > scores["b"]
    assert scores["a"] - scores["b"] > scores["b"]


def test_shorter_documents_score_higher_for_the_same_match() -> None:
    idx = index(short="apple pie", long="apple pie with cream and extra sugar")
    ranked = idx.top_k(["apple"], k=2)
    assert [key for key, _ in ranked] == ["short", "long"]


def test_top_k_is_sorted_limited_and_breaks_ties_by_insertion_order() -> None:
    idx = index(b="x", a="x", c="x y", d="z")
    ranked = idx.top_k(["x"], k=2)
    assert [key for key, _ in ranked] == ["b", "a"]
    assert ranked[0][1] >= ranked[1][1]


def test_scores_are_positive_even_for_terms_in_most_documents() -> None:
    idx = index(a="x", b="x", c="x")
    assert all(score > 0 for _, score in idx.top_k(["x"], k=3))


@pytest.mark.parametrize("query", [[], ["missing"]])
def test_queries_without_matches_return_nothing(query: list[str]) -> None:
    assert index(a="x").top_k(query, k=5) == []


def test_empty_index_returns_nothing() -> None:
    assert Bm25Index({}).top_k(["x"], k=5) == []


def test_k_must_be_positive() -> None:
    with pytest.raises(ValueError, match="k"):
        index(a="x").top_k(["x"], k=0)


# --- the ott_web data ----------------------------------------------------------


@pytest.mark.parametrize(
    ("requirement_id", "case_id"),
    [
        ("US-12.AC1", "TC-048"),  # FairPlay on Safari
        ("US-07.AC1", "TC-028"),  # turn on subtitles, choose a language
        ("US-05.AC4", "TC-022"),  # fullscreen with button and Escape
    ],
)
def test_ott_obvious_pairs_rank_first(requirement_id: str, case_id: str) -> None:
    pack = load_pack(ROOT / "domains" / "ott_web" / "pack.yaml")
    data = ROOT / "data" / "ott_web"
    reqs = {r.id: r for r in MarkdownSpecAdapter().read(data / "user_stories.md", pack)}
    cases = XlsxSuiteAdapter().read(data / "test_cases.xlsx", pack)
    tokenize = Tokenizer(pack.glossary)
    idx = Bm25Index(
        {c.id: tokenize(f"{c.title} {c.steps} {c.expected_result}") for c in cases}
    )
    [(best, _)] = idx.top_k(tokenize(reqs[requirement_id].text), k=1)
    assert best == case_id
