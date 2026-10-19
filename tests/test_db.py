import sqlite3

import pytest

from text2sql import db


def test_run_sql_returns_columns_and_rows(tiny_db):
    assert db.run_sql("SELECT x FROM t ORDER BY x", tiny_db) == (["x"], [(1,), (2,), (3,)])


def test_run_sql_rejects_writes(tiny_db):
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        db.run_sql("DELETE FROM t", tiny_db)


def test_run_sql_rejects_multiple_statements(tiny_db):
    with pytest.raises(db.QUERY_ERRORS):
        db.run_sql("SELECT 1; DROP TABLE t", tiny_db)


def test_run_sql_times_out(tiny_db):
    endless = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT count(*) FROM n"
    with pytest.raises(sqlite3.OperationalError, match="timed out"):
        db.run_sql(endless, tiny_db, timeout_s=0.2)


def test_schema_has_ddl_and_example_rows(tiny_db):
    schema = db.get_schema(tiny_db)
    assert "CREATE TABLE t (x INTEGER);" in schema
    assert "3 example rows from t" in schema
