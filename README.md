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
  app/controllers/    HTTP layer: routes, error handling, request hooks
  app/services/       Preprocessing, synonyms, intents, matching, chatbot service
  app/repositories/   FAQ + evaluation data access and validation
  data/               faqs.json, test_questions.json
  scripts/            setup_nltk, validate_data, evaluate, tune_thresholds, chat_cli
  tests/              pytest suite
frontend/             Static chat UI (served by the Flask app at /)
docs/                 Acceptance criteria, STS change log, design notes (preprocessing, matching, chatbot service, API, UI)
```

## Getting started

Python 3.10+ is required. This is a **Python** project: use `pip`, not `npm`.
`pip install` also downloads spaCy and its ~33 MB English model (word vectors), and the
first start-up takes a few seconds while they load.

**Linux / macOS**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m scripts.setup_nltk          # one-time NLTK data download
```

**Windows (PowerShell)**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements-dev.txt
python -m scripts.setup_nltk          # one-time NLTK data download
```

Then, in either shell (from `backend/`):

```
python run.py                             # start the chatbot + UI at http://127.0.0.1:5000
python -m scripts.chat_cli                # talk to the chatbot in the terminal
python -m scripts.chat_cli --ask "Do you ship abroad?" --debug
python -m scripts.validate_data           # validate FAQ + evaluation datasets
python -m scripts.preprocess_demo         # see the NLP pipeline stage by stage
python -m scripts.evaluate --verbose      # measure accuracy on the evaluation set
pytest                                    # run the test suite
flake8 . && black --check .               # lint and format checks (also enforced in CI)
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
| 2 | 3-5 | NLP pipeline, matching engine, intents, evaluation script, CLI client | Done; 80% accuracy target still open (see `docs/matching-engine.md`) |
| 3 | 6-7 | Flask API, logging, error handling, chat UI | Done; UI awaiting visual review in a browser |
| 4 | 8-10 | Tuning, UAT, handover, tag `v1.0.0` | In progress (word vectors and final held-out set done; accuracy target still open) |

## Dataset note

The project uses a **synthetic dataset** for a fictional online store ("ShopEase"):
80 FAQs, 320 alternate phrasings and a separate 144-case evaluation set. See
`backend/data/README.md` for provenance and the rules for extending it. The schema is
identical to a real dataset, so swapping in genuine client FAQs later needs no code changes.
