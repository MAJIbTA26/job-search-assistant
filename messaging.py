"""Форматування текстових повідомлень для Telegram-бота.

Навмисно окремо від bot.py: ця логіка - чисті функції (вхід -> текст), без
залежності від python-telegram-bot. Їх легко тестувати без запуску бота чи
мокання Telegram API.
"""

from schema import VERDICT_LABELS, Analysis, Vacancy, Verdict


def should_notify(analysis: Analysis | None) -> bool:
    """Чи варто надсилати сповіщення користувачу - лише якщо не "пропустити"."""
    return analysis is not None and analysis.verdict != Verdict.SKIP


def format_vacancy_report(vacancy: Vacancy, analysis: Analysis | None, link: str | None = None) -> str:
    """Формує текст повідомлення: структура вакансії + вердикт (якщо є)."""
    lines = [
        f"<b>{vacancy.title}</b>",
        f"Компанія: {vacancy.company or 'не вказано'}",
        f"Рівень: {vacancy.seniority}",
        f"Віддалено: {'так' if vacancy.is_remote else 'не вказано/ні'}",
    ]
    if link:
        lines.append(f"Посилання: {link}")

    if analysis is None:
        lines.append("\nАналіз не виконано.")
        return "\n".join(lines)

    label = VERDICT_LABELS.get(analysis.verdict, analysis.verdict)
    lines += [
        "",
        f"<b>Збіг: {analysis.match_percentage}% - {label}</b>",
        f"Збігається: {', '.join(analysis.matched_skills) or '-'}",
        f"Бракує: {', '.join(analysis.missing_skills) or '-'}",
    ]
    if analysis.key_concerns:
        lines.append(f"Застереження: {', '.join(analysis.key_concerns)}")
    lines.append(f"Пояснення: {analysis.reasoning}")
    return "\n".join(lines)


def format_stats_report(stats: dict) -> str:
    """Формує текст відповіді на команду /stats."""
    lines = [f"Усього переглянуто вакансій: {stats['total']}"]
    for verdict, label in VERDICT_LABELS.items():
        count = stats["by_verdict"].get(verdict, 0)
        lines.append(f"{label}: {count}")
    return "\n".join(lines)
