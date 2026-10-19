import json
from functools import partial
from types import SimpleNamespace

from text2sql import assistant, db, llm


def fake_response(sql):
    """Mimics the parts of an Anthropic Message the assistant reads."""
    return SimpleNamespace(
        stop_reason="end_turn",
        stop_details=None,
        content=[SimpleNamespace(type="text", text=json.dumps({"sql": sql, "explanation": "..."}))],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0),
    )


def test_failed_query_is_retried_with_the_error(monkeypatch, tiny_db):
    responses = iter([fake_response("SELECT missing_column FROM t"), fake_response("SELECT x FROM t")])
    calls = []

    def fake_create(system, messages, schema, **kwargs):
        calls.append(list(messages))
        return next(responses)

    monkeypatch.setattr(llm, "create", fake_create)
    monkeypatch.setattr(db, "run_sql", partial(db.run_sql, db_path=tiny_db))
    monkeypatch.setattr(db, "get_schema", partial(db.get_schema, db_path=tiny_db))

    result = assistant.ask("How many rows?")

    assert result["attempts"] == 2
    assert result["error"] is None
    assert result["rows"] == [(1,), (2,), (3,)]
    assert "no such column: missing_column" in calls[1][-1]["content"]


def test_gives_up_after_max_attempts(monkeypatch, tiny_db):
    monkeypatch.setattr(llm, "create", lambda *a, **k: fake_response("SELECT nope FROM t"))
    monkeypatch.setattr(db, "run_sql", partial(db.run_sql, db_path=tiny_db))
    monkeypatch.setattr(db, "get_schema", partial(db.get_schema, db_path=tiny_db))

    result = assistant.ask("?", max_attempts=2)

    assert result["attempts"] == 2
    assert "no such column" in result["error"]
