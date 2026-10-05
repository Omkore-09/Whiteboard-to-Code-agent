from langgraph.graph import END, START, StateGraph

from app.nodes.generate import generate_code
from app.nodes.readme import build_readme
from app.nodes.validate import validate_code
from app.nodes.vision import parse_diagram
from app.state import AgentState

MAX_ATTEMPTS = 3


def route(state: AgentState) -> str:
    if state.get("errors") and state.get("retries", 0) < MAX_ATTEMPTS:
        return "generate"
    return "readme"


g = StateGraph(AgentState)
g.add_node("parse", parse_diagram)
g.add_node("generate", generate_code)
g.add_node("validate", validate_code)
g.add_node("readme", build_readme)

g.add_edge(START, "parse")
g.add_edge("parse", "generate")
g.add_edge("generate", "validate")
g.add_conditional_edges("validate", route, {"generate": "generate", "readme": "readme"})
g.add_edge("readme", END)

graph = g.compile()

# Phase 1: read the diagram, then stop so the user can review it
p = StateGraph(AgentState)
p.add_node("parse", parse_diagram)
p.add_edge(START, "parse")
p.add_edge("parse", END)
parse_graph = p.compile()

# Phase 2: runs after the user approves the diagram
b = StateGraph(AgentState)
b.add_node("generate", generate_code)
b.add_node("validate", validate_code)
b.add_node("readme", build_readme)
b.add_edge(START, "generate")
b.add_edge("generate", "validate")
b.add_conditional_edges("validate", route, {"generate": "generate", "readme": "readme"})
b.add_edge("readme", END)
build_graph = b.compile()