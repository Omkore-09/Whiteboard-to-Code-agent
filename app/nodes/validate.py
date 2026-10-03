import ast

import psycopg

from app.config import SUPABASE_DB_URL
from app.state import AgentState


def validate_code(state: AgentState) -> dict:
    files = state["files"]
    errors: list[str] = []

    try:
        ast.parse(files["api.py"])
    except SyntaxError as e:
        errors.append(f"api.py syntax error at line {e.lineno}: {e.msg}")

    try:
        with psycopg.connect(SUPABASE_DB_URL, connect_timeout=15) as conn:
            with conn.transaction():
                conn.execute("create schema scratch_validate")
                conn.execute("set local search_path to scratch_validate")
                conn.execute(files["schema.sql"])
                raise psycopg.Rollback()
    except psycopg.Error as e:
        errors.append(f"schema.sql SQL error: {e}")

    return {"errors": errors}