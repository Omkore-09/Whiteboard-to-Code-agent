import json
import re

from langchain_groq import ChatGroq

from app.config import CODE_MODEL
from app.state import AgentState

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
    sql = re.search(rf"{FENCE}sql\s*\n(.*?){FENCE}", text, re.S)
    py = re.search(rf"{FENCE}python\s*\n(.*?){FENCE}", text, re.S)
    if not sql or not py:
        raise ValueError("Model reply did not contain both a sql block and a python block")
    return sql.group(1).strip(), py.group(1).strip()


def generate_code(state: AgentState) -> dict:
    llm = ChatGroq(model=CODE_MODEL, temperature=0.2)
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