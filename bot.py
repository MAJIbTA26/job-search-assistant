"""Telegram-бот: два режими роботи в одному процесі.

1. Встав текст вакансії прямо в чат боту - отримаєш структуру + вердикт + лист
   (той самий Orchestrator, що й у cli.py).
2. Бот сам періодично (CHECK_INTERVAL_HOURS, за замовчуванням 4 години)
   перевіряє RSS-стрічку remote-вакансій (sources.py) і сам пише тобі, якщо
   знайшов щось із вердиктом "apply" чи "maybe".

Запуск:
    python bot.py
Потрібно в .env:
    TELEGRAM_BOT_TOKEN - токен від @BotFather
    TELEGRAM_CHAT_ID   - твій chat_id (дізнаєшся командою /start при першому запуску)
    CHECK_INTERVAL_HOURS - необов'язково, за замовчуванням 4
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import db
from candidate_profile import load_profile
from messaging import format_stats_report, format_vacancy_report, should_notify
from orchestrator import run
from sources import fetch_remote_jobs
from url_fetcher import FetchError, fetch_page_text, looks_like_url

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL_HOURS = 4
MAX_VACANCIES_PER_CHECK = 5  # щоб один прогін не "з'їв" забагато викликів Gemini одразу
AUTO_CHECK_JOB_NAME = "check_new_vacancies"


def _check_interval_hours() -> float:
    return float(os.getenv("CHECK_INTERVAL_HOURS", DEFAULT_CHECK_INTERVAL_HOURS))


def _target_chat_id() -> int | None:
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return int(chat_id) if chat_id else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = (
        f"Привіт! Твій chat_id: <code>{chat_id}</code>\n"
        "Якщо хочеш автоматичні сповіщення про нові вакансії - додай цей chat_id "
        "у .env як TELEGRAM_CHAT_ID і перезапусти бота.\n\n"
        "Команди:\n"
        "/stats - статистика по переглянутих вакансіях\n"
        "/interval &lt;години&gt; - змінити, як часто бот сам шукає вакансії\n\n"
        "Встав текст вакансії або посилання на неї сюди - проаналізую одразу "
        "(деякі сайти з логіном, напр. LinkedIn, можуть не відкритись за посиланням - "
        "тоді встав текст вручну)."
    )
    await update.message.reply_html(text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        conn = db.get_connection()
        db.init_db(conn)
        report = format_stats_report(db.get_stats(conn))
        conn.close()
    except db.DatabaseError as e:
        report = f"База даних недоступна: {e}"
    await update.message.reply_text(report)


async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].replace(".", "", 1).isdigit():
        await update.message.reply_text("Використання: /interval <години>, наприклад /interval 6")
        return

    hours = float(context.args[0])
    for job in context.job_queue.get_jobs_by_name(AUTO_CHECK_JOB_NAME):
        job.schedule_removal()
    context.job_queue.run_repeating(check_new_vacancies, interval=hours * 3600, first=5, name=AUTO_CHECK_JOB_NAME)
    await update.message.reply_text(f"Готово, тепер перевіряю нові вакансії кожні {hours} год.")


async def handle_pasted_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw_text = update.message.text

    if looks_like_url(raw_text):
        await update.message.reply_text("Завантажую сторінку за посиланням...")
        try:
            raw_text = await asyncio.to_thread(fetch_page_text, raw_text)
        except FetchError as e:
            await update.message.reply_text(
                f"Не вдалося завантажити вакансію за посиланням ({e}).\n"
                "Деякі сайти (напр. LinkedIn) блокують прості запити або вимагають логін - "
                "у такому разі скопіюй текст вакансії вручну і встав його сюди."
            )
            return

    result = await asyncio.to_thread(run, raw_text)

    if result.get("error") and result.get("vacancy") is None:
        await update.message.reply_text(f"Помилка: {result['error']}")
        return

    vacancy = result["vacancy"]
    analysis = result.get("analysis")
    cover_letter_path = result.get("cover_letter_path")

    try:
        conn = db.get_connection()
        db.init_db(conn)
        db.save_result(conn, raw_text, vacancy, analysis, cover_letter_path)
        conn.close()
    except db.DatabaseError as e:
        logger.warning(f"Не вдалося зберегти в історію: {e}")

    await update.message.reply_html(format_vacancy_report(vacancy, analysis))

    if cover_letter_path:
        content = await asyncio.to_thread(Path(cover_letter_path).read_bytes)
        await update.message.reply_document(content, filename=os.path.basename(cover_letter_path))


async def check_new_vacancies(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Періодична задача: нові вакансії зі стрічки -> Orchestrator -> сповіщення, якщо збіг."""
    chat_id = _target_chat_id()
    if chat_id is None:
        logger.info("TELEGRAM_CHAT_ID не задано - автоматичний пошук пропущено (нема кому писати).")
        return

    candidates = await asyncio.to_thread(fetch_remote_jobs)
    if not candidates:
        logger.info("Нових вакансій зі стрічки не отримано (мережа чи порожня стрічка).")
        return

    try:
        conn = db.get_connection()
        db.init_db(conn)
    except db.DatabaseError as e:
        logger.warning(f"База недоступна, автоматичний пошук пропущено: {e}")
        return

    processed_this_run = 0
    for candidate in candidates:
        if processed_this_run >= MAX_VACANCIES_PER_CHECK:
            break
        if db.already_processed(conn, candidate.raw_text):
            continue

        processed_this_run += 1
        result = await asyncio.to_thread(run, candidate.raw_text)
        vacancy = result.get("vacancy")
        if vacancy is None:
            continue  # Researcher не впорався з цим записом - пропускаємо, не зберігаючи

        analysis = result.get("analysis")
        cover_letter_path = result.get("cover_letter_path")
        db.save_result(conn, candidate.raw_text, vacancy, analysis, cover_letter_path)

        if should_notify(analysis):
            text = format_vacancy_report(vacancy, analysis, link=candidate.link)
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            if cover_letter_path:
                content = await asyncio.to_thread(Path(cover_letter_path).read_bytes)
                await context.bot.send_document(
                    chat_id=chat_id, document=content, filename=os.path.basename(cover_letter_path)
                )

    conn.close()
    logger.info(f"Автоматичний пошук завершено: перевірено {processed_this_run} нових вакансій.")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задано в .env")

    load_profile()  # падає одразу з зрозумілою помилкою, якщо profile.json зіпсований

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("interval", set_interval))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pasted_vacancy))

    application.job_queue.run_repeating(
        check_new_vacancies, interval=_check_interval_hours() * 3600, first=10, name=AUTO_CHECK_JOB_NAME
    )

    logger.info("Бот запущений, очікую повідомлення...")
    application.run_polling()


if __name__ == "__main__":
    main()
