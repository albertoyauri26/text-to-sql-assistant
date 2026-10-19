"""Question in natural language -> SQL -> result, with self-correction when the query fails."""
import time

from text2sql import db, llm

SYSTEM = """You translate questions about the Olist Brazilian e-commerce database into SQLite queries.
Questions may be in English or Spanish.

Return:
- sql: one SQLite SELECT statement (CTEs allowed) that answers the question. Use only tables and columns from \
the schema below. Return only the columns the question asks for, with readable aliases.
- explanation: one or two sentences, in the language of the question, telling a non-technical reader how the \
query answers it.

Schema (CREATE TABLE statements with example rows):

{schema}"""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"sql": {"type": "string"}, "explanation": {"type": "string"}},
    "required": ["sql", "explanation"],
    "additionalProperties": False,
}


def ask(question: str, max_attempts: int = 3) -> dict:
    """Generate SQL with Claude and run it; on a database error, send the error back so Claude can fix the query."""
    start = time.perf_counter()
    system = SYSTEM.format(schema=db.get_schema())
    messages = [{"role": "user", "content": question}]
    tokens = {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0}
    for attempt in range(1, max_attempts + 1):
        response = llm.create(system, messages, ANSWER_SCHEMA)
        usage = response.usage
        tokens["input_tokens"] += usage.input_tokens + (usage.cache_read_input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
        tokens["cached_tokens"] += usage.cache_read_input_tokens or 0
        tokens["output_tokens"] += usage.output_tokens
        answer = llm.parse_json(response)
        try:
            columns, rows = db.run_sql(answer["sql"])
            error = None
            break
        except db.QUERY_ERRORS as e:
            columns, rows, error = [], [], f"{type(e).__name__}: {e}"
            messages += [
                {"role": "assistant", "content": response.content},  # full content, thinking blocks included
                {"role": "user", "content": f"The query failed with {error}\nReturn a corrected query."},
            ]
    return {
        **answer,
        "columns": columns,
        "rows": rows,
        "error": error,
        "attempts": attempt,
        "latency_s": round(time.perf_counter() - start, 2),
        **tokens,
    }
