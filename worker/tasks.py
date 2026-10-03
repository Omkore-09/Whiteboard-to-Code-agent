import asyncio
import json

import redis
from arq.connections import RedisSettings

from app.config import REDIS_URL
from app.graph import graph

TTL = 3600  # keep job data for an hour


def _run(job_id: str, image_path: str) -> None:
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    events_key = f"job:{job_id}:events"

    def emit(event: dict) -> None:
        r.rpush(events_key, json.dumps(event))
        r.expire(events_key, TTL)

    emit({"stage": "started"})
    final: dict = {}
    try:
        state = {"image_path": image_path, "errors": [], "retries": 0}
        for update in graph.stream(state, stream_mode="updates"):
            for node, out in update.items():
                final.update(out)
                emit({
                    "stage": node,
                    "attempt": final.get("retries", 0),
                    "errors": [e[:300] for e in final.get("errors", [])],
                })
        r.set(f"job:{job_id}:result", json.dumps({
            "files": final.get("files", {}),
            "errors": final.get("errors", []),
            "parsed_diagram": final.get("parsed_diagram"),
        }), ex=TTL)
        emit({"stage": "done"})
    except Exception as e:  # connection problems, API errors, bad model output
        emit({"stage": "failed", "error": str(e)[:500]})


async def run_job(ctx, job_id: str, image_path: str) -> None:
    # The graph uses blocking calls (Groq, psycopg), so keep it off the event loop.
    await asyncio.to_thread(_run, job_id, image_path)


class WorkerSettings:
    functions = [run_job]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 2        # keeps you inside Groq's free rate limits
    job_timeout = 300