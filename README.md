# CodeAlpha FAQ Bot

CodeAlpha FAQ Bot is a small question-and-answer app for a fictional online store
called ShopEase. Ask a question in the web chat or terminal, and the bot compares it
with its FAQ list to find a likely answer. It returns a prepared FAQ answer when the
match is strong, suggests related questions when it is unsure, and uses a fallback
when it cannot find a good match. It does not generate answers with an AI model.

## How it works

1. The bot cleans and normalizes the question.
2. It compares the question with FAQ questions and their alternate phrasings using
   text similarity. Word-vector similarity is also used when its spaCy model is
   available.
3. It returns the matching FAQ answer, suggestions, or a fallback message.

The project includes a Python/Flask backend, a browser-based chat page, a command-line
chat client, and scripts and tests for checking the FAQ data and matching quality.
The browser page is served by the Flask app; no separate frontend server is needed.

## Requirements

- Python 3.10 or 3.12
- Internet access for installing Python dependencies and downloading NLTK data

## Run the app

Open a terminal in the project folder, then create and activate a virtual environment
inside `backend`.

**Windows PowerShell**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this command in the same terminal and activate
again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**macOS / Linux**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

Then, from `backend/` in either shell, install the dependencies, download the required
NLTK data, and start the app:

```bash
python -m pip install -r requirements-dev.txt
python -m scripts.setup_nltk
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) to use the chat page. The server
uses Waitress by default. To use Flask's development server instead, run
`python run.py --dev`.

The default host and port can be changed with command-line options or environment
variables:

```bash
python run.py --host 127.0.0.1 --port 8000
```

The equivalent environment variables are `FAQBOT_HOST` and `FAQBOT_PORT`.

## Try the command-line chat

Run these commands from `backend/` with the virtual environment activated:

```bash
python -m scripts.chat_cli
python -m scripts.chat_cli --ask "Do you ship abroad?"
python -m scripts.chat_cli --ask "Do you ship abroad?" --debug
```

In interactive mode, type `quit` to exit. Debug mode includes matching details such as
the confidence score.

## API

The Flask app provides these endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Get an answer for a question |
| `GET` | `/api/faqs/suggested?limit=4` | Get a welcome message and example questions |
| `GET` | `/api/health` | Check service status and FAQ count |

Send a chat question as JSON:

```json
{"message": "Do you ship abroad?"}
```

The response includes an `answer`, a confidence score, whether the bot used a fallback,
an optional matched FAQ question, and suggested questions.

## Data and project layout

```text
backend/
  app/                 Flask API, FAQ data access, and chatbot logic
  data/                FAQ and evaluation question datasets
  scripts/             Setup, command-line chat, validation, and evaluation tools
  tests/               Backend and frontend tests
  run.py               Starts the web app
frontend/              Browser chat page, styles, and JavaScript
.github/workflows/     Continuous integration checks
```

The FAQ data describes a fictional store and contains synthetic information, not real
customer data. The FAQ list is the source of the bot's store-related answers. See
[backend/data/README.md](backend/data/README.md) for dataset details and guidance on
changing the data.

## Check the project

Run these commands from `backend/`:

```bash
python -m scripts.validate_data
python -m scripts.evaluate --verbose
pytest
flake8 .
black --check .
```

`validate_data` checks the FAQ and evaluation datasets. `evaluate` measures the
matching quality on held-out questions. The test suite and lint/format checks are also
run in the GitHub Actions workflow.
