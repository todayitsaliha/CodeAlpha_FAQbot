"""Tests for the command-line chat client."""

import pytest

from app import config
from app.repositories.faq_repository import FaqDataError, FaqRepository
from app.services.chatbot_service import ChatbotService
from app.services.matching_service import MatchingSettings
from scripts import chat_cli


@pytest.fixture(scope="module")
def bot():
    return ChatbotService.from_data()


@pytest.fixture(scope="module")
def suggesting_bot():
    faqs = FaqRepository(config.FAQ_PATH).load()
    return ChatbotService(faqs, settings=MatchingSettings(1.0, 0.2))


def run_chat(bot, inputs, debug=False):
    """Drive chat() with scripted input; EOF ends the session."""
    script = iter(inputs)
    output: list[str] = []

    def read(_prompt):
        try:
            return next(script)
        except StopIteration:
            raise EOFError

    chat_cli.chat(bot, debug=debug, read=read, write=output.append)
    return "\n".join(output)


class TestInteractiveChat:
    def test_shows_welcome_and_example_questions(self, bot):
        out = run_chat(bot, ["quit"])
        assert "Bot: Hello!" in out and "Try:" in out and "Goodbye" in out

    def test_answers_a_question(self, bot):
        out = run_chat(bot, ["How long does delivery take?", "exit"])
        assert "3-5 business days" in out
        assert "(matched: How long does delivery take?)" in out

    def test_empty_input_shows_validation_message_and_continues(self, bot):
        out = run_chat(bot, ["", "How long does delivery take?", "quit"])
        assert "Message must be between 1 and 500 characters." in out
        assert "3-5 business days" in out

    def test_end_of_input_exits_cleanly(self, bot):
        assert "Goodbye" in run_chat(bot, [])

    def test_keyboard_interrupt_exits_cleanly(self, bot):
        def read(_prompt):
            raise KeyboardInterrupt

        output: list[str] = []
        chat_cli.chat(bot, read=read, write=output.append)
        assert "Goodbye" in "\n".join(output)

    def test_typing_a_number_asks_the_suggested_question(self, suggesting_bot):
        out = run_chat(suggesting_bot, ["how many days for delivery", "1", "quit"])
        assert "Did you mean one of these?" in out
        assert "     1. " in out
        assert "You: " in out  # the chosen suggestion is echoed

    def test_numbers_are_plain_text_when_there_are_no_suggestions(self, bot):
        out = run_chat(bot, ["1", "quit"])
        assert "couldn't find an answer" in out

    def test_debug_mode_shows_diagnostics(self, bot):
        out = run_chat(bot, ["How long does delivery take?", "quit"], debug=True)
        assert "kind=answer faq_id=1 confidence=1.00" in out


class TestRender:
    def test_answer_includes_matched_question(self, bot):
        lines = chat_cli.render(bot.ask("How long does delivery take?"), debug=False)
        assert lines[0].startswith("Bot: ") and "matched:" in lines[1]

    def test_suggestions_are_numbered(self, suggesting_bot):
        lines = chat_cli.render(suggesting_bot.ask("how many days for delivery"), False)
        assert any(line.strip().startswith("1. ") for line in lines)


class TestMain:
    def test_ask_prints_the_answer(self, capsys):
        assert chat_cli.main(["--ask", "Can I track my order?"]) == 0
        assert "tracking number" in capsys.readouterr().out

    def test_ask_with_empty_message_fails(self, capsys):
        assert chat_cli.main(["--ask", "  "]) == 1
        assert "between 1 and 500" in capsys.readouterr().out

    def test_startup_failure_is_reported_clearly(self, monkeypatch, capsys):
        def broken():
            raise FaqDataError("FAQ file not found: x")

        monkeypatch.setattr(chat_cli.ChatbotService, "from_data", broken)
        assert chat_cli.main(["--ask", "hi"]) == 1
        assert "Cannot start: FAQ file not found" in capsys.readouterr().err
