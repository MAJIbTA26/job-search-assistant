"""Orchestrator: граф станів (LangGraph), що координує агентів.

Етап 3: Researcher -> Analyst -> (Executor | кінець).
Якщо Researcher не впорався - граф одразу завершується (Analyst не викликається
без вакансії). Якщо Analyst дав вердикт "skip" - Executor не викликається
(немає сенсу писати лист на вакансію, яку й так варто пропустити).
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from analyst import AnalystError, analyze_vacancy
from candidate_profile import load_profile
from executor import ExecutorError, draft_cover_letter, save_cover_letter
from researcher import ResearcherError, research_vacancy
from schema import Analysis, CoverLetter, Vacancy, Verdict


class AssistantState(TypedDict, total=False):
    """Спільний стан, який передається між вузлами графа."""

    raw_text: str
    vacancy: Vacancy | None
    analysis: Analysis | None
    cover_letter: CoverLetter | None
    cover_letter_path: str | None
    error: str | None


def researcher_node(state: AssistantState) -> AssistantState:
    """Вузол-обгортка: викликає Researcher agent і кладе результат у стан."""
    if not state.get("raw_text", "").strip():
        return {"vacancy": None, "error": "Текст вакансії порожній"}
    try:
        vacancy = research_vacancy(state["raw_text"])
        return {"vacancy": vacancy, "error": None}
    except (ResearcherError, ValueError) as e:
        return {"vacancy": None, "error": str(e)}


def analyst_node(state: AssistantState) -> AssistantState:
    """Вузол-обгортка: порівнює вакансію з профілем кандидата (profile.json)."""
    try:
        profile = load_profile()
        analysis = analyze_vacancy(state["vacancy"], profile)
        return {"analysis": analysis, "error": None}
    except AnalystError as e:
        return {"analysis": None, "error": str(e)}


def executor_node(state: AssistantState) -> AssistantState:
    """Вузол-обгортка: пише чернетку супровідного листа і зберігає у файл."""
    try:
        profile = load_profile()
        letter = draft_cover_letter(state["vacancy"], state["analysis"], profile)
        path = save_cover_letter(letter)
        return {"cover_letter": letter, "cover_letter_path": str(path), "error": None}
    except ExecutorError as e:
        return {"cover_letter": None, "cover_letter_path": None, "error": str(e)}


def _after_researcher(state: AssistantState) -> str:
    """Умовний перехід: до Analyst лише якщо Researcher дав вакансію без помилки."""
    return "analyst" if state.get("vacancy") is not None else END


def _after_analyst(state: AssistantState) -> str:
    """Умовний перехід: до Executor лише якщо вердикт не "skip" (є сенс писати лист)."""
    analysis = state.get("analysis")
    if analysis is not None and analysis.verdict != Verdict.SKIP:
        return "executor"
    return END


def build_graph():
    """Будує граф Orchestrator: researcher -> analyst -> (executor | кінець)."""
    graph = StateGraph(AssistantState)
    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("executor", executor_node)
    graph.set_entry_point("researcher")
    graph.add_conditional_edges("researcher", _after_researcher, {"analyst": "analyst", END: END})
    graph.add_conditional_edges("analyst", _after_analyst, {"executor": "executor", END: END})
    graph.add_edge("executor", END)
    return graph.compile()


def run(raw_text: str) -> AssistantState:
    """Запускає Orchestrator на одному тексті вакансії й повертає фінальний стан."""
    app = build_graph()
    return app.invoke(
        {
            "raw_text": raw_text,
            "vacancy": None,
            "analysis": None,
            "cover_letter": None,
            "cover_letter_path": None,
            "error": None,
        }
    )
