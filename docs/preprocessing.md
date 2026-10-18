# NLP Preprocessing: Design Notes

Implementation: `backend/app/services/preprocessing_service.py`
Demo: `python -m scripts.preprocess_demo "your question"` (from `backend/`)

## Contract

`PreprocessingService.preprocess(text) -> list[str]` is the only text-normalisation
path in the system. FAQ phrasings are processed with it at startup and every user
question is processed with it at request time, so both sides of the cosine
comparison are always comparable. An empty list means nothing meaningful remained;
the chatbot service treats that as "no match" and returns the fallback.

## Pipeline order and rationale

| Step | Behaviour | Why |
|---|---|---|
| Unicode NFKC + lowercase | Curly apostrophes become `'` | Phone keyboards produce curly quotes; matching must not depend on case |
| Expand contractions | `can't`, `cannot`, `can not` all become `can not`; `n't` becomes `not` | Negation must look identical however the user types it |
| Collapse dotted initials | `P.O.` becomes `po` | `PO box` and `P.O. box` must match |
| Strip punctuation, split hyphens | `interest-free` becomes `interest free` | Keeps unicode letters, drops symbols |
| NLTK `word_tokenize` | | Per STS |
| Slang map | `u`, `ur`, `pls`, `plz`, `thx` | Small, unambiguous set only |
| Drop one-letter tokens and stop words | NLTK English list **minus** negations and `before/after/over/under/off/out/up/down`; plus filler such as `hello`, `please`, `thanks` | `not`/`no` flip meaning; `sign up` and `out of stock` lose meaning without the particles |
| Lemmatise | WordNet, verb form first, then noun form | `shipped`, `shipping` and `ships` become `ship`; `cards` becomes `card` without needing a POS tagger |

## Known limitations (handled elsewhere)

- **No spell correction.** `cancle`, `delivry` and `shiping` pass through unchanged.
  The matching engine (next task) will add character n-gram features alongside
  word TF-IDF to recover typo-ridden queries.
- **Greetings are not interpreted here.** `hello` is filtered as filler. Greeting,
  thanks and goodbye intents are detected before preprocessing by the intent service.
- **Numbers are kept as plain tokens.** `9.99` becomes `9` and `99`; acceptable
  because prices are weak matching signals.
- **Stop-word choices are provisional.** If evaluation shows question words
  (`how`, `when`) help disambiguate similar FAQs, they can be added to
  `KEPT_FUNCTION_WORDS`; the module constants are the only place to change.

## Verification on the shipped dataset

- No FAQ phrasing or evaluation question is reduced to an empty token list.
- No negation present in any FAQ phrasing is lost (tests enforce this).
- FAQ vocabulary after preprocessing: 427 distinct tokens.
