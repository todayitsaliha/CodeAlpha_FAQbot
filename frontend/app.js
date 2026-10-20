(() => {
  "use strict";
  const log = document.getElementById("log");
  const form = document.getElementById("form");
  const input = document.getElementById("input");
  const send = document.getElementById("send");
  const status = document.getElementById("status");
  const statusText = document.getElementById("status-text");
  const SVG = "http://www.w3.org/2000/svg";
  let busy = false;
  let lastMessage = "";

  // Text is always inserted as plain text, so replies cannot inject markup.
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function icon(id) {
    const svg = document.createElementNS(SVG, "svg");
    const use = document.createElementNS(SVG, "use");
    use.setAttribute("href", "#" + id);
    svg.appendChild(use);
    return svg;
  }
  function setStatus(state, text) {
    status.dataset.state = state;
    statusText.textContent = text;
  }
  function scrollDown() { log.scrollTop = log.scrollHeight; }

  function row(who) {
    const wrap = el("div", "row " + who);
    const avatar = el("div", "avatar" + (who === "user" ? " person" : ""));
    avatar.appendChild(icon(who === "user" ? "person" : "bot"));
    const stack = el("div", "stack");
    wrap.append(avatar, stack);
    log.appendChild(wrap);
    return { wrap, stack };
  }
  function bot(text, cls) {
    const r = row("bot");
    r.stack.appendChild(el("div", "bubble" + (cls ? " " + cls : ""), text));
    scrollDown();
    return r;
  }
  function user(text) {
    row("user").stack.appendChild(el("div", "bubble", text));
    scrollDown();
  }
  function chips(stack, questions) {
    const box = el("div", "chips");
    for (const q of questions) {
      const b = el("button", "chip", q);
      b.type = "button";
      b.addEventListener("click", () => ask(q));
      box.appendChild(b);
    }
    stack.appendChild(box);
  }
  function badge(stack, text, low) {
    const b = el("div", "badge" + (low ? " low" : ""));
    if (!low) b.appendChild(icon("check"));
    b.appendChild(el("span", "", text));
    stack.appendChild(b);
  }
  function setBusy(value) {
    busy = value;
    send.disabled = value;
    document.querySelectorAll(".chip").forEach((c) => { c.disabled = value; });
  }

  function render(data) {
    const r = bot(data.answer);
    const pct = Math.round(data.confidence * 100);
    if (data.matchedQuestion && !data.fallback) {
      badge(r.stack, "Matched FAQ \u00b7 " + pct + "%", false);
    } else if (data.fallback && data.suggestions.length) {
      badge(r.stack, "Low confidence \u00b7 " + pct + "%", true);
    }
    if (data.suggestions.length) chips(r.stack, data.suggestions);
    scrollDown();
  }

  async function ask(message) {
    message = message.trim();
    if (!message || busy) return;
    lastMessage = message;
    user(message);
    input.value = "";
    setBusy(true);
    const typing = bot("Let me check that for you\u2026", "typing");
    typing.wrap.setAttribute("role", "status");
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      typing.wrap.remove();
      if (res.ok) { setStatus("online", "Online"); render(data); }
      else { problem(data.message || "Something went wrong.", res.status >= 500); }
    } catch (error) {
      typing.wrap.remove();
      setStatus("offline", "Offline");
      problem("I can\u2019t reach the server. Check your connection and try again.", true);
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  function problem(text, canRetry) {
    const r = bot(text, "error");
    if (canRetry) {
      const retry = el("button", "retry", "Try again");
      retry.type = "button";
      retry.addEventListener("click", () => { r.wrap.remove(); ask(lastMessage); });
      r.stack.appendChild(retry);
    }
  }

  async function start() {
    try {
      const res = await fetch("/api/faqs/suggested?limit=4");
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      setStatus("online", "Online");
      const r = bot("Hi! \ud83d\udc4b\n" + data.welcome);
      chips(r.stack, data.suggestions);
    } catch (error) {
      setStatus("offline", "Offline");
      bot("The FAQ service isn\u2019t available right now. Reload the page in a moment.", "error");
    }
  }

  form.addEventListener("submit", (event) => { event.preventDefault(); ask(input.value); });
  start();
})();
