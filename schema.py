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
