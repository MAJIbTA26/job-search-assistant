"""Структурні перевірки eval-набору (без реальних викликів Gemini) - ловить банальні
помилки на кшталт дубльованого id чи друкарської помилки у verdict."""

from eval.cases import CASES

VALID_VERDICTS = {"apply", "maybe", "skip"}


def test_case_ids_are_unique():
    ids = [case.id for case in CASES]
    assert len(ids) == len(set(ids))


def test_expected_verdicts_are_valid():
    for case in CASES:
        assert case.expected_verdict in VALID_VERDICTS, f"{case.id}: невідомий verdict {case.expected_verdict!r}"


def test_cases_have_non_empty_text_and_note():
    for case in CASES:
        assert case.raw_text.strip(), f"{case.id}: порожній текст вакансії"
        assert case.note.strip(), f"{case.id}: немає пояснення (note)"


def test_eval_set_covers_all_verdicts():
    """Набір має сенс лише якщо в ньому є приклади на кожен вердикт, інакше немає з чим порівнювати."""
    covered = {case.expected_verdict for case in CASES}
    assert covered == VALID_VERDICTS
