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


@pytest.fixture(scope="module")
def final(faqs):
    return EvaluationRepository(
        config.FINAL_EVALUATION_PATH, (f.id for f in faqs)
    ).load()


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


def test_written_in_a_conversational_style(final):
    """Guards the purpose of the set: noticeably longer than FAQ-style questions."""
    in_scope = [c.question for c in final if not c.is_out_of_scope]
    assert sum(len(q.split()) for q in in_scope) / len(in_scope) >= 10
