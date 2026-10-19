"""Use Claude to write a question -> SQL benchmark, keeping only pairs whose SQL runs and returns a small result."""
import json

from text2sql import db, llm

EVAL_PATH = db.ROOT / "data" / "eval_set.json"
PER_LEVEL = 17  # 3 levels x 17 = 51 candidates before validation

LEVELS = {
    "easy": "one table only: filters, COUNT / SUM / AVG, DISTINCT, ORDER BY ... LIMIT",
    "medium": "JOINs across 2-3 tables combined with GROUP BY, HAVING or ORDER BY",
    "hard": "subqueries or CTEs, window functions (RANK, ROW_NUMBER, LAG, running totals) and date logic "
            "with strftime / julianday; most should join 3+ tables",
}

SYSTEM = """You write text-to-SQL benchmark items for the SQLite database below.

Schema (CREATE TABLE statements with example rows):

{schema}"""

PROMPT = """Write {n} diverse, realistic business questions a manager could ask about this e-commerce data, each with \
the SQLite query that answers it correctly.

Difficulty: {level} - {description}.

Rules:
- Write about one third of the questions in Spanish and the rest in English.
- Each question must have exactly one reasonable interpretation: say which columns to return, the time period, \
the order or ranking rule, and the rounding when it matters.
- Each query must return between 1 and 50 rows.
- Cover different tables and business topics, including a few about payment methods and installment plans \
(order_payments.payment_installments); do not repeat questions."""

ITEMS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"question": {"type": "string"}, "sql": {"type": "string"}},
                "required": ["question", "sql"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def validate(sql: str) -> str | None:
    """Return why a gold query is unusable, or None if it is a valid test case."""
    try:
        _, rows = db.run_sql(sql)
    except db.QUERY_ERRORS as e:
        return f"{type(e).__name__}: {e}"
    return None if 1 <= len(rows) <= 50 else f"{len(rows)} rows"


def main() -> None:
    system = SYSTEM.format(schema=db.get_schema())
    kept, dropped = [], 0
    for level, description in LEVELS.items():
        prompt = PROMPT.format(n=PER_LEVEL, level=level, description=description)
        # High effort: wrong gold SQL silently corrupts the benchmark, so it is worth more thinking than the assistant
        response = llm.create(system, [{"role": "user", "content": prompt}], ITEMS_SCHEMA, effort="high")
        for item in llm.parse_json(response)["items"]:
            reason = validate(item["sql"])
            if reason:
                dropped += 1
                print(f"DROP [{level}] {reason}: {item['question']}")
            else:
                kept.append({"id": len(kept) + 1, "difficulty": level, **item})
    EVAL_PATH.write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Kept {len(kept)} pairs, dropped {dropped}. Written to {EVAL_PATH}")


if __name__ == "__main__":
    main()
