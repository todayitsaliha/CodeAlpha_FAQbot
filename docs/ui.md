# Chat UI

Files: `frontend/index.html`, `styles.css`, `app.js` (plain HTML/CSS/JS, no build step,
no npm). Served by the Flask app at `/`, so API calls are same-origin. Start it with
`python run.py` (from `backend/`) and open http://127.0.0.1:5000. Visual reference:
`docs/design/`.

## Behaviour

- Welcome bubble and four suggestion chips come from `GET /api/faqs/suggested`.
- Sending a message (Enter or the send button) shows "Let me check that for you..." while
  `POST /api/chat` is pending; input and chips are disabled meanwhile.
- Confident match: answer plus a "Matched FAQ" badge with the confidence percentage.
- Medium confidence: the answer, a "Low confidence" badge and clickable suggestions.
- Out of scope: the polite fallback, no badge. Small talk: plain reply, no badge.
- Validation errors (400) show the API's own message; network and server errors show a
  message with a "Try again" button that resends the last question.
- The header dot shows Online or Offline from the most recent API call.

## Design tokens (from the inspiration images)

Frame `#c9dcee`, card `#faf6ee`, bot bubble `#ede8dc`, ink `#1f4e8c`, user bubble
`#1f5a9e`, chip border `#a9c8e8`, accent `#2563b0`, online `#3cb878`. System monospace
stack (JetBrains Mono, IBM Plex Mono, Consolas, Courier New). The mascot is a 16x16
pixel-art SVG symbol, so no image files are needed.

## Quality and security

- Replies are inserted as plain text only (a test forbids `innerHTML`).
- No inline scripts, styles or external resources, as the Content-Security-Policy
  requires (tests enforce this).
- Message log has `role="log"` with a polite live region; the input has a label; every
  control is keyboard-operable with a visible focus ring; reduced-motion is respected;
  the layout goes full-screen below 520 px.

## Not yet verified

The UI was checked by automated tests (syntax, CSP rules, accessibility hooks, serving)
but not rendered in a browser during development. Open it once and compare it to the
inspiration images before the UAT session.
