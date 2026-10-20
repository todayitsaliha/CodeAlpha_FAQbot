"""Command-line test client for the chatbot (Sprint 2 demo).

Usage (from backend/):
    python -m scripts.chat_cli                          # interactive chat
    python -m scripts.chat_cli --ask "Do you ship abroad?"   # one question, then exit
    python -m scripts.chat_cli --debug                  # show kind, FAQ id, confidence

In interactive mode type a number to pick one of the suggested questions.
Type quit, exit or press Ctrl+C / Ctrl+D to leave.
"""

import argparse
import sys
from collections.abc import Callable

from app.repositories.faq_repository import FaqDataError
from app.services.chatbot_service import (
    ChatbotService,
    ChatResponse,
    InvalidMessageError,
)

EXIT_WORDS = {"quit", "exit", "q"}


def render(response: ChatResponse, debug: bool) -> list[str]:
    lines = [f"Bot: {response.answer}"]
    if response.matched_question:
        lines.append(f"     (matched: {response.matched_question})")
    for number, question in enumerate(response.suggestions, start=1):
        lines.append(f"     {number}. {question}")
    if debug:
        lines.append(
            f"     [kind={response.kind} faq_id={response.faq_id} "
            f"confidence={response.confidence:.2f} fallback={response.fallback}]"
        )
    return lines


def chat(
    bot: ChatbotService,
    debug: bool = False,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
) -> None:
    write(f"Bot: {bot.welcome_message()}")
    for question in bot.example_questions():
        write(f"     Try: {question}")
    write("     (type 'quit' to leave)\n")

    suggestions: tuple[str, ...] = ()
    while True:
        try:
            message = read("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            write("\nBot: Goodbye!")
            return
        if message.lower() in EXIT_WORDS:
            write("Bot: Goodbye!")
            return
        if message.isdigit() and 1 <= int(message) <= len(suggestions):
            message = suggestions[int(message) - 1]
            write(f"You: {message}")
        try:
            response = bot.ask(message)
        except InvalidMessageError as error:
            write(f"Bot: {error}")
            continue
        suggestions = response.suggestions
        for line in render(response, debug):
            write(line)
        write("")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # keep Windows consoles from crashing
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ask", metavar="QUESTION", help="ask one question and exit")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    try:
        bot = ChatbotService.from_data()
    except FaqDataError as error:
        print(f"Cannot start: {error}", file=sys.stderr)
        return 1

    if args.ask is not None:
        try:
            response = bot.ask(args.ask)
        except InvalidMessageError as error:
            print(f"Bot: {error}")
            return 1
        print("\n".join(render(response, args.debug)))
        return 0

    chat(bot, debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
