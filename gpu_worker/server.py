"""Authenticated GPU worker. Run: uvicorn gpu_worker.server:app --port 8013."""
from __future__ import annotations

import hmac
import os

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from core.lidar_presets import PROTOCOL, COORDINATES, GUIDELINE_LABELS, PRESETS
from core.lidar_runtime import LidarRuntime
from core.pointcloud import MAX_BYTES, parse_pointcloud


def create_app(runtime: LidarRuntime | None = None, token: str | None = None) -> FastAPI:
    runtime = runtime or LidarRuntime()
    token = token if token is not None else os.getenv("V3_WORKER_TOKEN", "")
    worker = FastAPI(title="V3 PointPillars / CenterPoint GPU Worker")

    def authorize(request: Request):
        if not token:
            raise HTTPException(503, "Set V3_WORKER_TOKEN before serving requests.")
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
            raise HTTPException(401, "Invalid GPU worker token")

    @worker.get("/health")
    def health(request: Request):
        authorize(request)
        return {"protocol": PROTOCOL, "coordinate_system": COORDINATES, "classes": GUIDELINE_LABELS, "models": runtime.status(), "input": "single-sweep XYZI float32 metres; cameras are not sent"}

    @worker.post("/infer/{model_id}")
    async def infer(model_id: str, request: Request, threshold: float = 0.3, intensity_scale: float = 1.0):
        authorize(request)
        if model_id not in PRESETS:
            raise HTTPException(404, "Unknown nuScenes detector")
        if not 0 <= threshold <= 1:
            raise HTTPException(400, "Threshold must be within [0, 1]")
        chunks, count = [], 0
        async for chunk in request.stream():
            count += len(chunk)
            if count > MAX_BYTES:
                raise HTTPException(413, "Point cloud exceeds 200 MB")
            chunks.append(chunk)
        try:
            points = parse_pointcloud(b"".join(chunks), "frame.bin")
            boxes = await run_in_threadpool(runtime.infer, points, model_id, threshold, intensity_scale)
            return {"protocol": PROTOCOL, "model_id": model_id, "coordinate_system": COORDINATES, "classes": GUIDELINE_LABELS, "boxes": boxes, "warnings": ["Single-sweep input: performance may differ from nuScenes multi-sweep benchmarks."]}
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error

    return worker


app = create_app()
