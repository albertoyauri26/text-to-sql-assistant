import sqlite3

import pytest


@pytest.fixture
def tiny_db(tmp_path):
    """A 3-row database so tests run without the Olist data or an API key."""
    path = tmp_path / "tiny.db"
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE t (x INTEGER); INSERT INTO t VALUES (1), (2), (3);")
    conn.close()
    return path
