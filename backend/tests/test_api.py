"""Tests for the Flask API: contract, validation, errors, headers, logging, serving."""

import logging
import uuid

import pytest

from app import config
from app.controllers.api import BAD_BODY
from app.controllers.errors import NOT_READY, UNEXPECTED_ERROR
from app.factory import StartupError, create_app
from app.services.chatbot_service import INVALID_MESSAGE

CHAT_KEYS = {"answer", "matchedQuestion", "confidence", "fallback", "suggestions"}
ERROR_KEYS = {"status", "message", "requestId"}


@pytest.fixture(scope="module")
def client():
    return create_app().test_client()


def assert_error(response, status, message=None):
    assert response.status_code == status
    body = response.get_json()
    assert set(body) == ERROR_KEYS
    assert body["status"] == status
    assert body["requestId"] == response.headers["X-Request-ID"]
    uuid.UUID(body["requestId"])
    if message is not None:
        assert body["message"] == message


class TestChat:
    def test_matched_question_returns_the_sts_payload(self, client):
        response = client.post(
            "/api/chat", json={"message": "How long does delivery take?"}
        )
        assert response.status_code == 200
        body = response.get_json()
        assert set(body) == CHAT_KEYS
        assert body["fallback"] is False and body["confidence"] == 1.0
        assert body["matchedQuestion"] == "How long does delivery take?"
        assert body["suggestions"] == []

    def test_out_of_scope_is_a_200_fallback_not_an_error(self, client):
        response = client.post("/api/chat", json={"message": "Who wrote Hamlet?"})
        body = response.get_json()
        assert response.status_code == 200
        assert body["fallback"] is True and body["matchedQuestion"] is None

    def test_small_talk_is_answered(self, client):
        body = client.post("/api/chat", json={"message": "hello"}).get_json()
        assert body["fallback"] is False and "answer questions" in body["answer"]

    def test_unicode_messages_are_handled(self, client):
        response = client.post(
            "/api/chat", json={"message": "¿Cuánto cuesta el envío? 配送"}
        )
        assert response.status_code == 200

    def test_json_is_accepted_without_a_content_type_header(self, client):
        response = client.post("/api/chat", data='{"message": "hi"}')
        assert response.status_code == 200


class TestChatValidation:
    @pytest.mark.parametrize(
        "payload",
        [{}, {"message": ""}, {"message": "   "}, {"message": 123}, {"message": None},
         {"message": ["hi"]}, {"msg": "hi"}, {"message": "a" * 501}],
    )  # fmt: skip
    def test_bad_messages_give_400(self, client, payload):
        assert_error(client.post("/api/chat", json=payload), 400, INVALID_MESSAGE)

    @pytest.mark.parametrize("body", ["not json", "[]", '"text"', "42", "null", ""])
    def test_non_object_bodies_give_400(self, client, body):
        response = client.post("/api/chat", data=body, content_type="application/json")
        assert_error(response, 400, BAD_BODY)

    def test_boundary_length_is_accepted(self, client):
        response = client.post("/api/chat", json={"message": "a" * 500})
        assert response.status_code == 200

    def test_oversized_body_gives_413(self, client):
        big = '{"message": "' + "a" * (config.MAX_REQUEST_BYTES + 10) + '"}'
        response = client.post("/api/chat", data=big, content_type="application/json")
        assert_error(response, 413, "Request body is too large.")


