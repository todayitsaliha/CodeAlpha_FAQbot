"""Grid-search the matching settings on the dev split.

Usage (from backend/):
    python -m scripts.tune_thresholds                 # search on dev, show top 5
    python -m scripts.tune_thresholds --report-test   # also score the best on test

Run --report-test sparingly: every look at the test split that influences a decision
weakens it as an unbiased estimate. Objective on dev: highest utility score (wrong
answers are penalised, see EvaluationReport.utility), then fewest wrong answers.
"""

import argparse
import itertools
import sys

from app import config
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.faq_repository import FaqRepository
from app.services.matching_service import MatchingService, MatchingSettings
from app.services.preprocessing_service import PreprocessingService
from app.services.semantic_service import SemanticModel
from scripts.evaluate import evaluate, split_cases

WEIGHTS = (0.2, 0.4, 0.6)
SEMANTIC_WEIGHTS = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
ANSWER_THRESHOLDS = tuple(round(0.30 + 0.05 * i, 2) for i in range(11))
SUGGESTION_THRESHOLDS = tuple(round(0.10 + 0.05 * i, 2) for i in range(9))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--report-test", action="store_true")
    args = parser.parse_args(argv)

    faqs = FaqRepository(config.FAQ_PATH).load()
    cases = EvaluationRepository(config.EVALUATION_PATH, (f.id for f in faqs)).load()
    dev, test = split_cases(cases, "dev"), split_cases(cases, "test")
    semantic = SemanticModel.load()
    base = MatchingService(faqs, PreprocessingService(), semantic=semantic)

    results = []
    for weight, sem, answer, suggest in itertools.product(
        WEIGHTS, SEMANTIC_WEIGHTS, ANSWER_THRESHOLDS, SUGGESTION_THRESHOLDS
    ):
        if suggest > answer or (semantic is None and sem > 0):
            continue
        settings = MatchingSettings(answer, suggest, weight, semantic_weight=sem)
        report = evaluate(base.with_settings(settings), dev)
        wrong = report.answered_wrong + report.oos_answered
        results.append(
            (
                round(report.utility, 6),
                -wrong,
                report.answered_correct,
                settings,
                report,
            )
        )
    results.sort(key=lambda r: r[:3], reverse=True)

    print("Top 5 settings on dev:")
    for utility, neg_wrong, correct, s, report in results[:5]:
        print(
            f"  utility={utility:+.3f} wrong={-neg_wrong} correct={correct} "
            f"top1={report.top1_accuracy:.1%} | word={s.word_weight} "
            f"semantic={s.semantic_weight} "
            f"answer={s.answer_threshold} suggest={s.suggestion_threshold}"
        )

    if args.report_test:
        best = results[0][3]
        report = evaluate(base.with_settings(best), test)
        print(
            f"\nBest settings on TEST: utility={report.utility:+.3f} "
            f"top1={report.top1_accuracy:.1%} "
            f"wrong={report.answered_wrong + report.oos_answered}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
