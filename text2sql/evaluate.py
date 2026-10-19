"""Execution-accuracy evaluation: run the assistant on every benchmark question and compare result sets."""
import json
import sys

import anthropic
import pandas as pd

from text2sql import assistant, db
from text2sql.generate_eval import EVAL_PATH

RESULTS_DIR = db.ROOT / "results"
LEVELS = ["easy", "medium", "hard"]


def _normalize(rows: list[tuple]) -> list[tuple]:
    # shortcut: ignores row order, column order and column names (a result's values must match exactly, numbers
    # to 2 decimals); questions whose answer depends on ORDER BY would need an order-aware comparison
    def value(v):
        return round(float(v), 2) if isinstance(v, (int, float)) else v

    return sorted((tuple(sorted(map(value, row), key=repr)) for row in rows), key=repr)


def results_match(expected: list[tuple], actual: list[tuple]) -> bool:
    return _normalize(expected) == _normalize(actual)


def main(limit: int | None = None) -> None:
    items = json.loads(EVAL_PATH.read_text(encoding="utf-8"))[:limit]
    records = []
    for item in items:
        _, expected = db.run_sql(item["sql"])
        try:
            result = assistant.ask(item["question"])
        except (anthropic.APIError, RuntimeError, ValueError) as e:
            # One failed API call must not throw away the rest of the run
            result = {"sql": "", "rows": [], "error": f"{type(e).__name__}: {e}", "attempts": 0}
        match = result["error"] is None and results_match(expected, result["rows"])
        records.append({
            "id": item["id"],
            "difficulty": item["difficulty"],
            "question": item["question"],
            "match": match,
            "attempts": result["attempts"],
            "error": result["error"],
            "latency_s": result.get("latency_s"),
            "input_tokens": result.get("input_tokens"),
            "cached_tokens": result.get("cached_tokens"),
            "output_tokens": result.get("output_tokens"),
            "gold_sql": item["sql"],
            "predicted_sql": result["sql"],
        })
        print(f"[{item['id']:>2}] {item['difficulty']:<6} {'PASS' if match else 'FAIL'} "
              f"({result['attempts']} attempt(s)) {item['question'][:80]}")

    df = pd.DataFrame(records)
    df["first_try_match"] = df["match"] & (df["attempts"] == 1)
    RESULTS_DIR.mkdir(exist_ok=True)
    df.to_csv(RESULTS_DIR / "eval_results.csv", index=False)

    def summarize(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "questions": len(g),
            "accuracy_%": round(100 * g["match"].mean(), 1),
            "first_try_accuracy_%": round(100 * g["first_try_match"].mean(), 1),
            "needed_retry": int((g["attempts"] > 1).sum()),
            "avg_latency_s": round(g["latency_s"].mean(), 1),
        })

    summary = df.groupby("difficulty").apply(summarize, include_groups=False)
    summary = summary.loc[[lvl for lvl in LEVELS if lvl in summary.index]]
    summary.loc["overall"] = summarize(df)
    summary = summary.astype({"questions": int, "needed_retry": int})
    summary.to_csv(RESULTS_DIR / "summary.csv")
    print(summary.to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
