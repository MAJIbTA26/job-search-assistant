"""Тести analyst.py з мокованим genai.Client (без реальних викликів Gemini)."""

import pytest

import analyst
from analyst import AnalystError, analyze_vacancy
from schema import Analysis, AnalysisExtraction, Vacancy


def make_vacancy(**overrides) -> Vacancy:
    data = {
        "title": "Junior Python Developer",
        "company": "Acme",
        "is_remote": True,
        "seniority": "Junior",
        "required_skills": ["Python", "FastAPI"],
        "nice_to_have_skills": ["Docker"],
        "min_years_experience": None,
        "english_level_required": "B1",
        "source_text": "текст",
    }
    data.update(overrides)
    return Vacancy(**data)


def make_analysis(**overrides) -> Analysis:
    data = {
        "match_percentage": 70,
        "verdict": "apply",
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": [],
        "key_concerns": [],
        "reasoning": "Збіг хороший.",
        "vacancy_title": "Junior Python Developer",
    }
    data.update(overrides)
    return Analysis(**data)


class FakeResponse:
    def __init__(self, analysis: Analysis):
        extraction = AnalysisExtraction(**analysis.model_dump(exclude={"vacancy_title"}))
        self.text = extraction.model_dump_json()


class FakeModels:
    def __init__(self, analysis=None, fail_times=0, exc=None):
        self.analysis = analysis or make_analysis()
        self.fail_times = fail_times
        self.exc = exc or RuntimeError("boom")
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.exc
        return FakeResponse(self.analysis)


class FakeClient:
    def __init__(self, models: FakeModels):
        self.models = models


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(analyst.time, "sleep", lambda _seconds: None)


def test_analyze_vacancy_returns_verdict(monkeypatch):
    fake_models = FakeModels(analysis=make_analysis(verdict="skip", match_percentage=15))
    monkeypatch.setattr(analyst, "_client", lambda: FakeClient(fake_models))

    result = analyze_vacancy(make_vacancy(), profile={"core_skills": ["Python"]})

    assert result.verdict == "skip"
    assert result.match_percentage == 15
    assert fake_models.calls == [analyst.MODEL]


def test_analyze_vacancy_uses_vacancy_title_not_llm_output(monkeypatch):
    fake_models = FakeModels(analysis=make_analysis(vacancy_title="щось інше"))
    monkeypatch.setattr(analyst, "_client", lambda: FakeClient(fake_models))

    vacancy = make_vacancy(title="Справжня назва")
    result = analyze_vacancy(vacancy, profile={})

    assert result.vacancy_title == "Справжня назва"


def test_missing_api_key_raises_analyst_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(AnalystError):
        analyze_vacancy(make_vacancy(), profile={})


def test_retries_then_succeeds(monkeypatch):
    fake_models = FakeModels(fail_times=2)
    monkeypatch.setattr(analyst, "_client", lambda: FakeClient(fake_models))

    result = analyze_vacancy(make_vacancy(), profile={})

    assert result.verdict == "apply"
    assert len(fake_models.calls) == 3


def test_falls_back_to_second_model_after_repeated_failures(monkeypatch):
    fake_models = FakeModels(fail_times=analyst.MAX_ATTEMPTS)
    monkeypatch.setattr(analyst, "_client", lambda: FakeClient(fake_models))

    result = analyze_vacancy(make_vacancy(), profile={})

    assert result.verdict == "apply"
    assert fake_models.calls[: analyst.MAX_ATTEMPTS] == [analyst.MODEL] * analyst.MAX_ATTEMPTS
    assert fake_models.calls[analyst.MAX_ATTEMPTS] == analyst.FALLBACK_MODEL


def test_all_attempts_fail_raises_analyst_error(monkeypatch):
    total_attempts = analyst.MAX_ATTEMPTS * 2
    fake_models = FakeModels(fail_times=total_attempts)
    monkeypatch.setattr(analyst, "_client", lambda: FakeClient(fake_models))

    with pytest.raises(AnalystError):
        analyze_vacancy(make_vacancy(), profile={})

    assert len(fake_models.calls) == total_attempts


def test_extraction_schema_has_no_default_values():
    """Gemini structured output відхиляє response_schema з полями, що мають 'default'."""
    schema = AnalysisExtraction.model_json_schema()
    for field_name, field_schema in schema["properties"].items():
        assert "default" not in field_schema, f"Поле {field_name} не повинно мати default"
