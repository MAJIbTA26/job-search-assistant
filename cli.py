"""Простий запуск з командного рядка: встав текст вакансії, отримай структурований результат.

Використання:
    python cli.py
    (встав текст вакансії, завершуй порожнім рядком двічі або Ctrl+D)
"""

import sys

from orchestrator import run


def read_multiline() -> str:
    print("Встав текст вакансії, потім Ctrl+D (Windows: Ctrl+Z, Enter):")
    return sys.stdin.read()


def main() -> None:
    raw_text = read_multiline()
    result = run(raw_text)

    if result.get("error"):
        print(f"\nПомилка: {result['error']}")
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
    if analysis is None:
        print("\nАналіз не виконано (помилка Analyst-агента).")
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


if __name__ == "__main__":
    main()
