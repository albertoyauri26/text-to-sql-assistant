"""SQLite access: build the Olist database, describe its schema, run read-only queries."""
import sqlite3
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "olist.db"
SCHEMA_SQL = Path(__file__).with_name("schema.sql")

# Everything a bad generated query can raise. Python < 3.12 reports "one statement at a time" as sqlite3.Warning.
QUERY_ERRORS = (sqlite3.Error, sqlite3.Warning, ValueError)


def build_db(raw_dir: Path = RAW_DIR, db_path: Path = DB_PATH) -> None:
    """Create the tables from schema.sql and load every Olist CSV into them."""
    csvs = sorted(raw_dir.glob("*.csv"))
    if not csvs:
        raise SystemExit(f"No CSV files in {raw_dir}. See the README for how to download the dataset.")
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
        for csv in csvs:
            table = csv.stem.removeprefix("olist_").removesuffix("_dataset")
            # Read as text and let schema.sql decide the types: SQLite column affinity converts numeric columns
            df = pd.read_csv(csv, dtype=str, encoding="utf-8-sig")
            df.to_sql(table, conn, if_exists="append", index=False)
            print(f"{table:<35} {len(df):>8,} rows")
        conn.commit()
    finally:
        conn.close()


def connect_ro(db_path: Path = DB_PATH) -> sqlite3.Connection:
    # mode=ro: SQLite itself rejects any write, whatever SQL the model produces
    return sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)


def get_schema(db_path: Path = DB_PATH, sample_rows: int = 3) -> str:
    """CREATE TABLE statements plus a few example rows per table, the prompt format from Rajkumar et al. (2022)."""
    conn = connect_ro(db_path)
    try:
        parts = []
        tables = conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
        for name, ddl in tables:
            cur = conn.execute(f'SELECT * FROM "{name}" LIMIT {sample_rows}')
            header = "\t".join(d[0] for d in cur.description)
            rows = "\n".join("\t".join(str(v)[:40] for v in row) for row in cur)
            parts.append(f"{ddl};\n/*\n{sample_rows} example rows from {name}:\n{header}\n{rows}\n*/")
        return "\n\n".join(parts)
    finally:
        conn.close()


def run_sql(sql: str, db_path: Path = DB_PATH, timeout_s: float = 10.0) -> tuple[list[str], list[tuple]]:
    """Run a single read-only statement and return (column names, rows)."""
    conn = connect_ro(db_path)
    deadline = time.monotonic() + timeout_s
    # Abort runaway queries (e.g. an accidental cross join on 100k rows) instead of hanging the app
    conn.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
    try:
        cur = conn.execute(sql)
        if cur.description is None:
            raise ValueError("Only queries that return rows are allowed.")
        return [d[0] for d in cur.description], cur.fetchall()
    except sqlite3.OperationalError as e:
        if str(e) == "interrupted":
            raise sqlite3.OperationalError(f"query timed out after {timeout_s:g}s") from e
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    build_db()
    print(f"Database written to {DB_PATH}")
