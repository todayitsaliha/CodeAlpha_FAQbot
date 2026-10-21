# Acceptance Criteria (baseline for sign-off)

Source: STS v1.0, re-baselined to a 2-week / 4-sprint delivery.

## Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | FAQ knowledge base in `faqs.json` with at least 50 pairs (synthetic ShopEase dataset, currently 80); fields: id, question, answer, category, alt_questions |
| FR-2 | One shared NLTK preprocessing pipeline (lowercase, clean, tokenize, stop-word removal keeping negations, lemmatize) used for FAQs and user input |
| FR-3 | TF-IDF (unigrams + bigrams) with cosine-similarity matching |
| FR-4 | Answer threshold and lower suggestion threshold; fallback with up to 3 suggested questions |
| FR-5 | Intent handling for greetings, thanks and goodbyes |
| FR-6 | `POST /api/chat`, `GET /api/health`, optional `GET /api/faqs/suggested`; response shape per STS section 6.3 |
| FR-7 | Input validation (1-500 chars), request logging, global error handler returning `{status, message, requestId}` |
| FR-8 | Evaluation script reporting top-1 accuracy and the misses/fallbacks |
| FR-9 | Browser chat UI (bubbles, typing indicator, suggested questions, ARIA live region) |

## Non-functional targets

- Top-1 accuracy of at least 80% on in-scope evaluation questions (confirmed with client).
  **Status:** met on FAQ-style questions (85% across the main set, 81% on its test half);
  not met on conversational questions (56% to 64% on two held-out sets); see `matching-engine.md`.
- Out-of-scope evaluation questions receive the fallback, not a wrong answer.
- Typical response time well under one second; startup within a few seconds.
- CI gates on every PR: flake8, Black, pytest (and the evaluation run from Sprint 2).

## Sprint exit criteria

| Sprint | Exit criteria |
|---|---|
| 1 | Repo, branching and CI live; validated synthetic `faqs.json` (>= 50 pairs) loads from the CLI; evaluation set committed; requirements signed off |
| 2 | CLI chatbot answers questions; preprocessing and matching unit tests pass; baseline accuracy report recorded |
| 3 | User asks a question in the browser and gets the best match from the live backend; API tests pass |
| 4 | Final accuracy report; client UAT sign-off; `v1.0.0` tagged on `main`; handover docs and deployment runbook |

## Out of scope

Generative AI answers, multi-turn memory, authentication, voice, non-English languages.
Stretch items (feedback buttons, embeddings, CSV import) are deferred to a post-release backlog.
