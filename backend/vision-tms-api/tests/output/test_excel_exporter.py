from src.output.excel_exporter import _format_sequence


def test_format_sequence_uses_plain_task_names() -> None:
    assert _format_sequence(["Chassi", "Montagem", "Porca"]) == "Chassi, Montagem, Porca"


def test_format_sequence_removes_leading_arrows_from_task_names() -> None:
    assert _format_sequence(["-> Chassi", " -> Montagem", "Porca"]) == "Chassi, Montagem, Porca"


def test_format_sequence_skips_empty_steps() -> None:
    assert _format_sequence(["", "  ", "Chassi"]) == "Chassi"
