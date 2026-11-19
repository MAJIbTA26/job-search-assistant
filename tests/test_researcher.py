"""Тести researcher.py з мокованим genai.Client (без реальних викликів Gemini)."""

import pytest

import researcher
from researcher import ResearcherError, research_vacancy
from schema import Vacancy, VacancyExtraction


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
        "source_text": "",
    }
    data.update(overrides)
    return Vacancy(**data)


class FakeResponse:
    def __init__(self, vacancy: Vacancy):
        # Імітує те, що справді повертає Gemini: VacancyExtraction (без source_text),
        # бо source_text researcher.py додає сам з оригінального тексту.
        extraction = VacancyExtraction(**vacancy.model_dump(exclude={"source_text"}))
        self.text = extraction.model_dump_json()


class FakeModels:
    def __init__(self, vacancy=None, fail_times=0, exc=None):
        self.vacancy = vacancy or make_vacancy()
        self.fail_times = fail_times
        self.exc = exc or RuntimeError("boom")
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.exc
        return FakeResponse(self.vacancy)


class FakeClient:
    def __init__(self, models: FakeModels):
        self.models = models


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(researcher.time, "sleep", lambda _seconds: None)


def test_research_vacancy_returns_structured_data(monkeypatch):
    fake_models = FakeModels(vacancy=make_vacancy(title="Data Analyst"))
    monkeypatch.setattr(researcher, "_client", lambda: FakeClient(fake_models))

    result = research_vacancy("Шукаємо Data Analyst...")

    assert result.title == "Data Analyst"
    assert fake_models.calls == [researcher.MODEL]


def test_research_vacancy_keeps_original_source_text(monkeypatch):
    fake_models = FakeModels()
    monkeypatch.setattr(researcher, "_client", lambda: FakeClient(fake_models))

    result = research_vacancy("  оригінальний текст  ")

    assert result.source_text == "  оригінальний текст  "


def test_empty_text_raises_value_error():
    with pytest.raises(ValueError):
        research_vacancy("   ")


def test_missing_api_key_raises_researcher_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ResearcherError):
        research_vacancy("якийсь текст")


def test_retries_then_succeeds(monkeypatch):
    fake_models = FakeModels(fail_times=2)
    monkeypatch.setattr(researcher, "_client", lambda: FakeClient(fake_models))

    result = research_vacancy("текст вакансії")

    assert result.title == "Junior Python Developer"
    assert len(fake_models.calls) == 3


def test_falls_back_to_second_model_after_repeated_failures(monkeypatch):
    fake_models = FakeModels(fail_times=researcher.MAX_ATTEMPTS)  # основна модель завжди падає
    monkeypatch.setattr(researcher, "_client", lambda: FakeClient(fake_models))

    result = research_vacancy("текст вакансії")

    assert result.title == "Junior Python Developer"
    assert fake_models.calls[: researcher.MAX_ATTEMPTS] == [researcher.MODEL] * researcher.MAX_ATTEMPTS
    assert fake_models.calls[researcher.MAX_ATTEMPTS] == researcher.FALLBACK_MODEL


def test_all_attempts_fail_raises_researcher_error(monkeypatch):
    total_attempts = researcher.MAX_ATTEMPTS * 2  # основна + резервна модель
    fake_models = FakeModels(fail_times=total_attempts)
    monkeypatch.setattr(researcher, "_client", lambda: FakeClient(fake_models))

    with pytest.raises(ResearcherError):
        research_vacancy("текст вакансії")

    assert len(fake_models.calls) == total_attempts


def test_extraction_schema_has_no_default_values():
    """Gemini structured output відхиляє response_schema з полями, що мають 'default'."""
    schema = VacancyExtraction.model_json_schema()
    for field_name, field_schema in schema["properties"].items():
        assert "default" not in field_schema, f"Поле {field_name} не повинно мати default"
