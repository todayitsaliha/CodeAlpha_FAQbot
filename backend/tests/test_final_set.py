"""The final held-out set must stay valid, complete and disjoint from other data."""

import pytest

from app import config
from app.repositories.evaluation_repository import (
    EvaluationRepository,
    find_leaked_cases,
    normalise_for_comparison,
)
from app.repositories.faq_repository import FaqRepository


@pytest.fixture(scope="module")
def faqs():
    return FaqRepository(config.FAQ_PATH).load()


PATHS = {"final": config.FINAL_EVALUATION_PATH, "final2": config.FINAL2_EVALUATION_PATH}


def load(name, faqs):
    return EvaluationRepository(PATHS[name], (f.id for f in faqs)).load()


@pytest.fixture(scope="module", params=sorted(PATHS))
def final(request, faqs):
    return load(request.param, faqs)


def test_covers_every_faq_and_includes_out_of_scope_cases(faqs, final):
    assert {f.id for f in faqs} <= {c.expected_faq_id for c in final}
    assert sum(c.is_out_of_scope for c in final) >= 15


def test_ids_are_unique(final):
    assert len({c.id for c in final}) == len(final)


def test_never_repeats_an_faq_phrasing(faqs, final):
    assert find_leaked_cases(final, faqs) == []


def test_is_disjoint_from_the_tuning_and_reporting_set(faqs, final):
    main = EvaluationRepository(config.EVALUATION_PATH, (f.id for f in faqs)).load()
    seen = {normalise_for_comparison(c.question) for c in main}
    assert [c.id for c in final if normalise_for_comparison(c.question) in seen] == []


def test_the_two_held_out_sets_do_not_overlap(faqs):
    first = {normalise_for_comparison(c.question) for c in load("final", faqs)}
    second = load("final2", faqs)
    assert [c.id for c in second if normalise_for_comparison(c.question) in first] == []


def test_first_set_is_written_in_a_conversational_style(faqs):
    in_scope = [c.question for c in load("final", faqs) if not c.is_out_of_scope]
    assert sum(len(q.split()) for q in in_scope) / len(in_scope) >= 10


def test_second_set_mixes_keywords_slang_and_long_stories(faqs):
    lengths = [
        len(c.question.split()) for c in load("final2", faqs) if not c.is_out_of_scope
    ]
    assert sum(n <= 4 for n in lengths) >= 15  # keyword-style queries
    assert sum(n >= 18 for n in lengths) >= 15  # long stories
