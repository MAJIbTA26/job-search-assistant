"""Тести url_fetcher.py: requests.get замокано (реальних мережевих запитів немає)."""

import pytest
import requests

import url_fetcher
from url_fetcher import FetchError, fetch_page_text, looks_like_url


def test_looks_like_url_true_for_http_https():
    assert looks_like_url("https://example.com/jobs/123") is True
    assert looks_like_url("http://example.com") is True


def test_looks_like_url_false_for_plain_text():
    assert looks_like_url("Junior Python Developer, remote") is False
    assert looks_like_url("  https://example.com and some text after it  ") is False


def test_looks_like_url_strips_surrounding_whitespace():
    assert looks_like_url("  https://example.com/job  ") is True


class FakeResponse:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def test_fetch_page_text_strips_tags_scripts_and_styles(monkeypatch):
    html = """
    <html><head><style>body{color:red}</style></head>
    <body>
      <script>console.log('noise')</script>
      <nav>Menu</nav>
      <h1>Junior Python Developer</h1>
      <p>We need Python and FastAPI.</p>
      <footer>copyright 2026</footer>
    </body></html>
    """
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: FakeResponse(html))

    text = fetch_page_text("https://example.com/job/1")

    assert "Junior Python Developer" in text
    assert "Python and FastAPI" in text
    assert "console.log" not in text
    assert "color:red" not in text
    assert "Menu" not in text
    assert "copyright" not in text


def test_fetch_page_text_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: FakeResponse("", status=404))

    with pytest.raises(FetchError):
        fetch_page_text("https://example.com/missing")


def test_fetch_page_text_raises_on_network_error(monkeypatch):
    def broken(url, headers=None, timeout=None):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(requests, "get", broken)

    with pytest.raises(FetchError):
        fetch_page_text("https://example.com/job/1")


def test_fetch_page_text_raises_on_empty_page(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: FakeResponse("<html></html>"))

    with pytest.raises(FetchError):
        fetch_page_text("https://example.com/empty")


def test_fetch_page_text_truncates_to_max_chars(monkeypatch):
    long_html = f"<p>{'a' * (url_fetcher.MAX_CHARS + 1000)}</p>"
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: FakeResponse(long_html))

    text = fetch_page_text("https://example.com/long")

    assert len(text) == url_fetcher.MAX_CHARS
