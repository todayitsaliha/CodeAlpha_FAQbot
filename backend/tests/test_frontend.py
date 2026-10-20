"""Static checks on the chat UI: CSP compliance, accessibility hooks, XSS safety."""

import re

import pytest

from app import config
from app.factory import create_app

FRONTEND = config.FRONTEND_DIR


@pytest.fixture(scope="module")
def html():
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js():
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def test_html_links_existing_local_assets(html):
    for name in re.findall(r'(?:href|src)="([^"#:]+\.(?:css|js))"', html):
        assert (FRONTEND / name).is_file()


def test_page_complies_with_the_content_security_policy(html):
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)  # no inline scripts
    assert not re.search(r"\sstyle=", html) and "<style" not in html
    assert not re.search(r"\son\w+=", html)  # no inline event handlers


def test_no_external_resources_are_loaded():
    for name in ("index.html", "styles.css", "app.js"):
        text = (FRONTEND / name).read_text(encoding="utf-8")
        urls = re.findall(r"https?://[^\s\"')]+", text)
        assert [u for u in urls if "w3.org/2000/svg" not in u] == []


def test_accessibility_hooks_are_present(html):
    assert 'role="log"' in html and 'aria-live="polite"' in html
    assert re.search(r'<label[^>]*for="input"', html)
    assert 'aria-label="Send question"' in html
    assert '<html lang="en">' in html


def test_input_limit_matches_the_api_limit(html):
    assert f'maxlength="{config.MAX_MESSAGE_LENGTH}"' in html


def test_replies_are_never_inserted_as_markup(js):
    assert "innerHTML" not in js and "insertAdjacentHTML" not in js
    assert "eval(" not in js


def test_script_calls_the_documented_endpoints(js):
    assert '"/api/chat"' in js and "/api/faqs/suggested" in js


def test_reduced_motion_is_respected():
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css


def test_ui_is_served_by_the_app_with_security_headers():
    client = create_app().test_client()
    with client.get("/") as page:
        assert page.status_code == 200 and b"FAQ Chat" in page.data
        assert "default-src 'self'" in page.headers["Content-Security-Policy"]
    with client.get("/app.js") as script:
        assert script.status_code == 200 and "javascript" in script.content_type
    with client.get("/styles.css") as sheet:
        assert sheet.status_code == 200
