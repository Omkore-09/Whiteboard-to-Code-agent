import re

from app.state import AgentState

REL = {"one-to-one": "||--||", "one-to-many": "||--o{", "many-to-many": "}o--o{"}
FENCE = "`" * 3


def _id(s: str) -> str:
    return re.sub(r"\W+", "_", s).strip("_") or "x"


def build_mermaid(d: dict) -> str:
    lines = ["erDiagram"]
    for e in d["entities"]:
        lines.append(f"    {_id(e['name']).upper()} {{")
        for c in e["columns"]:
            lines.append(f"        {_id(c['type'])} {_id(c['name'])}")
        lines.append("    }")
    for r in d["relations"]:
        sym = REL.get(r["kind"], "}o--o{")
        label = r.get("name") or "relates"
        lines.append(f'    {_id(r["from_entity"]).upper()} {sym} {_id(r["to_entity"]).upper()} : "{label}"')
    return "\n".join(lines)


def build_readme(state: AgentState) -> dict:
    files = dict(state["files"])
    warn = ""
    if state.get("errors"):
        warn = "> Validation errors remained after retries:\n" + "\n".join(
            f"> - {e}" for e in state["errors"]) + "\n\n"
    files["README.md"] = (
        "# Generated from whiteboard diagram\n\n"
        f"{warn}## ER diagram\n\n{FENCE}mermaid\n{build_mermaid(state['parsed_diagram'])}\n{FENCE}\n\n"
        "## Files\n- `schema.sql`: PostgreSQL schema\n- `api.py`: FastAPI skeleton\n"
    )
    return {"files": files}