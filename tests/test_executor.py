"""Тести executor.py з мокованим genai.Client (без реальних викликів Gemini)."""

import pytest

import executor
from executor import ExecutorError, draft_cover_letter, save_cover_letter
from schema import Analysis, CoverLetter, CoverLetterExtraction, Vacancy


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


def make_cover_letter(**overrides) -> CoverLetter:
    data = {
        "cover_letter_en": "Dear hiring manager, ...",
        "cover_letter_uk": "Шановний менеджере з найму, ...",
        "vacancy_title": "Junior Python Developer",
        "company": "Acme",
    }
    data.update(overrides)
    return CoverLetter(**data)


class FakeResponse:
    def __init__(self, letter: CoverLetter):
        extraction = CoverLetterExtraction(**letter.model_dump(exclude={"vacancy_title", "company"}))
        self.text = extraction.model_dump_json()


class FakeModels:
    def __init__(self, letter=None, fail_times=0, exc=None):
        self.letter = letter or make_cover_letter()
        self.fail_times = fail_times
        self.exc = exc or RuntimeError("boom")
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.exc
        return FakeResponse(self.letter)


class FakeClient:
    def __init__(self, models: FakeModels):
        self.models = models


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(executor.time, "sleep", lambda _seconds: None)


def test_draft_cover_letter_returns_both_languages(monkeypatch):
    fake_models = FakeModels()
    monkeypatch.setattr(executor, "_client", lambda: FakeClient(fake_models))

    result = draft_cover_letter(make_vacancy(), make_analysis(), profile={})

    assert "Dear hiring manager" in result.cover_letter_en
    assert "Шановний" in result.cover_letter_uk
    assert fake_models.calls == [executor.MODEL]


def test_draft_cover_letter_uses_vacancy_data_not_llm_output(monkeypatch):
    fake_models = FakeModels(letter=make_cover_letter(vacancy_title="щось інше", company="Інша компанія"))
    monkeypatch.setattr(executor, "_client", lambda: FakeClient(fake_models))

    vacancy = make_vacancy(title="Справжня назва", company="Справжня компанія")
    result = draft_cover_letter(vacancy, make_analysis(), profile={})

    assert result.vacancy_title == "Справжня назва"
    assert result.company == "Справжня компанія"


def test_missing_api_key_raises_executor_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ExecutorError):
        draft_cover_letter(make_vacancy(), make_analysis(), profile={})


def test_retries_then_succeeds(monkeypatch):
    fake_models = FakeModels(fail_times=2)
    monkeypatch.setattr(executor, "_client", lambda: FakeClient(fake_models))

    result = draft_cover_letter(make_vacancy(), make_analysis(), profile={})

    assert result.company == "Acme"
    assert len(fake_models.calls) == 3


def test_falls_back_to_second_model_after_repeated_failures(monkeypatch):
    fake_models = FakeModels(fail_times=executor.MAX_ATTEMPTS)
    monkeypatch.setattr(executor, "_client", lambda: FakeClient(fake_models))

    result = draft_cover_letter(make_vacancy(), make_analysis(), profile={})

    assert result.company == "Acme"
    assert fake_models.calls[: executor.MAX_ATTEMPTS] == [executor.MODEL] * executor.MAX_ATTEMPTS
    assert fake_models.calls[executor.MAX_ATTEMPTS] == executor.FALLBACK_MODEL


def test_all_attempts_fail_raises_executor_error(monkeypatch):
    total_attempts = executor.MAX_ATTEMPTS * 2
    fake_models = FakeModels(fail_times=total_attempts)
    monkeypatch.setattr(executor, "_client", lambda: FakeClient(fake_models))

    with pytest.raises(ExecutorError):
        draft_cover_letter(make_vacancy(), make_analysis(), profile={})

    assert len(fake_models.calls) == total_attempts


def test_extraction_schema_has_no_default_values():
    """Gemini structured output відхиляє response_schema з полями, що мають 'default'."""
    schema = CoverLetterExtraction.model_json_schema()
    for field_name, field_schema in schema["properties"].items():
        assert "default" not in field_schema, f"Поле {field_name} не повинно мати default"


def test_save_cover_letter_writes_both_languages(tmp_path):
    letter = make_cover_letter()

    path = save_cover_letter(letter, directory=tmp_path)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Dear hiring manager" in content
    assert "Шановний" in content
    assert letter.vacancy_title in content


def test_save_cover_letter_filename_has_no_unsafe_characters(tmp_path):
    letter = make_cover_letter(company="ТОВ «Ацме»!", vacancy_title="Junior Python Developer (remote)")

    path = save_cover_letter(letter, directory=tmp_path)

    assert path.parent == tmp_path
    assert " " not in path.name
    assert "«" not in path.name
