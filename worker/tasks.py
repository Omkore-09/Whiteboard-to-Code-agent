import asyncio
import json
import os

import redis
from arq.connections import RedisSettings

from app.config import REDIS_URL
from app.graph import build_graph, parse_graph

TTL = 24 * 3600


def _client():
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _emitter(r, job_id: str):
    key = f"job:{job_id}:events"

    def emit(event: dict) -> None:
        event["worker"] = os.getpid()
        r.rpush(key, json.dumps(event))
        r.expire(key, TTL)

    return emit


def _stream(graph, state: dict, emit) -> dict:
    """Run a graph, emit one event per finished node, return the merged state."""
    final: dict = {}
    for update in graph.stream(state, stream_mode="updates"):
        for node, out in update.items():
            final.update(out)
            emit({
                "stage": node,
                "attempt": final.get("retries", 0),
                "errors": [e[:300] for e in final.get("errors", [])],
            })
    return final


def _parse(job_id: str, image_path: str) -> None:
    r = _client()
    emit = _emitter(r, job_id)
    emit({"stage": "started"})
    try:
        final = _stream(parse_graph, {"image_path": image_path}, emit)
        r.set(f"job:{job_id}:parsed", json.dumps(final["parsed_diagram"]), ex=TTL)
        emit({"stage": "review"})
    except Exception as e:
        emit({"stage": "failed", "error": str(e)[:500]})


def _build(job_id: str, diagram: dict) -> None:
    r = _client()
    emit = _emitter(r, job_id)
    try:
        state = {"parsed_diagram": diagram, "errors": [], "retries": 0}
        final = _stream(build_graph, state, emit)
        r.set(f"job:{job_id}:result", json.dumps({
            "files": final.get("files", {}),
            "errors": final.get("errors", []),
            "parsed_diagram": diagram,
        }), ex=TTL)
        emit({"stage": "done"})
    except Exception as e:
        emit({"stage": "failed", "error": str(e)[:500]})


async def parse_job(ctx, job_id: str, image_path: str) -> None:
    await asyncio.to_thread(_parse, job_id, image_path)


async def build_job(ctx, job_id: str, diagram_json: str) -> None:
    await asyncio.to_thread(_build, job_id, json.loads(diagram_json))


class WorkerSettings:
    functions = [parse_job, build_job]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 1        
    job_timeout = 300