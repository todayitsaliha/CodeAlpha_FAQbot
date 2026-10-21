"""Measure chatbot accuracy against the held-out evaluation set.

Usage (from backend/):
    python -m scripts.evaluate                    # all cases
    python -m scripts.evaluate --split test       # report on the untouched half
    python -m scripts.evaluate --verbose          # list every failure
    python -m scripts.evaluate --min-top1 0.80    # exit 1 below the STS target

Cases are split deterministically (even positions = dev, odd = test). Tune
thresholds on `dev`, then report final accuracy on `test`.
"""

import argparse
import sys
from dataclasses import dataclass, field

from app import config
from app.repositories.evaluation_repository import EvaluationCase, EvaluationRepository
from app.repositories.faq_repository import FaqRepository
from app.services.matching_service import MatchingService, MatchStatus
from app.services.preprocessing_service import PreprocessingService
from app.services.semantic_service import SemanticModel


def split_cases(cases: list[EvaluationCase], split: str) -> list[EvaluationCase]:
    if split == "dev":
        return cases[0::2]
    if split == "test":
        return cases[1::2]
    return list(cases)


@dataclass
class EvaluationReport:
    in_scope: int = 0
    top1_correct: int = 0
    top3_correct: int = 0
    answered_correct: int = 0
    answered_wrong: int = 0
    suggested_with_hit: int = 0
    suggested_without_hit: int = 0
    fell_back: int = 0
    out_of_scope: int = 0
    oos_fell_back: int = 0
    oos_suggested: int = 0
    oos_answered: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.in_scope + self.out_of_scope

    @property
    def top1_accuracy(self) -> float:
        return self.top1_correct / self.in_scope if self.in_scope else 0.0

    @property
    def utility(self) -> float:
        """Per-case score in [-1, 1] that penalises wrong answers.

        +1 correct answer or correct fallback; +0.5 helpful suggestions (right FAQ
        listed, or suggestions for an out-of-scope question); -1 wrong answer;
        0 otherwise. Used to choose thresholds, because answering wrongly is worse
        than asking the user to rephrase.
        """
        score = (
            self.answered_correct
            + 0.5 * self.suggested_with_hit
            - self.answered_wrong
            + self.oos_fell_back
            + 0.5 * self.oos_suggested
            - self.oos_answered
        )
        return score / self.total if self.total else 0.0

    @property
    def overall_accuracy(self) -> float:
        """Share of cases with a good outcome: correct answer, or no wrong answer."""
        good = self.answered_correct + self.out_of_scope - self.oos_answered
        return good / self.total if self.total else 0.0


def evaluate(matcher: MatchingService, cases: list[EvaluationCase]) -> EvaluationReport:
    report = EvaluationReport()
    for case in cases:
        result = matcher.match(case.question)
        ranked = matcher.rank(case.question, k=3)
        top1 = ranked[0].faq.id if ranked else None

        if case.is_out_of_scope:
            report.out_of_scope += 1
            if result.status is MatchStatus.ANSWER:
                report.oos_answered += 1
                report.failures.append(
                    f"{case.id} OOS answered with FAQ {result.best.faq.id} "
                    f"({result.top_score:.2f}): {case.question!r}"
                )
            elif result.status is MatchStatus.SUGGESTIONS:
                report.oos_suggested += 1
            else:
                report.oos_fell_back += 1
            continue

        report.in_scope += 1
        report.top1_correct += top1 == case.expected_faq_id
        report.top3_correct += any(m.faq.id == case.expected_faq_id for m in ranked)
        if result.status is MatchStatus.ANSWER:
            if result.best.faq.id == case.expected_faq_id:
                report.answered_correct += 1
            else:
                report.answered_wrong += 1
                report.failures.append(
                    f"{case.id} wrong answer FAQ {result.best.faq.id} "
                    f"({result.top_score:.2f}), expected {case.expected_faq_id}: "
                    f"{case.question!r}"
                )
        elif result.status is MatchStatus.SUGGESTIONS:
            hit = any(m.faq.id == case.expected_faq_id for m in result.suggestions)
            report.suggested_with_hit += hit
            report.suggested_without_hit += not hit
            report.failures.append(
                f"{case.id} only suggestions ({result.top_score:.2f}), "
                f"expected {case.expected_faq_id}, "
                f"{'hit' if hit else 'miss'}: {case.question!r}"
            )
        else:
            report.fell_back += 1
            report.failures.append(
                f"{case.id} fallback ({result.top_score:.2f}), "
                f"expected {case.expected_faq_id}: {case.question!r}"
            )
    return report


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:6.1%} ({part}/{whole})" if whole else "   n/a"


def _row(label: str, part: int, whole: int) -> str:
    return f"    {label:<34}{_pct(part, whole)}"


def print_report(report: EvaluationReport, label: str, verbose: bool) -> None:
    n, m = report.in_scope, report.out_of_scope
    print(f"Evaluation [{label}]: {report.total} cases")
    print(f"  In-scope questions: {n}")
    print(_row("Top-1 ranking accuracy", report.top1_correct, n))
    print(_row("Top-3 ranking accuracy", report.top3_correct, n))
    print(_row("Answered correctly", report.answered_correct, n))
    print(_row("Answered wrongly", report.answered_wrong, n))
    print(_row("Suggestions, right FAQ listed", report.suggested_with_hit, n))
    print(_row("Suggestions, right FAQ absent", report.suggested_without_hit, n))
    print(_row("Fallback", report.fell_back, n))
    print(f"  Out-of-scope questions: {m}")
    print(_row("Correct fallback", report.oos_fell_back, m))
    print(_row("Suggestions shown", report.oos_suggested, m))
    print(_row("Wrongly answered", report.oos_answered, m))
    print(f"  Overall good-outcome rate: {report.overall_accuracy:.1%}")
    print(f"  Utility score (-1 to 1): {report.utility:+.3f}")
    if verbose and report.failures:
        print("\nNon-ideal outcomes:")
        for line in report.failures:
            print(f"  - {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--split", choices=("all", "dev", "test"), default="all")
    parser.add_argument(
        "--dataset",
        choices=("main", "final"),
        default="main",
        help="'final' is reserved for the last report (ignores --split)",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--no-semantic", action="store_true", help="TF-IDF only (skip word vectors)"
    )
    parser.add_argument(
        "--min-top1",
        type=float,
        default=None,
        help="exit with status 1 if in-scope top-1 accuracy is below this (0-1)",
    )
    args = parser.parse_args(argv)

    faqs = FaqRepository(config.FAQ_PATH).load()
    path = (
        config.FINAL_EVALUATION_PATH
        if args.dataset == "final"
        else config.EVALUATION_PATH
    )
    cases = EvaluationRepository(path, (f.id for f in faqs)).load()
    semantic = None if args.no_semantic else SemanticModel.load()
    matcher = MatchingService(faqs, PreprocessingService(), semantic=semantic)

    split = "all" if args.dataset == "final" else args.split
    report = evaluate(matcher, split_cases(cases, split))
    print_report(
        report, "final held-out" if args.dataset == "final" else split, args.verbose
    )

    if args.min_top1 is not None and report.top1_accuracy < args.min_top1:
        print(
            f"\nFAIL: top-1 accuracy {report.top1_accuracy:.1%} is below "
            f"the required {args.min_top1:.1%}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
