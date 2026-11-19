"""Структуровані дані вакансії, які Researcher витягує з сирого тексту."""

from pydantic import BaseModel, Field


class VacancyExtraction(BaseModel):
    """Те, що LLM витягує з тексту вакансії.

    Навмисно без значень за замовчуванням (default) і без source_text: Gemini
    structured output не підтримує "default" у response_schema (помилка
    "Default value is not supported..."), тому вся модель, яку ми просимо
    заповнити LLM, має лише обов'язкові поля. source_text ми додаємо самі
    після відповіді, з оригінального тексту, а не просимо модель його повторити.
    """

    title: str = Field(description="Назва позиції, напр. 'Junior Python Developer'")
    company: str = Field(description="Назва компанії, якщо вказана в тексті, інакше порожній рядок")
    is_remote: bool = Field(description="Чи дозволена віддалена робота (якщо прямо не сказано - false)")
    seniority: str = Field(description="Рівень: Intern, Junior, Junior+, Middle, Senior, або 'не вказано'")
    required_skills: list[str] = Field(description="Обов'язкові навички/технології, перелічені в тексті")
    nice_to_have_skills: list[str] = Field(
        description="Бажані, але не обов'язкові навички (порожній список, якщо немає)"
    )
    min_years_experience: float | None = Field(
        description="Мінімальна вимога до досвіду в роках, якщо вказана (напр. 3), інакше null"
    )
    english_level_required: str = Field(
        description="Вимога до англійської, напр. 'B2+', якщо не вказана - порожній рядок"
    )


class Vacancy(VacancyExtraction):
    """Повний структурований опис вакансії: те, що витягла LLM, плюс оригінальний текст."""

    source_text: str = Field(description="Оригінальний текст вакансії без змін (для аудиту)")


class Verdict:
    """Можливі вердикти Analyst-агента."""

    APPLY = "apply"
    MAYBE = "maybe"
    SKIP = "skip"


class AnalysisExtraction(BaseModel):
    """Те, що LLM-Analyst витягує при порівнянні вакансії з профілем.

    Без default-значень (та сама причина, що й у VacancyExtraction: Gemini
    structured output відхиляє response_schema з полями, що мають 'default').
    """

    match_percentage: int = Field(description="Оцінка збігу профілю з вакансією, від 0 до 100")
    verdict: str = Field(description="Один з трьох варіантів: 'apply', 'maybe' або 'skip'")
    matched_skills: list[str] = Field(description="Навички з профілю, які прямо збігаються з вимогами вакансії")
    missing_skills: list[str] = Field(description="Обов'язкові вимоги вакансії, яких немає в профілі")
    key_concerns: list[str] = Field(
        description="Головні причини, чому вакансія НЕ підходить (напр. 'потрібно 3+ роки комерційного досвіду, "
        "у профілі 0'). Порожній список, якщо серйозних застережень немає"
    )
    reasoning: str = Field(description="Коротке (2-4 речення) пояснення вердикту простою мовою")


class Analysis(AnalysisExtraction):
    """Повний результат аналізу: те, що оцінила LLM, плюс дані про саму вакансію."""

    vacancy_title: str = Field(description="Назва вакансії (для зручності, скопійовано з Vacancy)")


class CoverLetterExtraction(BaseModel):
    """Те, що LLM-Executor пише - чернетка супровідного листа обома мовами.

    Без default-значень (та сама причина, що й в інших Extraction-моделях:
    Gemini structured output відхиляє response_schema з полями, що мають 'default').
    """

    cover_letter_en: str = Field(description="Супровідний лист англійською, короткий і професійний (3-5 абзаців)")
    cover_letter_uk: str = Field(description="Той самий лист українською (не буквальний переклад, а природний стиль)")


class CoverLetter(CoverLetterExtraction):
    """Повний результат роботи Executor: лист плюс дані про вакансію (для імені файлу/заголовка)."""

    vacancy_title: str = Field(description="Назва вакансії (скопійовано з Vacancy)")
    company: str = Field(description="Назва компанії (скопійовано з Vacancy)")
