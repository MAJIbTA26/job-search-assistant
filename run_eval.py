"""Прогін eval-набору (eval/cases.py) через СПРАВЖНІЙ Researcher + Analyst (реальні
виклики Gemini - це не pytest-тест, тут навмисно НЕ мокається LLM).

Мета: ловити регресії якості Analyst - наприклад, якщо після зміни промпту він
раптом почне казати "apply" на вакансію з явно завищеними вимогами. pytest
(tests/test_analyst.py) перевіряє КОД (retry, fallback, схему), а цей скрипт
перевіряє ЯКІСТЬ ОЦІНКИ - дві різні речі.

Використання:
    python run_eval.py

Потребує GEMINI_API_KEY в .env (реальні виклики, хоч і дешевою моделлю).
"""

from analyst import AnalystError, analyze_vacancy
from candidate_profile import load_profile
from eval.cases import CASES
from researcher import ResearcherError, research_vacancy


def run_case(case, profile: dict) -> dict:
    try:
        vacancy = research_vacancy(case.raw_text)
    except (ResearcherError, ValueError) as e:
        return {"case": case, "actual_verdict": None, "match_percentage": None, "error": f"Researcher: {e}"}

    try:
        analysis = analyze_vacancy(vacancy, profile)
    except AnalystError as e:
        return {"case": case, "actual_verdict": None, "match_percentage": None, "error": f"Analyst: {e}"}

    return {
        "case": case,
        "actual_verdict": analysis.verdict,
        "match_percentage": analysis.match_percentage,
        "error": None,
    }


def main() -> None:
    profile = load_profile()
    results = [run_case(case, profile) for case in CASES]

    print(f"{'ID':<36} {'Очікувано':<10} {'Фактично':<10} {'Збіг %':<8} {'Результат'}")
    print("-" * 85)

    correct = 0
    errors = 0
    for r in results:
        case = r["case"]
        if r["error"] is not None:
            errors += 1
            print(f"{case.id:<36} {case.expected_verdict:<10} {'ПОМИЛКА':<10} {'-':<8} {r['error']}")
            continue

        is_correct = r["actual_verdict"] == case.expected_verdict
        correct += is_correct
        mark = "правильно" if is_correct else "НЕ ЗБІГЛОСЬ"
        print(f"{case.id:<36} {case.expected_verdict:<10} {r['actual_verdict']:<10} {r['match_percentage']:<8} {mark}")

    total = len(CASES)
    evaluated = total - errors
    print("-" * 85)
    print(
        f"Разом: {total} кейсів, {errors} помилок, точність: {correct}/{evaluated}"
        if evaluated
        else "Усі кейси впали з помилкою."
    )


if __name__ == "__main__":
    main()
