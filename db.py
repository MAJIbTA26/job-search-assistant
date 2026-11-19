"""Зберігає історію переглянутих вакансій і рішень у PostgreSQL.

Навмисно окремо від агентів (researcher.py/analyst.py/executor.py): агенти
залишаються "чистими" (текст на вході, структуровані дані на виході), а запис
в базу - окрема відповідальність, яку викликає cli.py після того, як
Orchestrator уже віддав результат.
"""

import hashlib
import logging
import os

import psycopg
from dotenv import load_dotenv

from schema import Analysis, Vacancy

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "postgresql://job_agent:job_agent@localhost:5434/job_agent"


class DatabaseError(RuntimeError):
    """Не вдалося виконати операцію з базою даних."""


def _database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_connection() -> psycopg.Connection:
    try:
        return psycopg.connect(_database_url())
    except psycopg.OperationalError as e:
        raise DatabaseError(f"Не вдалося підключитися до бази даних: {e}") from e


def init_db(conn: psycopg.Connection) -> None:
    """Створює таблицю vacancy_history, якщо вона ще не існує. Безпечно викликати повторно."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS vacancy_history (
                id SERIAL PRIMARY KEY,
                source_hash TEXT NOT NULL UNIQUE,
                vacancy_title TEXT NOT NULL,
                company TEXT,
                match_percentage INTEGER,
                verdict TEXT,
                cover_letter_path TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def compute_source_hash(raw_text: str) -> str:
    """Унікальний відбиток тексту вакансії - щоб не аналізувати один і той самий текст двічі."""
    return hashlib.sha256(raw_text.strip().encode("utf-8")).hexdigest()


def already_processed(conn: psycopg.Connection, raw_text: str) -> bool:
    """Чи вже є в історії запис з таким самим текстом вакансії."""
    source_hash = compute_source_hash(raw_text)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM vacancy_history WHERE source_hash = %s", (source_hash,))
        return cur.fetchone() is not None


def save_result(
    conn: psycopg.Connection,
    raw_text: str,
    vacancy: Vacancy,
    analysis: Analysis | None,
    cover_letter_path: str | None,
) -> None:
    """Записує результат обробки вакансії в історію. Якщо такий текст вже був - оновлює запис."""
    source_hash = compute_source_hash(raw_text)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vacancy_history
                (source_hash, vacancy_title, company, match_percentage, verdict, cover_letter_path)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_hash) DO UPDATE SET
                vacancy_title = EXCLUDED.vacancy_title,
                company = EXCLUDED.company,
                match_percentage = EXCLUDED.match_percentage,
                verdict = EXCLUDED.verdict,
                cover_letter_path = EXCLUDED.cover_letter_path
            """,
            (
                source_hash,
                vacancy.title,
                vacancy.company or None,
                analysis.match_percentage if analysis else None,
                analysis.verdict if analysis else None,
                cover_letter_path,
            ),
        )
    conn.commit()


def get_stats(conn: psycopg.Connection) -> dict:
    """Проста статистика: скільки всього вакансій, скільки по кожному вердикту."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM vacancy_history")
        total = cur.fetchone()[0]
        cur.execute("SELECT verdict, COUNT(*) FROM vacancy_history GROUP BY verdict")
        by_verdict = dict(cur.fetchall())
    return {"total": total, "by_verdict": by_verdict}
