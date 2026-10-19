"""Tests for the evaluation script's splitting, metrics and exit codes."""

from dataclasses import dataclass

import pytest

from app.repositories.evaluation_repository import EvaluationCase
from scripts import evaluate as ev
from app.services.matching_service import Match, MatchResult, MatchStatus
from app.repositories.faq_repository import Faq


def make_cases(n):
    return [EvaluationCase(f"T{i}", f"q{i}", 1) for i in range(n)]


class TestSplit:
    def test_dev_and_test_are_disjoint_and_cover_everything(self):
        cases = make_cases(11)
        dev, test = ev.split_cases(cases, "dev"), ev.split_cases(cases, "test")
        assert not {c.id for c in dev} & {c.id for c in test}
        assert {c.id for c in dev} | {c.id for c in test} == {c.id for c in cases}

    def test_all_returns_every_case_and_split_is_deterministic(self):
        cases = make_cases(7)
        assert ev.split_cases(cases, "all") == cases
        assert ev.split_cases(cases, "dev") == ev.split_cases(cases, "dev")


@dataclass
class StubMatcher:
    """Returns scripted results keyed by question."""

    results: dict

    def match(self, text):
        return self.results[text]

    def rank(self, text, k=None):
        result = self.results[text]
        matches = [result.best] if result.best else list(result.suggestions)
        return matches[:k]


def faq(i):
    return Faq(i, f"Q{i}", f"A{i}")


class TestMetrics:
    def test_outcomes_are_classified_and_scored(self):
        cases = [
            EvaluationCase("A", "right", 1),  # answered correctly      +1
            EvaluationCase("B", "wrong", 1),  # answered wrongly        -1
            EvaluationCase("C", "suggest-hit", 1),  # suggestion hit    +0.5
            EvaluationCase("D", "fallback", 1),  # fallback            0
            EvaluationCase("E", "oos-fallback", None),  # fallback     +1
            EvaluationCase("F", "oos-answered", None),  # wrong answer -1
        ]
        results = {
            "right": MatchResult(MatchStatus.ANSWER, best=Match(faq(1), 0.9)),
            "wrong": MatchResult(MatchStatus.ANSWER, best=Match(faq(2), 0.9)),
            "suggest-hit": MatchResult(
                MatchStatus.SUGGESTIONS, suggestions=(Match(faq(1), 0.5),)
            ),
            "fallback": MatchResult(MatchStatus.FALLBACK),
            "oos-fallback": MatchResult(MatchStatus.FALLBACK),
            "oos-answered": MatchResult(MatchStatus.ANSWER, best=Match(faq(3), 0.8)),
        }
        report = ev.evaluate(StubMatcher(results), cases)

        assert (report.in_scope, report.out_of_scope) == (4, 2)
        assert report.answered_correct == 1 and report.answered_wrong == 1
        assert report.suggested_with_hit == 1 and report.fell_back == 1
        assert report.oos_fell_back == 1 and report.oos_answered == 1
        assert report.top1_correct == 2  # right + suggest-hit rank the FAQ first
        assert report.utility == pytest.approx((1 - 1 + 0.5 + 0 + 1 - 1) / 6)
        assert len(report.failures) == 4  # wrong, suggest-hit, fallback, oos-answered


class TestCommandLine:
    def test_runs_on_shipped_data_and_prints_a_report(self, capsys):
        assert ev.main(["--split", "all"]) == 0
        output = capsys.readouterr().out
        assert "Top-1 ranking accuracy" in output and "Utility score" in output

    def test_exits_nonzero_below_the_required_accuracy(self, capsys):
        assert ev.main(["--min-top1", "0.999"]) == 1
        assert "below the required" in capsys.readouterr().err

    def test_regression_floor_holds_on_shipped_data(self):
        assert ev.main(["--min-top1", "0.65"]) == 0
