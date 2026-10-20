# Chatbot Service and CLI Client

Implementation: `backend/app/services/chatbot_service.py`,
`backend/app/services/intent_service.py`, `backend/scripts/chat_cli.py`

`ChatbotService.ask(message)` is the single entry point. The Flask API (Sprint 3) and
the CLI both call it, so behaviour is identical everywhere.

## Request flow (STS section 3.2)

1. **Validate**: a string of 1 to 500 characters after trimming, otherwise
   `InvalidMessageError("Message must be between 1 and 500 characters.")`. The API layer
   will turn this into the HTTP 400 error response.
2. **Intent check**: greetings, thanks and goodbyes return a canned reply and stop.
3. **Match**: preprocessing, typo correction, TF-IDF cosine scoring (see `matching-engine.md`).
4. **Decide and shape the response**, as below.

## Response mapping (STS section 6.3)

| Situation | `answer` | `matchedQuestion` | `confidence` | `fallback` | `suggestions` |
|---|---|---|---|---|---|
| Confident match | FAQ answer | FAQ question | score (2 d.p.) | `false` | `[]` |
| Medium confidence | "I'm not sure I understood. Did you mean one of these?" | `null` | best score | `true` | up to 3 FAQ questions |
| No match / out of scope | Polite fallback naming the topics the bot covers | `null` | best score | `true` | `[]` |
| Small talk | Canned reply | `null` | `1.0` | `false` | `[]` |

Small talk reports confidence 1.0 because it is recognised exactly rather than scored; a
UI that labels low-confidence replies as "uncertain" therefore never mislabels a greeting.
Topic names in greetings and fallbacks are read from the FAQ categories, so the bot
adapts to any dataset without code changes.

## Intent rules

An intent fires only when the **whole** message is small talk (plus harmless filler such
as "so much" or "bot"). `hi` and `thanks a lot` are intents; `hi, where is my order?` is
a real question and goes to the matcher, where the greeting is discarded as filler. If a
message mixes intents, priority is goodbye, then thanks, then greeting. Tests prove that
none of the 320 FAQ phrasings or 144 evaluation questions is classified as an intent.

## Logging (STS section 8)

Each reply logs one INFO line: question (first 120 chars), kind, FAQ id, confidence and
fallback flag. The question is logged with `%r`, which escapes control characters, so a
user cannot forge log lines. Fallback questions are logged to help find gaps in the FAQ set.

## CLI client

```
python -m scripts.chat_cli                              # interactive chat
python -m scripts.chat_cli --ask "Do you ship abroad?"  # one question, then exit
python -m scripts.chat_cli --debug                      # show kind, FAQ id, confidence
```

In interactive mode, type a number to pick one of the suggested questions; `quit`,
`exit`, Ctrl+C or Ctrl+D leave. Output is forced to UTF-8 so Windows consoles do not crash.
