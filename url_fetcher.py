"""Завантажує текст вакансії за посиланням (коли в бот кидають не текст, а URL).

Чесне обмеження: це простий HTTP-запит (requests), без браузера і без виконання
JavaScript. Сайти, що рендерять вміст через JS, вимагають логін (LinkedIn - саме
такий) або блокують "ботів" без заголовків справжнього браузера - можуть
повернути порожню/неповну сторінку. У такому разі краще скопіювати текст
вакансії вручну і вставити його прямо в чат, як звичайний текст.
"""

import re

import requests
from bs4 import BeautifulSoup

MAX_CHARS = 6000
_URL_PATTERN = re.compile(r"^https?://\S+$")

_NOISE_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "svg"]


class FetchError(RuntimeError):
    """Не вдалося завантажити чи розпарсити сторінку за посиланням."""


def looks_like_url(text: str) -> bool:
    """Чи виглядає повідомлення як одне-єдине посилання (а не текст вакансії)."""
    return bool(_URL_PATTERN.match(text.strip()))


def fetch_page_text(url: str, timeout: int = 15) -> str:
    """Завантажує сторінку і повертає її видимий текст (без тегів, скриптів, стилів).

    Raises:
        FetchError: мережева помилка, HTTP-помилка, або на сторінці не знайшлося тексту.
    """
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; job-search-assistant/1.0)"},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise FetchError(f"не вдалося завантажити сторінку: {e}") from e

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    text = re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()
    if not text:
        raise FetchError("сторінка порожня (можливо, потрібен логін або JavaScript-рендеринг)")

    return text[:MAX_CHARS]
