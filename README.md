# Job Search Assistant (Multi-Agent, Stage 1)

AI-агент, що допомагає аналізувати вакансії. Архітектура: Orchestrator (LangGraph)
координує спеціалізованих агентів. На цьому етапі є лише **Researcher**: він бере
довільний текст вакансії та перетворює його у структуровані дані (назва, навички,
рівень, вимоги до досвіду й англійської).

Наступні етапи додадуть **Analyst** (оцінка % збігу з профілем) та **Executor**
(чернетка супровідного листа), без переписування Orchestrator з нуля.

## Запуск

```
pip install -r requirements.txt
cp .env.example .env   # встав свій GEMINI_API_KEY
python cli.py
```

Встав текст вакансії, заверши вводом Ctrl+D (Windows: Ctrl+Z, Enter).

## Тести

```
pytest -v
```

10 тестів, LLM замокано (реальних викликів Gemini при тестуванні немає).

## Структура

- `schema.py` — Pydantic-модель `Vacancy` (структура даних Researcher)
- `researcher.py` — агент: структурує текст через Gemini, retry + fallback-модель
- `orchestrator.py` — граф LangGraph, що координує агентів
- `cli.py` — запуск з командного рядка
