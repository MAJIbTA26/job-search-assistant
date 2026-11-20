"""Eval-набір: вакансії з ЗАЗДАЛЕГІДЬ відомим "правильним" вердиктом, щоб перевіряти,
наскільки чесно Analyst оцінює реальні (хоч і синтетичні) тексти вакансій.

Тексти навмисно вигадані (не справжні вакансії), але побудовані так, щоб кожна
чітко потрапляла в одну категорію - без двозначності, інакше eval сам стане
ненадійним (LLM може чесно вагатися на межі apply/maybe, і це не буде помилкою
агента). Набір невеликий (5 кейсів) - цього достатньо, щоб ловити явні регресії
(наприклад, якщо після зміни промпту Analyst раптом почне казати "apply" на
вакансію з 5-річною вимогою до досвіду).
"""

from dataclasses import dataclass


@dataclass
class EvalCase:
    id: str
    raw_text: str
    expected_verdict: str
    note: str


CASES = [
    EvalCase(
        id="clear_apply_junior_python_remote",
        expected_verdict="apply",
        note="Майже ідеальний збіг: junior, remote, точний стек з профілю, досвід не вимагається.",
        raw_text="""
Junior Python Developer (Remote)

Шукаємо junior-розробника в невеликий продуктовий бекенд-стартап.
Комерційний досвід не обов'язковий - головне, впевнене знання стеку та pet-проєкти.

Обов'язкові навички:
- Python, FastAPI
- PostgreSQL, SQL
- Docker, Docker Compose
- Git, pytest
- REST API

Буде плюсом: досвід з n8n або AWS.

Формат: повністю віддалено. Англійська: B1+ (команда міжнародна, стендапи англійською).
""",
    ),
    EvalCase(
        id="clear_skip_senior_experience",
        expected_verdict="skip",
        note="Той самий стек, але 5+ років комерційного досвіду і рівень Senior - критична невідповідність.",
        raw_text="""
Senior Python Backend Developer

Потрібен Senior-розробник з 5+ роками комерційного досвіду в Python/Django.
Очікуємо глибоку експертизу в проєктуванні високонавантажених систем,
менторство junior-розробників, участь в архітектурних рішеннях.

Обов'язково:
- 5+ років комерційної розробки на Python
- Django, PostgreSQL, Redis
- Досвід проєктування мікросервісної архітектури
- Kubernetes

Офіс у Варшаві, гібридний формат (3 дні в офісі).
""",
    ),
    EvalCase(
        id="clear_skip_different_domain",
        expected_verdict="skip",
        note="Зовсім інший домен (frontend, нема Python) - очевидний skip незалежно від рівня.",
        raw_text="""
Middle Frontend Developer (React)

Шукаємо Middle Frontend-розробника для розвитку SaaS-платформи.

Обов'язково:
- 2+ роки комерційного досвіду з React
- TypeScript, Redux
- CSS-in-JS (styled-components)
- Досвід з Next.js

Офіс в Києві, гібрид.
""",
    ),
    EvalCase(
        id="maybe_junior_ai_with_some_experience",
        expected_verdict="maybe",
        note="Непогано збігається (Python, LangChain, remote), але потрібен 1 рік досвіду "
        "і RAG/vector stores, яких у профілі ще немає - реальний, але не очевидний шанс.",
        raw_text="""
Junior AI Engineer (Remote)

Шукаємо junior-інженера для розвитку внутрішнього AI-асистента на базі LLM.

Обов'язково:
- Python
- Досвід роботи з LangChain або LangGraph
- Розуміння RAG / vector stores (Pinecone, Chroma або аналоги)
- Мінімум 1 рік комерційного досвіду в розробці

Буде плюсом: Docker, досвід з Telegram-ботами.

Формат: повністю віддалено, англійська команда (B2+ бажано).
""",
    ),
    EvalCase(
        id="clear_skip_wrong_remote_and_stack",
        expected_verdict="skip",
        note="Не віддалено (лише офіс, інше місто), інший стек (Java, нема Python) - подвійна невідповідність.",
        raw_text="""
Java Backend Developer (Junior/Middle)

Запрошуємо в команду розробки корпоративної ERP-системи.

Обов'язково:
- Java, Spring Boot
- Oracle DB
- 1+ рік комерційного досвіду

Робота виключно в офісі у Варшаві, релокейт обов'язковий, видалена робота не розглядається.
""",
    ),
]
