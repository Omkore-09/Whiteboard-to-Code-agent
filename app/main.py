import asyncio
import json
import pathlib
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, File, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from app.config import REDIS_URL

UPLOADS = pathlib.Path("uploads")
UPLOADS.mkdir(exist_ok=True)
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_BYTES = 8 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.arq = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield
    await app.state.arq.close()
    await app.state.redis.aclose()


app = FastAPI(title="Whiteboard-to-Code", lifespan=lifespan)


@app.post("/jobs")
async def create_job(file: UploadFile = File(...)):
    ext = EXT.get(file.content_type)
    if not ext:
        raise HTTPException(400, "Upload a JPEG, PNG or WebP image")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image larger than 8 MB")

    job_id = uuid.uuid4().hex
    path = UPLOADS / f"{job_id}{ext}"
    path.write_bytes(data)
    await app.state.arq.enqueue_job("run_job", job_id, str(path))
    return {"job_id": job_id}


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    key = f"job:{job_id}:events"

    async def stream():
        cursor = 0
        for _ in range(600):  # about 5 minutes at 0.5 s per poll
            items = await app.state.redis.lrange(key, cursor, -1)
            for item in items:
                yield {"data": item}
                if json.loads(item)["stage"] in ("done", "failed"):
                    return
            cursor += len(items)
            await asyncio.sleep(0.5)

    return EventSourceResponse(stream())


@app.get("/jobs/{job_id}/result")
async def job_result(job_id: str):
    raw = await app.state.redis.get(f"job:{job_id}:result")
    if raw is None:
        raise HTTPException(404, "Result not ready (or expired)")
    return json.loads(raw)