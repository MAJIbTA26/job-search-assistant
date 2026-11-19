"""Тести orchestrator.py: перевіряємо сам граф (Researcher/Analyst/Executor підмінено заглушками)."""

import orchestrator
from schema import Analysis, CoverLetter, Vacancy


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


def make_cover_letter(**overrides) -> CoverLetter:
    data = {
        "cover_letter_en": "Dear hiring manager, ...",
        "cover_letter_uk": "Шановний менеджере з найму, ...",
        "vacancy_title": "Junior Python Developer",
        "company": "Acme",
    }
    data.update(overrides)
    return CoverLetter(**data)


def test_run_returns_vacancy_analysis_and_letter_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())
    monkeypatch.setattr(orchestrator, "load_profile", lambda: {"core_skills": ["Python"]})
    monkeypatch.setattr(orchestrator, "analyze_vacancy", lambda vacancy, profile: make_analysis())
    monkeypatch.setattr(orchestrator, "draft_cover_letter", lambda vacancy, analysis, profile: make_cover_letter())
    monkeypatch.setattr(orchestrator, "save_cover_letter", lambda letter: tmp_path / "letter.txt")

    result = orchestrator.run("текст вакансії")

    assert result["vacancy"].title == "Junior Python Developer"
    assert result["analysis"].verdict == "apply"
    assert result["cover_letter"].company == "Acme"
    assert result["cover_letter_path"] == str(tmp_path / "letter.txt")
    assert result["error"] is None


def test_run_returns_error_on_researcher_failure(monkeypatch):
    def broken(text):
        raise orchestrator.ResearcherError("Gemini недоступний")

    monkeypatch.setattr(orchestrator, "research_vacancy", broken)

    result = orchestrator.run("текст вакансії")

    assert result["vacancy"] is None
    assert result["analysis"] is None
    assert result["cover_letter"] is None
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
    assert result["cover_letter"] is None
    assert "Gemini недоступний" in result["error"]


def test_executor_not_called_when_verdict_is_skip(monkeypatch):
    """Executor не повинен писати лист на вакансію, яку Analyst вже порадив пропустити."""
    calls = []

    def spy_draft(vacancy, analysis, profile):
        calls.append(vacancy)
        return make_cover_letter()

    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())
    monkeypatch.setattr(orchestrator, "load_profile", dict)
    monkeypatch.setattr(orchestrator, "analyze_vacancy", lambda vacancy, profile: make_analysis(verdict="skip"))
    monkeypatch.setattr(orchestrator, "draft_cover_letter", spy_draft)

    result = orchestrator.run("текст вакансії")

    assert calls == []
    assert result["cover_letter"] is None
    assert result["cover_letter_path"] is None


def test_executor_called_when_verdict_is_maybe(monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())
    monkeypatch.setattr(orchestrator, "load_profile", dict)
    monkeypatch.setattr(orchestrator, "analyze_vacancy", lambda vacancy, profile: make_analysis(verdict="maybe"))
    monkeypatch.setattr(orchestrator, "draft_cover_letter", lambda vacancy, analysis, profile: make_cover_letter())
    monkeypatch.setattr(orchestrator, "save_cover_letter", lambda letter: tmp_path / "letter.txt")

    result = orchestrator.run("текст вакансії")

    assert result["cover_letter"].company == "Acme"


def test_run_returns_error_on_executor_failure(monkeypatch):
    def broken(vacancy, analysis, profile):
        raise orchestrator.ExecutorError("Gemini недоступний")

    monkeypatch.setattr(orchestrator, "research_vacancy", lambda text: make_vacancy())
    monkeypatch.setattr(orchestrator, "load_profile", dict)
    monkeypatch.setattr(orchestrator, "analyze_vacancy", lambda vacancy, profile: make_analysis())
    monkeypatch.setattr(orchestrator, "draft_cover_letter", broken)

    result = orchestrator.run("текст вакансії")

    assert result["analysis"].verdict == "apply"
    assert result["cover_letter"] is None
    assert "Gemini недоступний" in result["error"]
