"""Analyst agent: порівнює структуровану вакансію (Vacancy) з профілем кандидата
і дає чесний вердикт: apply / maybe / skip.

Логіка побудови повторює researcher.py: structured output через Gemini,
повтори з exponential backoff, резервна модель при збої основної.
"""

import json
import logging
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from schema import Analysis, AnalysisExtraction, Vacancy

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "gemini-flash-lite-latest"
FALLBACK_MODEL = "gemini-flash-latest"
MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 3

# Інструкція навмисно консервативна: мета - чесна оцінка, а не підбадьорення.
# Саме так ми й оцінювали вакансії вручну в цій розмові - без прикрашання.
SYSTEM_PROMPT = """Ти чесний і прямий кар'єрний консультант для junior-розробника.
Порівнюєш вимоги вакансії з профілем кандидата і даєш РЕАЛІСТИЧНУ оцінку збігу.

Правила:
- НЕ прикрашай: якщо вакансія вимагає 3+ роки комерційного досвіду, а в кандидата 0,
  це критична невідповідність незалежно від збігу технологій.
- "nice to have" навички важать менше, ніж "required".
- verdict "apply": реальний шанс пройти відбір (збіг обов'язкових вимог високий,
  рівень посади відповідає профілю).
- verdict "maybe": є сенс спробувати, але шанси помірні, варто зважити.
- verdict "skip": вакансія явно не для цього профілю (інший рівень, відсутні
  критичні навички, яких не надолужити швидко).
- match_percentage узгоджуй з verdict: apply зазвичай 60+, maybe 35-60, skip нижче 35.
- Пиши коротко і по суті, без зайвого оптимізму."""


class AnalystError(RuntimeError):
    """Не вдалося проаналізувати вакансію (конфігурація або LLM недоступна після всіх спроб)."""


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise AnalystError("GEMINI_API_KEY не задано")
    return genai.Client(api_key=api_key)


def _build_prompt(vacancy: Vacancy, profile: dict) -> str:
    return (
        f"ПРОФІЛЬ КАНДИДАТА:\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        f"ВАКАНСІЯ:\n"
        f"Назва: {vacancy.title}\n"
        f"Рівень: {vacancy.seniority}\n"
        f"Мін. досвід (років): {vacancy.min_years_experience}\n"
        f"Віддалено: {vacancy.is_remote}\n"
        f"Обов'язкові навички: {', '.join(vacancy.required_skills)}\n"
        f"Бажані навички: {', '.join(vacancy.nice_to_have_skills)}\n"
        f"Англійська: {vacancy.english_level_required or 'не вказано'}\n"
    )


def _extract(client: genai.Client, model: str, vacancy: Vacancy, profile: dict) -> Analysis:
    response = client.models.generate_content(
        model=model,
        contents=_build_prompt(vacancy, profile),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=AnalysisExtraction,
            temperature=0,
        ),
    )
    extraction = AnalysisExtraction.model_validate_json(response.text)
    return Analysis(**extraction.model_dump(), vacancy_title=vacancy.title)


def analyze_vacancy(vacancy: Vacancy, profile: dict) -> Analysis:
    """Порівнює вакансію з профілем і повертає вердикт.

    Raises:
        AnalystError: якщо не задано GEMINI_API_KEY або всі спроби (основна + резервна модель) провалились.
    """
    client = _client()
    last_error: Exception | None = None

    for model in (MODEL, FALLBACK_MODEL):
        for attempt in range(MAX_ATTEMPTS):
            try:
                return _extract(client, model, vacancy, profile)
            except Exception as e:  # noqa: BLE001 - будь-яка помилка LLM/парсингу веде до повтору чи fallback
                last_error = e
                logger.warning(f"Analyst: спроба {attempt + 1} з моделлю {model} невдала: {e}")
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(BASE_DELAY_SECONDS * (2**attempt))

    raise AnalystError(f"Не вдалося проаналізувати вакансію після всіх спроб: {last_error}") from last_error
