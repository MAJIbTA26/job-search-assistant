"""Executor agent: пише чернетку супровідного листа (англійською та українською)
для вакансії, яку Analyst визнав вартою уваги (verdict "apply" або "maybe"),
і зберігає результат у файл.

Логіка побудови повторює researcher.py/analyst.py: structured output через Gemini,
повтори з exponential backoff, резервна модель при збої основної.
"""

import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from schema import Analysis, CoverLetter, CoverLetterExtraction, Vacancy

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "gemini-flash-lite-latest"
FALLBACK_MODEL = "gemini-flash-latest"
MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 3

APPLICATIONS_DIR = Path(__file__).parent / "applications"

SYSTEM_PROMPT = """Ти пишеш чернетку супровідного листа (cover letter) для junior Python-розробника,
який відгукується на вакансію. Лист повинен звучати природно, по-людськи, без штампів і
перебільшень. Ніяких "I am a perfect fit" чи вигаданих досягнень - тільки те, що реально
є в профілі кандидата.

Правила:
- Коротко: 3-5 абзаців, не більше.
- Опирайся на matched_skills і reasoning з аналізу - покажи, що саме збігається.
- Якщо є key_concerns (наприклад, брак комерційного досвіду), не приховуй це, а чесно
  поясни, чим кандидат компенсує (навчання, власні проєкти, портфоліо).
- Без вигаданих фактів: не додавай нічого, чого немає в профілі чи вакансії.
- Напиши ОБИДВІ версії: cover_letter_en англійською і cover_letter_uk українською -
  не буквальний переклад одна одної, а природний текст у кожній мові."""


class ExecutorError(RuntimeError):
    """Не вдалося згенерувати супровідний лист (конфігурація або LLM недоступна після всіх спроб)."""


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ExecutorError("GEMINI_API_KEY не задано")
    return genai.Client(api_key=api_key)


def _build_prompt(vacancy: Vacancy, analysis: Analysis, profile: dict) -> str:
    return (
        f"ПРОФІЛЬ КАНДИДАТА:\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        f"ВАКАНСІЯ:\n"
        f"Назва: {vacancy.title}\n"
        f"Компанія: {vacancy.company or 'не вказано'}\n"
        f"Рівень: {vacancy.seniority}\n"
        f"Обов'язкові навички: {', '.join(vacancy.required_skills)}\n\n"
        f"АНАЛІЗ ВІДПОВІДНОСТІ:\n"
        f"Збіг: {analysis.match_percentage}%\n"
        f"Збігається: {', '.join(analysis.matched_skills) or '-'}\n"
        f"Бракує: {', '.join(analysis.missing_skills) or '-'}\n"
        f"Застереження: {', '.join(analysis.key_concerns) or '-'}\n"
        f"Пояснення Analyst: {analysis.reasoning}\n"
    )


def _extract(client: genai.Client, model: str, vacancy: Vacancy, analysis: Analysis, profile: dict) -> CoverLetter:
    response = client.models.generate_content(
        model=model,
        contents=_build_prompt(vacancy, analysis, profile),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=CoverLetterExtraction,
            temperature=0.4,
        ),
    )
    extraction = CoverLetterExtraction.model_validate_json(response.text)
    return CoverLetter(**extraction.model_dump(), vacancy_title=vacancy.title, company=vacancy.company)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug or "vacancy"


def save_cover_letter(letter: CoverLetter, directory: Path = APPLICATIONS_DIR) -> Path:
    """Зберігає обидві версії листа в один текстовий файл. Повертає шлях до файлу."""
    directory.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()  # noqa: DTZ011 - лише для імені файлу, точна зона тут не важлива
    filename = f"{today}_{_slugify(letter.company)}_{_slugify(letter.vacancy_title)}.txt"
    path = directory / filename
    content = (
        f"Вакансія: {letter.vacancy_title}\n"
        f"Компанія: {letter.company or 'не вказано'}\n"
        f"{'=' * 60}\n\n"
        f"--- ENGLISH ---\n\n{letter.cover_letter_en}\n\n"
        f"{'=' * 60}\n\n"
        f"--- УКРАЇНСЬКОЮ ---\n\n{letter.cover_letter_uk}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def draft_cover_letter(vacancy: Vacancy, analysis: Analysis, profile: dict) -> CoverLetter:
    """Генерує чернетку супровідного листа. Повторює спроби, при повторних збоях переходить на резервну модель.

    Raises:
        ExecutorError: якщо не задано GEMINI_API_KEY або всі спроби (основна + резервна модель) провалились.
    """
    client = _client()
    last_error: Exception | None = None

    for model in (MODEL, FALLBACK_MODEL):
        for attempt in range(MAX_ATTEMPTS):
            try:
                return _extract(client, model, vacancy, analysis, profile)
            except Exception as e:  # noqa: BLE001 - будь-яка помилка LLM/парсингу веде до повтору чи fallback
                last_error = e
                logger.warning(f"Executor: спроба {attempt + 1} з моделлю {model} невдала: {e}")
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(BASE_DELAY_SECONDS * (2**attempt))

    raise ExecutorError(f"Не вдалося згенерувати супровідний лист після всіх спроб: {last_error}") from last_error
