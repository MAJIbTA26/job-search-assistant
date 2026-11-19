"""Тести orchestrator.py: перевіряємо сам граф (Researcher і Analyst підмінено заглушками)."""

import orchestrator
from schema import Analysis, Vacancy


def make_vacancy() -> Vacancy:
    return Vacancy(
        title="Junior Python Developer",
        company="Acme",
        is_remote=True,
        seniority="Junior",
        required_skills=["Python"],
        nice_to_have_skills=[],
        min_years_experience=None,
        english_level_required="",
        source_text="текст",
    )


def make_analysis(**overrides) -> Analysis:
    data = {
        "match_percentage": 80,
        "verdict": "apply",
        "matched_skills": ["Python"],
        "missing_skills": [],
        "key_concerns": [],
        "reasoning": "Збіг хороший.",
        "vacancy_title": "Junior Python Developer",
    }
    data.update(overrides)
    return Analysis(**data)


def test_run_returns_vacancy_and_analysis_on_success(monkeypatch):
    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())
    monkeypatch.setattr(orchestrator, "load_profile", lambda: {"core_skills": ["Python"]})
    monkeypatch.setattr(orchestrator, "analyze_vacancy", lambda vacancy, profile: make_analysis())

    result = orchestrator.run("текст вакансії")

    assert result["vacancy"].title == "Junior Python Developer"
    assert result["analysis"].verdict == "apply"
    assert result["error"] is None


def test_run_returns_error_on_researcher_failure(monkeypatch):
    def broken(text):
        raise orchestrator.ResearcherError("Gemini недоступний")

    monkeypatch.setattr(orchestrator, "research_vacancy", broken)

    result = orchestrator.run("текст вакансії")

    assert result["vacancy"] is None
    assert result["analysis"] is None
    assert "Gemini недоступний" in result["error"]


def test_run_returns_error_on_empty_text(monkeypatch):
    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())

    result = orchestrator.run("   ")

    assert result["vacancy"] is None
    assert result["analysis"] is None
    assert result["error"] is not None


def test_analyst_not_called_when_researcher_fails(monkeypatch):
    """Analyst не повинен викликатися, якщо Researcher не повернув вакансію."""
    calls = []

    def broken(text):
        raise orchestrator.ResearcherError("Gemini недоступний")

    def spy_analyze(vacancy, profile):
        calls.append(vacancy)
        return make_analysis()

    monkeypatch.setattr(orchestrator, "research_vacancy", broken)
    monkeypatch.setattr(orchestrator, "analyze_vacancy", spy_analyze)

    orchestrator.run("текст вакансії")

    assert calls == []


def test_run_returns_error_on_analyst_failure(monkeypatch):
    def broken(vacancy, profile):
        raise orchestrator.AnalystError("Gemini недоступний")

    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())
    monkeypatch.setattr(orchestrator, "load_profile", dict)
    monkeypatch.setattr(orchestrator, "analyze_vacancy", broken)

    result = orchestrator.run("текст вакансії")

    assert result["vacancy"].title == "Junior Python Developer"
    assert result["analysis"] is None
    assert "Gemini недоступний" in result["error"]
