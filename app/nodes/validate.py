import ast
import re
import uuid

import psycopg

from app.config import SUPABASE_DB_URL
from app.state import AgentState


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower()).rstrip("s")


def check_fidelity(conn, schema: str, diagram: dict) -> list[str]:
    """Compare the tables Postgres actually created with the diagram."""
    cols: dict[str, set[str]] = {}
    for t, c in conn.execute(
        "select table_name, column_name from information_schema.columns where table_schema = %s",
        (schema,),
    ):
        cols.setdefault(t, set()).add(_norm(c))

    fks: dict[str, list[str]] = {}
    for t, ref in conn.execute(
        "select c.relname, r.relname from pg_constraint k "
        "join pg_class c on c.oid = k.conrelid join pg_class r on r.oid = k.confrelid "
        "where k.contype = 'f' and k.connamespace = (select oid from pg_namespace where nspname = %s)",
        (schema,),
    ):
        fks.setdefault(t, []).append(ref)

    def table_for(name: str):
        n = _norm(name)
        exact = [t for t in cols if _norm(t) == n]
        if exact:
            return exact[0]
        near = sorted((t for t in cols if n in _norm(t)), key=len)
        return near[0] if near else None

    errors: list[str] = []
    tmap: dict[str, str] = {}
    for e in diagram["entities"]:
        t = table_for(e["name"])
        if not t:
            errors.append(f"Schema does not match the diagram: no table for entity '{e['name']}'")
            continue
        tmap[e["name"]] = t
        for c in e["columns"]:
            n = _norm(c["name"])
            if not any(n == h or n in h for h in cols[t]):
                errors.append(f"Schema does not match the diagram: table '{t}' has no column for '{c['name']}'")

    need: dict[tuple, int] = {}
    for r in diagram["relations"]:
        a, b = tmap.get(r["from_entity"]), tmap.get(r["to_entity"])
        if not a or not b:
            continue
        kind = r["kind"].lower().replace("_", "-").replace(" ", "-")
        if kind == "many-to-many":
            key = tuple(sorted((a, b)))
            need[key] = need.get(key, 0) + 1
        elif b not in fks.get(a, []) and a not in fks.get(b, []):
            errors.append(
                f"Schema does not match the diagram: no foreign key between '{a}' and '{b}' "
                f"for the {kind} relation '{r.get('name') or ''}'"
            )
    for (a, b), count in need.items():
        found = sum(
            1 for refs in fks.values()
            if a in refs and b in refs and (a != b or refs.count(a) >= 2)
        )
        if found < count:
            errors.append(
                f"Schema does not match the diagram: expected {count} junction table(s) "
                f"between '{a}' and '{b}' for many-to-many relations, found {found}"
            )
    return errors


def validate_code(state: AgentState) -> dict:
    files = state["files"]
    errors: list[str] = []

    try:
        ast.parse(files["api.py"])
    except SyntaxError as e:
        errors.append(f"api.py syntax error at line {e.lineno}: {e.msg}")

    schema = f"scratch_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(SUPABASE_DB_URL, connect_timeout=15) as conn:
        with conn.transaction():
            conn.execute(f"create schema {schema}")
            conn.execute(f"set local search_path to {schema}")
            try:
                conn.execute(files["schema.sql"])
                errors += check_fidelity(conn, schema, state["parsed_diagram"])
            except psycopg.OperationalError:
                raise  # connection or config problem: the model can't fix this
            except psycopg.Error as e:
                errors.append(f"schema.sql SQL error: {e}")
            raise psycopg.Rollback()  # nothing is ever kept

    return {"errors": errors}