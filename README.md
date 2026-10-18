# CodeAlpha_FAQbot

A retrieval-based FAQ chatbot. User questions and stored FAQ questions are cleaned
with NLTK, vectorised with TF-IDF, and matched by cosine similarity. The answer of
the best-matching FAQ is returned; low-confidence questions get a polite fallback
with suggested questions. Every answer is a pre-approved FAQ answer (no generative AI).

Specification: *Software Technical Specification (STS) v1.0*, re-baselined to a
**2-week / 4-sprint** delivery (see `docs/sts-v1.1-changes.md`).

## Repository layout

```
backend/              Python application (3-tier: controllers / services / repositories)
  app/controllers/    HTTP layer (Sprint 3)
  app/services/       Preprocessing, intent, matching, chatbot (Sprint 2)
  app/repositories/   FAQ + evaluation data access and validation
  data/               faqs.json, test_questions.json
  scripts/            setup_nltk, validate_data, evaluate (Sprint 2), CLI client (Sprint 2)
  tests/              pytest suite
frontend/             Static chat UI (Sprint 3)
docs/                 Acceptance criteria, STS change log
```

## Getting started

Requires Python 3.10+.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m scripts.setup_nltk      # one-time NLTK data download
python -m scripts.validate_data   # validate FAQ + evaluation datasets
python -m scripts.preprocess_demo    # see the NLP pipeline stage by stage
pytest                            # run the test suite
flake8 . && black --check .       # lint and format checks (also enforced in CI)
```

## Branching strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code only; release tags (`v1.0.0`) |
| `develop` | Integration branch |
| `feature/backend/<name>`, `feature/frontend/<name>` | New work, branched from `develop` |
| `bugfix/backend/<name>`, `bugfix/frontend/<name>` | Fixes, branched from `develop` |

All work reaches `develop` through a pull request: CI green and at least one peer
review. See `.github/pull_request_template.md`.

## Sprint plan (10 working days)

| Sprint | Days | Focus | Status |
|---|---|---|---|
| 1 | 1-2 | Repo, CI, FAQ dataset, evaluation set | Done (pending GitHub setup) |
| 2 | 3-5 | NLP pipeline, matching engine, intents, evaluation script | In progress (preprocessing done) |
| 3 | 6-7 | Flask API, logging, error handling, chat UI | Planned |
| 4 | 8-10 | Tuning, UAT, handover, tag `v1.0.0` | Planned |

## Dataset note

The project uses a **synthetic dataset** for a fictional online store ("ShopEase"):
80 FAQs, 320 alternate phrasings and a separate 144-case evaluation set. See
`backend/data/README.md` for provenance and the rules for extending it. The schema is
identical to a real dataset, so swapping in genuine client FAQs later needs no code changes.
