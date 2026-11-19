"""Простий запуск з командного рядка: встав текст вакансії, отримай структурований результат.

Використання:
    python cli.py
    (встав текст вакансії, завершуй порожнім рядком двічі або Ctrl+D)

Якщо PostgreSQL недоступний (контейнер не запущено) - CLI все одно працює,
просто без збереження в історію (бачиш попередження, результат показується як завжди).
"""

import sys

import db
from orchestrator import run


def read_multiline() -> str:
    print("Встав текст вакансії, потім Ctrl+D (Windows: Ctrl+Z, Enter):")
    return sys.stdin.read()


def _connect_to_db():
    """Повертає з'єднання з базою або None, якщо база недоступна (не блокує роботу CLI)."""
    try:
        conn = db.get_connection()
        db.init_db(conn)
        return conn
    except db.DatabaseError as e:
        print(f"[попередження] База даних недоступна, історія не зберігається: {e}")
        return None


def main() -> None:
    raw_text = read_multiline()
    conn = _connect_to_db()

    if conn is not None and raw_text.strip() and db.already_processed(conn, raw_text):
        print("\n[примітка] Цю вакансію вже аналізували раніше (бачив однаковий текст).")

    result = run(raw_text)

    if result.get("error") and result.get("vacancy") is None:
        print(f"\nПомилка: {result['error']}")
        if conn is not None:
            conn.close()
        return

    vacancy = result["vacancy"]
    print("\n--- Структурована вакансія ---")
    print(f"Назва: {vacancy.title}")
    print(f"Компанія: {vacancy.company or 'не вказано'}")
    print(f"Віддалено: {'так' if vacancy.is_remote else 'не вказано/ні'}")
    print(f"Рівень: {vacancy.seniority}")
    print(f"Обов'язкові навички: {', '.join(vacancy.required_skills)}")
    print(f"Бажані навички: {', '.join(vacancy.nice_to_have_skills) or '-'}")
    print(f"Мін. досвід (років): {vacancy.min_years_experience or 'не вказано'}")
    print(f"Англійська: {vacancy.english_level_required or 'не вказано'}")

    analysis = result.get("analysis")
    cover_letter_path = result.get("cover_letter_path")

    if conn is not None:
        try:
            db.save_result(conn, raw_text, vacancy, analysis, cover_letter_path)
        except db.DatabaseError as e:
            print(f"[попередження] Не вдалося зберегти в історію: {e}")
        finally:
            conn.close()

    if analysis is None:
        print(f"\nАналіз не виконано: {result.get('error') or 'помилка Analyst-агента'}")
        return

    verdict_labels = {
        "apply": "ВІДГУКНУТИСЬ",
        "maybe": "МОЖНА СПРОБУВАТИ",
        "skip": "ПРОПУСТИТИ",
    }
    print("\n--- Вердикт ---")
    print(f"Збіг: {analysis.match_percentage}%")
    print(f"Рішення: {verdict_labels.get(analysis.verdict, analysis.verdict)}")
    print(f"Збігається: {', '.join(analysis.matched_skills) or '-'}")
    print(f"Бракує: {', '.join(analysis.missing_skills) or '-'}")
    if analysis.key_concerns:
        print(f"Застереження: {', '.join(analysis.key_concerns)}")
    print(f"Пояснення: {analysis.reasoning}")

    if analysis.verdict == "skip":
        print("\nЛист не пишемо - вердикт 'пропустити'.")
        return

    if cover_letter_path is None:
        print(f"\nЛист не згенеровано: {result.get('error') or 'невідома помилка Executor-агента'}")
        return

    print(f"\n--- Супровідний лист збережено: {cover_letter_path} ---")


if __name__ == "__main__":
    main()
