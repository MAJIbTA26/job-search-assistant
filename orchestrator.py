"""Orchestrator: граф станів (LangGraph), що координує агентів.

Етап 1: лише Researcher. Наступні етапи додадуть вузли Analyst і Executor
у цей самий граф, Orchestrator не потрібно буде переписувати з нуля.
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from researcher import ResearcherError, research_vacancy
from schema import Vacancy


class AssistantState(TypedDict, total=False):
    """Спільний стан, який передається між вузлами графа."""

    raw_text: str
    vacancy: Vacancy | None
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


def build_graph():
    """Будує граф Orchestrator. Етап 1: один вузол researcher."""
    graph = StateGraph(AssistantState)
    graph.add_node("researcher", researcher_node)
    graph.set_entry_point("researcher")
    graph.add_edge("researcher", END)
    return graph.compile()


def run(raw_text: str) -> AssistantState:
    """Запускає Orchestrator на одному тексті вакансії й повертає фінальний стан."""
    app = build_graph()
    return app.invoke({"raw_text": raw_text, "vacancy": None, "error": None})
