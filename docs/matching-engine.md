# Matching Engine: Design, Tuning and Measured Results

Implementation: `backend/app/services/matching_service.py`, `semantic_service.py`
Commands (from `backend/`): `python -m scripts.evaluate [--split dev|test|all]
[--dataset final] [--no-semantic] [--verbose]`, `python -m scripts.tune_thresholds`

## How it works

1. Every FAQ is indexed by all its phrasings (question + alternates).
2. A user question is preprocessed (see `preprocessing.md`). Words that are not real
   English words but closely resemble an FAQ word are corrected (`cancle` -> `cancel`).
3. Three cosine similarities are computed against every phrasing; a FAQ keeps the score
   of its best phrasing:
   - **word TF-IDF**, unigrams + bigrams (shared vocabulary, short phrases)
   - **character TF-IDF**, 3-5 grams (tolerant of typos)
   - **word vectors** (spaCy `en_core_web_md`): IDF-weighted average vectors with the
     corpus mean removed. Bridges words TF-IDF cannot, e.g. "nations" and "international".
4. Final score: `(1 - 0.4) * (0.2 * word + 0.8 * char) + 0.4 * semantic`.
5. Decision on the best score:

| Best score | Result |
|---|---|
| >= 0.70 | **Answer** with that FAQ |
| 0.40 to 0.70 | **Suggestions**: up to 3 similar FAQs |
| < 0.40 or no overlap | **Fallback** |

The word vectors are optional. If spaCy or the model is missing, the matcher logs a
warning and uses a TF-IDF-only profile with its own tuned thresholds (`config.py`).
Installing `requirements.txt` provides both; first start-up takes about 5 seconds.

## Evaluation protocol

| Set | File | Used for |
|---|---|---|
| dev (even positions of the main set) | `test_questions.json` | Tuning weights and thresholds |
| test (odd positions) | `test_questions.json` | Reporting; viewed several times, so a validation figure |
| **final held-out** | `final_questions.json` | Written *after* tuning, in a conversational style; run only to report, never to tune |

Settings were chosen by grid search on dev with a utility score that penalises wrong
answers (+1 correct answer or correct fallback, +0.5 helpful suggestions, -1 wrong
answer), taking the centre of the best plateau rather than the single best cell.

## Results

| | Main set, all | Main test split | **Final held-out** |
|---|---|---|---|
| Style of questions | Short, close to FAQ wording | same | Long, conversational, indirect |
| In-scope / out-of-scope | 114 / 30 | 57 / 15 | 80 / 20 |
| **Top-1, TF-IDF only** | 71.9% | 61.4% | **40.0%** |
| **Top-1, with word vectors** | **78.1%** | **71.9%** | **37.5%** |
| Top-3, TF-IDF only | 91.2% | 86.0% | 66.2% |
| Top-3, with word vectors | 93.0% | 89.5% | 62.5% |
| Answered directly and correctly | 39.5% | 33.3% | 5.0% |
| Wrong answers (in + out of scope) | 1 of 144 | 0 of 72 | **0 of 100** |
| Utility, TF-IDF only / with vectors | +0.604 / +0.653 | +0.535 / +0.590 | +0.315 / +0.335 |

## Interpretation

- **The STS target (top-1 >= 80%) is not met.** Best held-out results: 72% on questions
  worded like the FAQs, **about 38% on conversational questions**.
- **Word vectors help only part of the problem.** They add about 6 to 10 points of top-1
  on FAQ-style questions and remove wrong answers on the final set, but give no gain on
  long conversational questions (37.5% vs 40.0% without them, within noise for 80 cases).
- **The earlier 61% figure was optimistic.** My first test questions were written close
  to the FAQ phrasings. The fresh conversational set is the better guide to real users.
- **The main weakness is style, not vocabulary.** Real messages are long, indirect and
  describe a situation ("the mug was in pieces when I opened the box"); the FAQ phrasings
  are short and generic. Averaged word vectors cannot bridge that.
- **Behaviour is safe, not yet satisfying.** Out-of-scope questions were never answered
  (0 of 50 across both sets) and wrong answers are rare, but the bot answers directly in
  only 5% of conversational cases and otherwise offers suggestions or falls back.

## What would move the number (decision needed)

| Option | Expected effect | Cost |
|---|---|---|
| B2. Add conversational, situation-style phrasings to each FAQ (e.g. "the item arrived broken", "my order never showed up") | Most direct fix: closes the style gap | Writing effort; needs one more fresh held-out set to measure honestly |
| A2. Sentence embeddings (e.g. all-MiniLM, ~90 MB via `sentence-transformers`) | Best semantic matching on long text | Needs Hugging Face access, which could not be tested in the build environment; new dependency |
| D. Redefine acceptance as top-3 or "resolved with one click" | Honest for the UI; top-3 is 93% (FAQ-style) / 63% (conversational) | Needs client agreement; weak on conversational input |
| E. Accept and document the limits | None | Target stays unmet |

## Regression protection

CI runs two floors, not targets: `--min-top1 0.70` on the main set (currently 78.1%) and
`--dataset final --min-top1 0.30` (currently 37.5%). Tests also enforce that out-of-scope
questions are never answered and that at least 95% of answered questions are correct, on
both the main and final sets.
