import base64
import io

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from PIL import Image

from app.config import VISION_MODEL
from app.schemas import ParsedDiagram
from app.state import AgentState

PROMPT = """You are reading a hand-drawn database/ER diagram.
Extract every entity (table), its columns with sensible SQL types, primary keys,
and the relations between entities. If handwriting is unclear, make your best
guess and describe the doubt in `notes`. Do not invent entities that are not drawn.
Put each relationship's diamond label in `name`. If two entities are joined by several
diamonds, output one relation per diamond."""


def _encode(path: str) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((1600, 1600))  # keeps the payload small for the free tier
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def parse_diagram(state: AgentState) -> dict:
    llm = ChatGroq(model=VISION_MODEL, temperature=0).with_structured_output(ParsedDiagram)
    msg = HumanMessage(content=[
        {"type": "text", "text": PROMPT},
        {"type": "image_url",
         "image_url": {"url": f"data:image/jpeg;base64,{_encode(state['image_path'])}"}},
    ])
    result = llm.invoke([msg])
    return {"parsed_diagram": result.model_dump()}