import json
import re

from langchain_groq import ChatGroq

from app.config import CODE_MODEL
from app.state import AgentState

SQL_LANGS = {"sql", "postgresql", "postgres", "psql", "pgsql"}
PY_LANGS = {"python", "py", "python3"}
FENCE = "`" * 3

SYSTEM = f"""You are a senior backend engineer. From the ER model below produce two files.

Reply with exactly two fenced code blocks and nothing else:
1. a {FENCE}sql block containing schema.sql
2. a {FENCE}python block containing api.py

schema.sql rules (PostgreSQL DDL):
- Only plain CREATE TABLE statements. No schema prefix, no CREATE EXTENSION, no DROP, no INSERT.
- snake_case names. Every table gets `id bigint generated always as identity primary key`.
- Real FOREIGN KEY constraints, tables created in dependency order.
- A relation of kind many-to-many MUST become a junction table. Never add a foreign key
  column to one of the entities for a many-to-many relation.
- If two entities have several relations, create one junction table per relation,
  named after the relation.

api.py rules: a single-file FastAPI skeleton using Pydantic v2 (model_dump, no orm_mode),
with GET (list) and POST (create) routes per table. Route bodies can be stubs with a
`# TODO: db` comment."""


def _extract(text: str) -> tuple[str, str]:
    blocks = re.findall(rf"{FENCE}[ \t]*([\w+-]*)[ \t]*\n(.*?)(?:{FENCE}|\Z)", text, re.S)
    sql = py = None
    for lang, body in blocks:
        body, lang = body.strip(), lang.lower()
        if lang in SQL_LANGS:
            sql = sql or body
        elif lang in PY_LANGS:
            py = py or body
        elif "create table" in body.lower():
            sql = sql or body
        elif "fastapi" in body.lower():
            py = py or body
    if not sql or not py:
        raise ValueError(f"Model reply is missing a sql or python block. Reply began: {text[:200]!r}")
    return sql, py


def generate_code(state: AgentState) -> dict:
    llm = ChatGroq(model=CODE_MODEL, temperature=0.2, max_tokens=8000)
    prompt = f"{SYSTEM}\n\nER model (JSON):\n{json.dumps(state['parsed_diagram'], indent=2)}"

    if state.get("errors"):
        prev = state.get("files", {})
        prompt += (
            "\n\nYour previous attempt failed validation. Fix what the errors point to.\n"
            "Errors:\n" + "\n".join(state["errors"])
            + f"\n\nPrevious schema.sql:\n{prev.get('schema.sql', '')}"
            + f"\n\nPrevious api.py:\n{prev.get('api.py', '')}"
        )

    sql, py = _extract(llm.invoke(prompt).content)
    return {
        "files": {"schema.sql": sql, "api.py": py},
        "retries": state.get("retries", 0) + 1,
    }