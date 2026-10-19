# Matching Engine: Design, Tuning and Measured Results

Implementation: `backend/app/services/matching_service.py`
Commands (from `backend/`): `python -m scripts.evaluate [--split dev|test|all] [--verbose]`,
`python -m scripts.tune_thresholds`

## How it works

1. Every FAQ is indexed by all its phrasings (question + alternates).
2. A user question is preprocessed (see `preprocessing.md`). Words that are not real
   English words but closely resemble an FAQ word are corrected (`cancle` -> `cancel`).
   Real words are never touched.
3. Two cosine similarities are computed against every phrasing, and a FAQ keeps the
   score of its best phrasing:
   - word TF-IDF, unigrams + bigrams (shared vocabulary and short phrases)
   - character TF-IDF, 3-5 grams (tolerant of typos)
4. Scores are blended: `0.4 * word + 0.6 * char`.
5. Decision on the best blended score:

| Best score | Result |
|---|---|
| >= 0.70 | **Answer** with that FAQ |
| 0.35 to 0.70 | **Suggestions**: up to 3 similar FAQs |
| < 0.35 or no overlap | **Fallback** |

## Evaluation protocol

The 144 evaluation cases are split deterministically: even positions = **dev**
(tuning), odd positions = **test** (reporting). Thresholds and the blend weight were
chosen by grid search on dev only, using a utility score that penalises wrong answers
(wrong answer -1, correct answer or correct fallback +1, helpful suggestions +0.5).
Settings are the centre of the best-scoring plateau, not the single argmax.

## Results (final settings)

| | Dev (tuned on) | Test | All |
|---|---|---|---|
| Cases (in-scope / out-of-scope) | 57 / 15 | 57 / 15 | 114 / 30 |
| **Top-1 ranking accuracy** | 82.5% | **61.4%** | 71.9% |
| Top-3 ranking accuracy | 96.5% | 86.0% | 91.2% |
| Answered directly and correctly | 40.4% | 26.3% | 33.3% |
| Answered directly and wrongly | 1.8% | 0.0% | 0.9% |
| Right FAQ offered as a suggestion | 50.9% | 47.4% | 49.1% |
| Out-of-scope wrongly answered | 0 / 15 | 0 / 15 | **0 / 30** |
| Utility score (-1 to 1) | +0.674 | +0.535 | +0.604 |

Caveat: the test split was inspected more than once while building this task (baseline
and final aggregate numbers; no individual test failures were read or used). Treat it as
a validation figure, not a pristine one.

## Interpretation

- **The STS target (top-1 >= 80%) is met on dev only, not on held-out data.** The honest
  held-out figure is about 61% top-1 (86% top-3).
- **Why dev overstates quality.** The synonym map was written after reading dev failures,
  so it fixed the vocabulary gaps seen there ("erase", "showroom", "university") but not
  the different gaps in unseen paraphrases. Measured on test: a-priori baseline 61.4%
  top-1 before synonyms and typo correction, 61.4% after. They are principled but have
  not been shown to generalise.
- **The failure mode is vocabulary mismatch.** TF-IDF only rewards shared words. Where a
  user says something the FAQ phrasings never say, ranking degrades. More rules cannot
  fix this; semantic similarity can.
- **Behaviour is safe, not yet satisfying.** The engine almost never answers wrongly
  (1 of 114 in-scope, 0 of 30 out-of-scope), but it answers directly only about a third
  of the time and otherwise shows suggestions. The right FAQ is in the top 3 for 91% of
  in-scope questions, so suggestions usually rescue the user in one click.

## Options to close the gap (decision needed)

| Option | Expected effect | Cost |
|---|---|---|
| A. Add pre-trained word vectors (e.g. spaCy `en_core_web_md`, ~45 MB) as a third similarity signal | Largest: bridges synonyms and paraphrases | New dependency; STS lists embeddings as a deferred stretch item |
| B. More and more varied alternate phrasings per FAQ | Moderate; cheap | Author bias: risk of fitting our own writing style |
| C. Fresh held-out evaluation set written after tuning | Gives an unbiased final figure | Effort only |
| D. Redefine the acceptance metric (e.g. top-3 or "resolved with at most one click") | Reflects how the UI behaves | Needs client agreement |

## Regression protection

CI runs `python -m scripts.evaluate --min-top1 0.65` on the full set. This is a
**regression floor**, not the 80% target. Tests also enforce that out-of-scope
questions are never answered and that at least 95% of answered questions are correct.
