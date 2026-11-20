"""Тести messaging.py: чисте форматування тексту, без Telegram SDK."""

from messaging import format_stats_report, format_vacancy_report, should_notify
from schema import Analysis, Vacancy


def make_vacancy(**overrides) -> Vacancy:
    data = {
        "title": "Junior Python Developer",
        "company": "Acme",
        "is_remote": True,
        "seniority": "Junior",
        "required_skills": ["Python"],
        "nice_to_have_skills": [],
        "min_years_experience": None,
        "english_level_required": "",
        "source_text": "текст",
    }
    data.update(overrides)
    return Vacancy(**data)


def make_analysis(**overrides) -> Analysis:
    data = {
        "match_percentage": 70,
        "verdict": "apply",
        "matched_skills": ["Python"],
        "missing_skills": [],
        "key_concerns": [],
        "reasoning": "Збіг хороший.",
        "vacancy_title": "Junior Python Developer",
    }
    data.update(overrides)
    return Analysis(**data)


def test_should_notify_true_for_apply_and_maybe():
    assert should_notify(make_analysis(verdict="apply")) is True
    assert should_notify(make_analysis(verdict="maybe")) is True


def test_should_notify_false_for_skip_or_none():
    assert should_notify(make_analysis(verdict="skip")) is False
    assert should_notify(None) is False


def test_format_vacancy_report_includes_title_and_verdict():
    report = format_vacancy_report(make_vacancy(), make_analysis(verdict="apply", match_percentage=85))

    assert "Junior Python Developer" in report
    assert "85%" in report
    assert "ВІДГУКНУТИСЬ" in report


def test_format_vacancy_report_includes_link_when_given():
    report = format_vacancy_report(make_vacancy(), make_analysis(), link="https://example.com/job/1")

    assert "https://example.com/job/1" in report


def test_format_vacancy_report_handles_missing_analysis():
    report = format_vacancy_report(make_vacancy(), None)

    assert "Аналіз не виконано" in report


def test_format_stats_report_shows_all_verdicts():
    stats = {"total": 5, "by_verdict": {"apply": 2, "skip": 3}}

    report = format_stats_report(stats)

    assert "Усього переглянуто вакансій: 5" in report
    assert "ВІДГУКНУТИСЬ: 2" in report
    assert "ПРОПУСТИТИ: 3" in report
    assert "МОЖНА СПРОБУВАТИ: 0" in report
