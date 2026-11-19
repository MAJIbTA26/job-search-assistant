"""Тести db.py з фейковим psycopg-з'єднанням (справжньої бази даних не потрібно)."""

import pytest

import db
from schema import Analysis, Vacancy


def make_vacancy(**overrides) -> Vacancy:
    data = {
        "title": "Junior Python Developer",
        "company": "Acme",
        "is_remote": True,
        "seniority": "Junior",
        "required_skills": ["Python"],
        "nice_to_have_skills": [],
        "min_years_experience": None,
        "english_level_required": "",
        "source_text": "текст",
    }
    data.update(overrides)
    return Vacancy(**data)


def make_analysis(**overrides) -> Analysis:
    data = {
        "match_percentage": 70,
        "verdict": "apply",
        "matched_skills": ["Python"],
        "missing_skills": [],
        "key_concerns": [],
        "reasoning": "Збіг хороший.",
        "vacancy_title": "Junior Python Developer",
    }
    data.update(overrides)
    return Analysis(**data)


class FakeCursor:
    """Імітує psycopg-курсор: пам'ятає кожен виконаний запит і простий in-memory стан рядків."""

    def __init__(self, store: dict):
        self.store = store  # {source_hash: row_dict}
        self.executed = []
        self._last_result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, params=None):
        self.executed.append((query, params))
        normalized = " ".join(query.split())

        if normalized.startswith("CREATE TABLE"):
            self._last_result = None
        elif normalized.startswith("SELECT 1 FROM vacancy_history"):
            source_hash = params[0]
            self._last_result = (1,) if source_hash in self.store else None
        elif normalized.startswith("INSERT INTO vacancy_history"):
            source_hash, title, company, match_pct, verdict, letter_path = params
            self.store[source_hash] = {
                "vacancy_title": title,
                "company": company,
                "match_percentage": match_pct,
                "verdict": verdict,
                "cover_letter_path": letter_path,
            }
            self._last_result = None
        elif normalized.startswith("SELECT COUNT(*) FROM vacancy_history"):
            self._last_result = (len(self.store),)
        elif normalized.startswith("SELECT verdict, COUNT(*)"):
            counts: dict[str, int] = {}
            for row in self.store.values():
                counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
            self._rows = list(counts.items())
        else:
            raise AssertionError(f"Неочікуваний запит у тесті: {normalized}")

    def fetchone(self):
        return self._last_result

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, store=None):
        self.store = store if store is not None else {}
        self.committed = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self.store)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_compute_source_hash_is_stable_and_trims_whitespace():
    assert db.compute_source_hash("  текст вакансії  ") == db.compute_source_hash("текст вакансії")


def test_compute_source_hash_differs_for_different_text():
    assert db.compute_source_hash("вакансія А") != db.compute_source_hash("вакансія Б")


def test_init_db_creates_table_and_commits():
    conn = FakeConnection()

    db.init_db(conn)

    assert conn.committed is True


def test_already_processed_false_for_new_text():
    conn = FakeConnection()

    assert db.already_processed(conn, "нова вакансія") is False


def test_save_result_then_already_processed_true():
    conn = FakeConnection()
    vacancy = make_vacancy()
    analysis = make_analysis()

    db.save_result(conn, "текст вакансії", vacancy, analysis, "applications/letter.txt")

    assert db.already_processed(conn, "текст вакансії") is True
    assert conn.committed is True


def test_save_result_handles_missing_analysis():
    conn = FakeConnection()
    vacancy = make_vacancy()

    db.save_result(conn, "текст вакансії", vacancy, None, None)

    saved = next(iter(conn.store.values()))
    assert saved["match_percentage"] is None
    assert saved["verdict"] is None


def test_get_stats_counts_by_verdict():
    conn = FakeConnection()
    db.save_result(conn, "вакансія 1", make_vacancy(title="A"), make_analysis(verdict="apply"), None)
    db.save_result(conn, "вакансія 2", make_vacancy(title="B"), make_analysis(verdict="skip"), None)
    db.save_result(conn, "вакансія 3", make_vacancy(title="C"), make_analysis(verdict="skip"), None)

    stats = db.get_stats(conn)

    assert stats["total"] == 3
    assert stats["by_verdict"] == {"apply": 1, "skip": 2}


def test_get_connection_wraps_operational_error(monkeypatch):
    def broken_connect(url):
        raise db.psycopg.OperationalError("не вдалося з'єднатися")

    monkeypatch.setattr(db.psycopg, "connect", broken_connect)

    with pytest.raises(db.DatabaseError):
        db.get_connection()
