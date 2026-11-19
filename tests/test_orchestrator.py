"""Тести orchestrator.py: перевіряємо сам граф (researcher підмінено заглушкою)."""

import orchestrator
from schema import Vacancy


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


def test_run_returns_vacancy_on_success(monkeypatch):
    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())

    result = orchestrator.run("текст вакансії")

    assert result["vacancy"].title == "Junior Python Developer"
    assert result["error"] is None


def test_run_returns_error_on_researcher_failure(monkeypatch):
    def broken(text):
        raise orchestrator.ResearcherError("Gemini недоступний")

    monkeypatch.setattr(orchestrator, "research_vacancy", broken)

    result = orchestrator.run("текст вакансії")

    assert result["vacancy"] is None
    assert "Gemini недоступний" in result["error"]


def test_run_returns_error_on_empty_text(monkeypatch):
    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())

    result = orchestrator.run("   ")

    assert result["vacancy"] is None
    assert result["error"] is not None
