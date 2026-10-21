# Matching Engine: Design, Tuning and Measured Results

Implementation: `backend/app/services/matching_service.py`, `semantic_service.py`
Commands (from `backend/`): `python -m scripts.evaluate [--split dev|test|all]
[--dataset final|final2] [--no-semantic] [--verbose]`,
`python -m scripts.tune_thresholds [--no-semantic] [--max-wrong N]`

## How it works

1. Every FAQ is indexed by all its phrasings: its question plus 7 alternates (560
   alternates in total): short rewordings, keyword fragments, and first-person
   "situation" sentences such as "The courier tried to deliver but I was not at home".
2. A user question is preprocessed (see `preprocessing.md`). Words that are not real
   English words but closely resemble an FAQ word are corrected (`cancle` -> `cancel`).
3. Three cosine similarities are computed against every phrasing; a FAQ keeps the score
   of its best phrasing: word TF-IDF (unigrams + bigrams), character TF-IDF (3-5 grams,
   typo tolerant) and word vectors (spaCy `en_core_web_md`, IDF-weighted averages with the
   corpus mean removed).
4. Score (default profile): `0.5 * (0.4 * word + 0.6 * char) + 0.5 * vectors`.
5. Decision: **answer** at score >= 0.65, **suggestions** (up to 3) from 0.45 to 0.65,
   otherwise **fallback**.

The word vectors are optional. Without spaCy or the model the matcher logs a warning and
uses the TF-IDF-only profile (word weight 0.4, answer >= 0.70, suggestions from 0.30).
Both profiles are in `config.py`. First start-up takes about 5 seconds.

## Evaluation protocol

| Set | Cases | Role | Status |
|---|---|---|---|
| main, dev half | 72 | Tuning weights and thresholds | Tuned on |
| main, test half | 72 | Reporting, FAQ-style wording | Viewed repeatedly |
| held-out set 1 (`final`) | 100 | Conversational questions, written before the new phrasings | Viewed twice |
| held-out set 2 (`final2`) | 100 | Mixed styles: keywords, typos and slang, long stories; 20 lookalike out-of-scope questions | Viewed after a safety-driven setting change |

Settings were chosen by grid search on dev only, maximising a utility score (+1 correct
answer or correct fallback, +0.5 helpful suggestions, -1 wrong answer), at the centre of
the best plateau. A **safety constraint** (at most 2 wrong answers on dev) was added after
the first attempt answered too many out-of-scope questions. That change was made after
seeing held-out set 2, so both held-out sets are validation figures, not pristine tests.
A third fresh set would be needed for an unbiased final number.

## Results (default profile with word vectors; TF-IDF-only in brackets)

| | Main, all | Main, test half | Held-out 1 | Held-out 2 |
|---|---|---|---|---|
| In-scope / out-of-scope | 114 / 30 | 57 / 15 | 80 / 20 | 80 / 20 |
| **Top-1** | **85.1%** (80.7%) | **80.7%** (73.7%) | 56.2% (61.3%) | **63.7%** (65.0%) |
| Top-3 | 95.6% (93.9%) | 93.0% (89.5%) | 72.5% (78.8%) | 77.5% (83.8%) |
| Answered directly, correct | 56.1% (39.5%) | 52.6% (35.1%) | 15.0% (8.8%) | 31.2% (22.5%) |
| Answered directly, wrong | 2.6% (0.9%) | 3.5% (0.0%) | 0.0% (1.2%) | 5.0% (2.5%) |
| Out-of-scope answered | 1 of 30 (0) | 0 of 15 (0) | 1 of 20 (2) | 5 of 20 (5) |
| Utility (-1 to 1) | +0.701 (+0.649) | +0.660 (+0.611) | +0.385 (+0.390) | +0.410 (+0.410) |

For reference, before the conversational phrasings, top-1 on held-out set 1 was 37.5%
(40.0% TF-IDF-only), so the new phrasings added roughly 19 to 24 points on conversational
questions.

## Interpretation

- **The 80% top-1 target is met on FAQ-style wording (85% on the main set, 81% on its
  test half) but not on conversational input (56% to 64%).**
- **Conversational phrasings were the biggest lever** (about +20 points on conversational
  questions). Word vectors add 5 to 7 points on FAQ-style questions and roughly double
  the share of questions answered directly, but give no top-1 gain on conversational
  ones (slightly lower: 56.2% vs 61.3% and 63.7% vs 65.0%).
- **Known weakness: lookalike out-of-scope questions.** Questions about other services
  that share FAQ vocabulary ("forgot my Netflix password", "delete my Instagram
  account") are sometimes answered: 5 of 20 on held-out set 2. The bot does not know
  what it does not know; it only measures similarity to FAQs.
- **Behaviour is otherwise safe.** In-scope wrong answers are 0% to 5%; for conversational
  messages the bot more often offers suggestions than a direct answer.

## What would move the number next

| Option | Expected effect | Cost |
|---|---|---|
| Distractor entries: add FAQ-like entries for common other-service topics (streaming, social media, other retailers, airlines) whose match triggers the fallback | Targets the lookalike weakness directly | Small writing effort; needs a third fresh set to measure |
| Sentence embeddings (e.g. all-MiniLM via `sentence-transformers`) | Better semantic matching on long text | Needs Hugging Face access, untested in the build environment; ~90 MB dependency |
| Redefine acceptance as top-3 or "resolved in one click" | Matches how the UI behaves (top-3: 78% to 96%) | Needs client agreement |
| Ship with documented limits | None | Target met only for FAQ-style input |

## Regression protection

CI floors (regression guards, not targets): top-1 >= 0.78 on the main set, >= 0.50 on
held-out set 1, >= 0.55 on held-out set 2. Tests also bound the share of out-of-scope
questions answered (5% main, 10% set 1, 30% set 2) and the precision of answered
questions (93%, 90%, 70%).
