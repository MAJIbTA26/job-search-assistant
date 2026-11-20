"""Тести sources.py: парсинг RSS без реальних мережевих запитів (feedparser.parse
приймає як URL, так і готовий текст - для тестів даємо готовий XML-текст)."""

from sources import RawVacancy, fetch_remote_jobs, parse_feed

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Test Feed</title>
  <item>
    <title>Junior Python Developer</title>
    <link>https://weworkremotely.com/jobs/12345</link>
    <description>&lt;p&gt;We need a &lt;b&gt;Python&lt;/b&gt; developer. Remote only.&lt;/p&gt;</description>
  </item>
  <item>
    <title>Senior Rust Engineer</title>
    <link>https://weworkremotely.com/jobs/67890</link>
    <description>Looking for 5+ years Rust experience.</description>
  </item>
</channel>
</rss>
"""

EMPTY_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>
"""

BROKEN_FEED = "це не XML, а просто текст"


def test_parse_feed_returns_one_vacancy_per_item():
    result = parse_feed(SAMPLE_FEED)

    assert len(result) == 2
    assert all(isinstance(v, RawVacancy) for v in result)


def test_parse_feed_strips_html_from_description():
    result = parse_feed(SAMPLE_FEED)

    first = result[0]
    assert "<p>" not in first.raw_text
    assert "<b>" not in first.raw_text
    assert "Python developer" in first.raw_text


def test_parse_feed_includes_title_and_link_in_raw_text():
    result = parse_feed(SAMPLE_FEED)

    first = result[0]
    assert first.title == "Junior Python Developer"
    assert first.link == "https://weworkremotely.com/jobs/12345"
    assert first.link in first.raw_text
    assert first.title in first.raw_text


def test_parse_feed_handles_empty_feed():
    assert parse_feed(EMPTY_FEED) == []


def test_fetch_remote_jobs_returns_empty_list_on_broken_feed(monkeypatch):
    """Якщо мережа/стрічка недоступна - fetch_remote_jobs не повинен кидати виняток, лише повернути []."""
    import feedparser as fp

    original_parse = fp.parse
    monkeypatch.setattr(fp, "parse", lambda url, **kwargs: original_parse(BROKEN_FEED))

    assert fetch_remote_jobs("https://example.com/broken.rss") == []
