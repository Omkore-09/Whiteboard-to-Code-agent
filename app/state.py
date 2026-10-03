from typing import TypedDict


class AgentState(TypedDict, total=False):
    image_path: str
    parsed_diagram: dict
    approved: bool
    plan: dict
    files: dict[str, str]
    errors: list[str]
    retries: int