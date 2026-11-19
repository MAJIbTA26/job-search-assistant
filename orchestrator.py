"""Orchestrator: граф станів (LangGraph), що координує агентів.

Етап 2: Researcher -> Analyst. Якщо Researcher не впорався (помилка, порожній
текст), граф одразу завершується - Analyst не викликається без вакансії.
Executor (етап 3) додасться сюди ж, тим самим способом.
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from analyst import AnalystError, analyze_vacancy
from candidate_profile import load_profile
from researcher import ResearcherError, research_vacancy
from schema import Analysis, Vacancy


class AssistantState(TypedDict, total=False):
    """Спільний стан, який передається між вузлами графа."""

    raw_text: str
    vacancy: Vacancy | None
    analysis: Analysis | None
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


def _after_researcher(state: AssistantState) -> str:
    """Умовний перехід: до Analyst лише якщо Researcher дав вакансію без помилки."""
    return "analyst" if state.get("vacancy") is not None else END


def build_graph():
    """Будує граф Orchestrator: researcher -> (analyst | кінець при помилці)."""
    graph = StateGraph(AssistantState)
    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.set_entry_point("researcher")
    graph.add_conditional_edges("researcher", _after_researcher, {"analyst": "analyst", END: END})
    graph.add_edge("analyst", END)
    return graph.compile()


def run(raw_text: str) -> AssistantState:
    """Запускає Orchestrator на одному тексті вакансії й повертає фінальний стан."""
    app = build_graph()
    return app.invoke({"raw_text": raw_text, "vacancy": None, "analysis": None, "error": None})
