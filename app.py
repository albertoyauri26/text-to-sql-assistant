"""Streamlit UI: ask a question, see the generated SQL, the result table and a short explanation."""
import os

import anthropic
import pandas as pd
import streamlit as st

from text2sql import assistant, db, llm

st.set_page_config(page_title="Text-to-SQL Assistant", layout="wide")
st.title("Text-to-SQL Assistant")
st.caption("Ask about the Olist Brazilian e-commerce data (~100k orders, 2016-2018) in English or Spanish. "
           "Claude writes the SQL; the app runs it on a read-only SQLite connection.")

if not db.DB_PATH.exists():
    st.error("Database not found. Build it first with `python -m text2sql.db`.")
    st.stop()

with st.sidebar:
    st.subheader("Database schema")
    st.code(db.get_schema(), language="sql")

if not os.getenv("ANTHROPIC_API_KEY"):  # llm.py already loaded .env
    st.warning("Set ANTHROPIC_API_KEY in a `.env` file (see `.env.example`) and restart the app.")
    st.stop()

# The same question in a session reuses the answer instead of paying for another API call
ask = st.cache_data(show_spinner=False)(assistant.ask)

question = st.text_input("Question", value=st.query_params.get("q", ""),
                         placeholder="Top 5 product categories by revenue in 2018")
if question:
    with st.spinner("Writing and running the query..."):
        try:
            result = ask(question)
        except (anthropic.APIError, RuntimeError, ValueError) as e:
            st.error(f"Could not get an answer: {e}")
            st.stop()
    st.code(result["sql"], language="sql", wrap_lines=True)
    if result["error"]:
        st.error(f"The query still failed after {result['attempts']} attempts: {result['error']}")
    else:
        st.dataframe(pd.DataFrame(result["rows"], columns=result["columns"]), hide_index=True)
    st.info(result["explanation"])
    st.caption(f"{result['attempts']} attempt(s) · {result['latency_s']} s · {len(result['rows'])} rows · {llm.MODEL}")