class TestHealthAndSuggestions:
    def test_health_confirms_faq_data_is_loaded(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok", "faqCount": 80}

    def test_suggested_questions_default(self, client):
        body = client.get("/api/faqs/suggested").get_json()
        assert len(body["suggestions"]) == 4 and body["welcome"]
        assert len(set(body["suggestions"])) == 4

    def test_suggested_questions_respect_limit(self, client):
        assert (
            len(client.get("/api/faqs/suggested?limit=2").get_json()["suggestions"])
            == 2
        )

    @pytest.mark.parametrize("limit", ["0", "9", "abc", "-1"])
    def test_invalid_limit_gives_400(self, client, limit):
        response = client.get(f"/api/faqs/suggested?limit={limit}")
        assert_error(response, 400)


class TestErrorHandling:
    def test_unknown_route_gives_json_404(self, client):
        assert_error(client.get("/api/nope"), 404, "Resource not found.")

    def test_wrong_method_gives_json_405_with_allow_header(self, client):
        response = client.get("/api/chat")
        assert_error(response, 405, "Method not allowed.")
        assert "POST" in response.headers["Allow"]

    def test_unexpected_exception_gives_generic_500_and_is_logged(self, caplog):
        class Exploding:
            faq_count = 1

            def ask(self, _message):
                raise RuntimeError("secret internal detail")

        app = create_app(chatbot=Exploding())
        with caplog.at_level(logging.ERROR):
            response = app.test_client().post("/api/chat", json={"message": "hi"})
        assert_error(response, 500, UNEXPECTED_ERROR)
        assert "secret" not in response.get_data(as_text=True)
        logged = [r for r in caplog.records if r.exc_info]
        assert logged and "secret internal detail" in str(logged[0].exc_info[1])

    def test_each_response_gets_its_own_request_id(self, client):
        ids = {client.get("/api/health").headers["X-Request-ID"] for _ in range(3)}
        assert len(ids) == 3


class TestDegradedStartup:
    def test_missing_data_gives_503_everywhere_without_leaking_paths(
        self, tmp_path, caplog
    ):
        with caplog.at_level(logging.ERROR):
            client = create_app(faq_path=tmp_path / "missing.json").test_client()
        for response in (
            client.get("/api/health"),
            client.post("/api/chat", json={"message": "hi"}),
            client.get("/api/faqs/suggested"),
        ):
            assert_error(response, 503, NOT_READY)
            assert "missing.json" not in response.get_data(as_text=True)
        assert any("missing.json" in r.getMessage() for r in caplog.records)

    def test_strict_mode_refuses_to_start(self, tmp_path):
        with pytest.raises(StartupError, match="not found"):
            create_app(faq_path=tmp_path / "missing.json", strict=True)

    def test_malformed_data_is_reported_as_a_startup_problem(self, tmp_path):
        bad = tmp_path / "faqs.json"
        bad.write_text("[]", encoding="utf-8")
        assert_error(create_app(faq_path=bad).test_client().get("/api/health"), 503)


class TestSecurity:
    def test_security_headers_are_set(self, client):
        headers = client.get("/api/health").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        assert headers["Cache-Control"] == "no-store"

    def test_cross_origin_requests_get_no_cors_permission(self, client):
        response = client.get("/api/health", headers={"Origin": "https://evil.example"})
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_cross_origin_preflight_is_not_approved(self, client):
        response = client.options(
            "/api/chat",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "Access-Control-Allow-Origin" not in response.headers


class TestLogging:
    def test_every_request_is_logged_with_method_path_status_and_duration(
        self, client, caplog
    ):
        with caplog.at_level(logging.INFO, logger="app.controllers.hooks"):
            client.get("/api/health?secret=1")
        line = caplog.records[-1].getMessage()
        assert (
            "GET" in line
            and "'/api/health'" in line
            and "200" in line
            and " ms " in line
        )
        assert "secret" not in line  # query strings are never logged

    def test_crafted_paths_cannot_forge_log_lines(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="app.controllers.hooks"):
            client.get("/api/x%0AINFO%20FAKE")
        assert "\n" not in caplog.records[-1].getMessage()

    def test_personal_data_is_redacted_from_chat_logs(self, client, caplog):
        message = "my email is jane.doe@example.com and my phone is +1 (800) 555-0199"
        with caplog.at_level(logging.INFO, logger="app.services.chatbot_service"):
            client.post("/api/chat", json={"message": message})
        logged = caplog.records[-1].getMessage()
        assert "jane.doe" not in logged and "555" not in logged
        assert "[email]" in logged and "[number]" in logged


class TestServingTheFrontend:
    @pytest.fixture()
    def web(self, tmp_path):
        (tmp_path / "index.html").write_text("<h1>chat</h1>", encoding="utf-8")
        (tmp_path / "app.js").write_text("console.log(1)", encoding="utf-8")
        (tmp_path.parent / "secret.txt").write_text("secret", encoding="utf-8")
        return create_app(frontend_dir=tmp_path).test_client()

    def test_index_and_assets_are_served_from_the_same_origin(self, web):
        with web.get("/") as index:
            assert b"<h1>chat</h1>" in index.data
            assert "default-src 'self'" in index.headers["Content-Security-Policy"]
        with web.get("/app.js") as script:
            assert script.data == b"console.log(1)"

    def test_missing_assets_give_json_404(self, web):
        assert_error(web.get("/missing.css"), 404)

    def test_path_traversal_is_blocked(self, web):
        for path in ("/../secret.txt", "/..%2fsecret.txt", "/%2e%2e/secret.txt"):
            response = web.get(path)
            assert response.status_code == 404
            assert b"secret" not in response.data

    def test_api_still_works_alongside_the_frontend(self, web):
        assert web.get("/api/health").status_code == 200
        assert_error(web.get("/api/nope"), 404)

    def test_api_only_mode_when_no_frontend_folder_exists(self, tmp_path):
        client = create_app(frontend_dir=tmp_path / "does-not-exist").test_client()
        assert_error(client.get("/"), 404)
