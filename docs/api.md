# HTTP API

Implementation: `backend/app/controllers/` (HTTP only), `backend/app/factory.py`,
`backend/run.py`. All behaviour lives in `ChatbotService`; controllers only route,
validate and shape responses.

## Running

```
cd backend
python run.py                  # production server (waitress), http://127.0.0.1:5000
python run.py --dev            # Flask development server
python run.py --port 8000      # or set FAQBOT_HOST / FAQBOT_PORT
```

If `frontend/index.html` exists it is served at `/`, on the same origin as the API.
The server refuses to start (exit code 1, clear message) if the FAQ file is missing or
invalid, or if the NLTK data has not been downloaded.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/chat` | Ask a question |
| GET | `/api/faqs/suggested?limit=4` | Welcome message and example questions (limit 1-8) |
| GET | `/api/health` | `{"status": "ok", "faqCount": 80}` when ready |

### POST /api/chat

Request: `{"message": "How long will my order take to arrive?"}` (1 to 500 characters).

Response (200), always these five fields:

```json
{
  "answer": "I'm not sure I understood. Did you mean one of these?",
  "matchedQuestion": null,
  "confidence": 0.61,
  "fallback": true,
  "suggestions": ["How long does delivery take?", "How long do refunds take?"]
}
```

A low-confidence or out-of-scope question is a normal 200 reply with `fallback: true`,
not an error. See `chatbot-service.md` for how each case maps to the fields.

### GET /api/faqs/suggested

`{"welcome": "Hello! I can answer questions about ...", "suggestions": ["...", "..."]}`
(one question per category). Used by the UI for the welcome bubble and chips.

## Errors

Every error has the same shape and the request id is also sent in `X-Request-ID`:

```json
{"status": 400, "message": "Message must be between 1 and 500 characters.", "requestId": "b7c1e0a2-..."}
```

| Status | When |
|---|---|
| 400 | Missing, empty, non-string or over-length `message`; body is not a JSON object; bad `limit` |
| 404 / 405 | Unknown route / wrong method (405 includes an `Allow` header) |
| 413 | Request body larger than 8 KB |
| 500 | Unexpected error: generic message to the client, full stack trace in the log |
| 503 | FAQ data or NLTK data not loaded: health and chat report it, details go to the log only |

## Trying it from the command line

Linux / macOS:
```
curl -X POST http://127.0.0.1:5000/api/chat -H "Content-Type: application/json" \
     -d '{"message": "do u ship abroad"}'
```
Windows PowerShell:
```
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/chat `
  -ContentType "application/json" -Body '{"message": "do u ship abroad"}'
```

## Security and privacy (STS section 8.3)

- **CORS:** no cross-origin permission is ever granted; the UI is served from the same origin.
- **HTTPS:** terminate TLS at a reverse proxy (nginx, a cloud load balancer) in
  deployment; the app itself speaks plain HTTP on the proxy's private side.
- **Headers:** `Content-Security-Policy: default-src 'self'` (so the UI must use no
  inline scripts or styles and no CDNs), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on API responses.
- **No conversation storage.** Logs hold only the first 120 characters of a question,
  with emails and long digit runs (phones, card and order numbers) masked.
- **Log forging:** paths and questions are logged with `%r`, which escapes newlines.
- **Input limits:** message capped at 500 characters, body at 8 KB; all input is treated
  as text and never executed.

## Logging

Each request: method, path (no query string), status, duration, request id. Each chat
request additionally: matched FAQ id, confidence and fallback flag. Unhandled errors are
logged at ERROR level with stack traces.
