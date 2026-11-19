"""Researcher agent: перетворює сирий текст вакансії на структуровані дані (Vacancy).

Логіка навмисно схожа на classifier.py з Request Classifier: structured output
через Gemini, повтори з exponential backoff, резервна модель при збої основної.
"""

import logging
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from schema import Vacancy, VacancyExtraction

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "gemini-flash-lite-latest"
FALLBACK_MODEL = "gemini-flash-latest"
MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 3

SYSTEM_PROMPT = """Ти уважно читаєш текст вакансії та витягуєш з нього структуровані дані.
Не вигадуй те, чого немає в тексті: якщо щось не вказано, залишай порожнім/null/false.
Мова полів вільна (можна українською чи англійською, як зручніше), але точно відображай факти з тексту."""


class ResearcherError(RuntimeError):
    """Не вдалося структурувати вакансію (конфігурація або LLM недоступна після всіх спроб)."""


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ResearcherError("GEMINI_API_KEY не задано")
    return genai.Client(api_key=api_key)


def _extract(client: genai.Client, model: str, raw_text: str) -> Vacancy:
    response = client.models.generate_content(
        model=model,
        contents=f"Текст вакансії:\n\n{raw_text}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=VacancyExtraction,
            temperature=0,
        ),
    )
    extraction = VacancyExtraction.model_validate_json(response.text)
    # source_text завжди береться з оригіналу, а не з того, що могла повторити модель.
    return Vacancy(**extraction.model_dump(), source_text=raw_text)


def research_vacancy(raw_text: str) -> Vacancy:
    """Структурує текст вакансії. Повторює спроби, при повторних збоях переходить на резервну модель.

    Raises:
        ResearcherError: якщо не задано GEMINI_API_KEY або всі спроби (основна + резервна модель) провалились.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text не може бути порожнім")

    client = _client()
    last_error: Exception | None = None

    for model in (MODEL, FALLBACK_MODEL):
        for attempt in range(MAX_ATTEMPTS):
            try:
                return _extract(client, model, raw_text)
            except Exception as e:  # noqa: BLE001 - будь-яка помилка LLM/парсингу веде до повтору чи fallback
                last_error = e
                logger.warning(f"Researcher: спроба {attempt + 1} з моделлю {model} невдала: {e}")
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(BASE_DELAY_SECONDS * (2**attempt))

    raise ResearcherError(f"Не вдалося структурувати вакансію після всіх спроб: {last_error}") from last_error
