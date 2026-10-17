# Data files

| File | Purpose |
|---|---|
| `faqs.json` | FAQ knowledge base: the only source of answers the chatbot can return |
| `test_questions.json` | Held-out evaluation set used to measure accuracy |

## Provenance

Both files are **synthetic**. They describe a fictional online store ("ShopEase"); all
policies, prices, emails and phone numbers are invented. Nothing here is real customer
data. The schema follows STS sections 6.1 and 6.4, so a genuine client dataset can be
dropped in without code changes.

## Current size

- `faqs.json`: 80 FAQs across 9 categories, each with 4 alternate phrasings.
- `test_questions.json`: 144 cases: 80 held-out paraphrases of the FAQs, 34 noisy queries
  (typos, terse or informal wording) and 30 out-of-scope questions (15 general, 15 harder
  ones that are partly store-flavoured, e.g. "Are you hiring?").

## Rules for extending the data

1. **More phrasings help coverage, not "training".** TF-IDF is not trained; extra
   `alt_questions` widen the vocabulary each FAQ can match.
2. **Never copy an evaluation question into `alt_questions`** (or the reverse). The
   evaluation set must stay held out, or measured accuracy becomes meaningless.
   `python -m scripts.validate_data` and the test suite fail on any exact overlap.
3. **Tune on `faqs.json`, measure on `test_questions.json`.** If thresholds are tuned
   against the evaluation set, add fresh held-out cases before reporting final accuracy.
4. Keep every FAQ id covered by at least one evaluation case (enforced by tests).
5. Out-of-scope cases use `"expected_faq_id": "none"` and must receive the fallback.
