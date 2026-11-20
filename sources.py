"""Джерело вакансій для автоматичного пошуку: офіційна RSS-стрічка We Work Remotely.

Чому саме цей сайт: Djinni і DOU (популярні українські борди) не мають
публічного RSS - довелося б парсити HTML без дозволу сайту, а це вже сіра зона.
We Work Remotely, навпаки, САМ надає цю стрічку для таких цілей
(https://weworkremotely.com/remote-job-rss-feed) - це звичайний, легальний RSS,
як у новинних сайтів.

Якщо згодом захочеш додати інше джерело - досить дописати ще одну функцію
на кшталт fetch_remote_jobs() нижче, яка повертає список RawVacancy.
"""

import html
import logging
import re
from dataclasses import dataclass

import feedparser

logger = logging.getLogger(__name__)

# Офіційна стрічка категорії "Programming" (бек-енд/фул-стек/фронт-енд разом).
WWR_FEED_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"


@dataclass
class RawVacancy:
    """Один запис з джерела вакансій: ще не оброблений Researcher-агентом."""

    title: str
    link: str
    raw_text: str


def _strip_html(text: str) -> str:
    """Грубо прибирає HTML-теги з опису вакансії (RSS часто містить HTML усередині)."""
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", without_tags)).strip()


def _extract_vacancies(parsed) -> list[RawVacancy]:
    """Перетворює вже розпарсений feedparser-об'єкт у список RawVacancy."""
    vacancies = []
    for entry in parsed.entries:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        description = _strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        if not title or not link:
            continue
        raw_text = f"{title}\n\n{description}\n\nПосилання: {link}"
        vacancies.append(RawVacancy(title=title, link=link, raw_text=raw_text))
    return vacancies


def parse_feed(feed_text: str) -> list[RawVacancy]:
    """Парсить уже завантажений текст RSS-стрічки (без мережі - зручно для тестів)."""
    return _extract_vacancies(feedparser.parse(feed_text))


def fetch_remote_jobs(feed_url: str = WWR_FEED_URL) -> list[RawVacancy]:
    """Завантажує RSS-стрічку по мережі і парсить її. Повертає [] (з логом), якщо мережа недоступна."""
    try:
        parsed = feedparser.parse(feed_url, request_headers={"User-Agent": "job-search-assistant/1.0"})
        if parsed.bozo and not parsed.entries:
            logger.warning(f"Не вдалося розпарсити RSS-стрічку {feed_url}: {parsed.bozo_exception}")
            return []
        return _extract_vacancies(parsed)
    except Exception as e:  # noqa: BLE001 - мережева помилка не повинна валити весь цикл перевірки
        logger.warning(f"Не вдалося завантажити RSS-стрічку {feed_url}: {e}")
        return []
