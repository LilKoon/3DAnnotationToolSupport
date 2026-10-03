"""Local/remote detector selection and append-only GPU connection settings."""
from __future__ import annotations

import json
import math
import os
import platform
from pathlib import Path
import threading
import time
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import numpy as np

from .geometry import Cuboid
from .lidar_presets import PRESETS, GUIDELINE_LABELS, NUSCENES_CLASSES, PROTOCOL, COORDINATES
from .lidar_runtime import LidarRuntime
from .mac_lidar import MacLidarRuntime


class DetectorService:
    def __init__(self, settings_root: Path):
        self.settings_root = settings_root
        self.runtime = LidarRuntime()
        self.mac_runtime = MacLidarRuntime()
        self.cached = None
        self.cache_lock = threading.Lock()

    def settings(self) -> dict:
        files = sorted(self.settings_root.glob("*.json")) if self.settings_root.exists() else []
        if files:
            return json.loads(files[-1].read_text(encoding="utf-8"))
        default_mode = "mac" if platform.system() == "Darwin" and not os.getenv("V3_GPU_API_URL") else "remote"
        return {"mode": default_mode, "url": os.getenv("V3_GPU_API_URL", "").rstrip("/"), "api_token": os.getenv("V3_GPU_API_TOKEN", ""), "intensity_scale": 1.0}

    def public_settings(self) -> dict:
        settings = self.settings()
        return {key: value for key, value in settings.items() if key != "api_token"} | {"has_token": bool(settings["api_token"]), "classes": GUIDELINE_LABELS}

    def configure(self, mode: str, url: str, api_token: str | None, intensity_scale: float) -> dict:
        if mode not in {"remote", "local", "mac"}:
            raise ValueError("Chọn backend Mac Metal/MPS, remote hoặc local CUDA.")
        url = url.strip().rstrip("/")
        parsed = urlparse(url)
        if url and (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("GPU URL phải là http/https, không chứa mật khẩu, query hoặc fragment.")
        if mode == "remote" and not url:
            raise ValueError("Nhập URL của GPU worker hoặc Colab tunnel.")
        if not math.isfinite(intensity_scale) or intensity_scale <= 0:
            raise ValueError("Intensity scale phải hữu hạn và lớn hơn 0.")
        previous = self.settings()
        token = api_token or (previous["api_token"] if previous["url"] == url else "")
        if mode == "remote" and not token:
            raise ValueError("Nhập token do GPU worker cung cấp.")
        self.settings_root.mkdir(parents=True, exist_ok=True)
        # New configuration records preserve every previous version and token.
        path = self.settings_root / f"{time.time_ns():020d}-{uuid4().hex}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump({"mode": mode, "url": url, "api_token": token, "intensity_scale": intensity_scale}, output, ensure_ascii=False)
        self.cached = None
        return self.public_settings()

    @staticmethod
    def check_contract(data: dict):
        if not isinstance(data, dict) or data.get("protocol") != PROTOCOL or data.get("coordinate_system") != COORDINATES or data.get("classes") is None:
            raise RuntimeError("GPU worker không khớp giao thức, hệ tọa độ hoặc 10 nhãn DOCX. Dùng worker đi kèm V3.")
        if not isinstance(data["classes"], list) or len(data["classes"]) != 10 or set(data["classes"]) != set(GUIDELINE_LABELS):
            raise RuntimeError("GPU worker phải có đúng 10 nhãn DOCX.")

    def remote_health(self, force: bool = False) -> dict:
        settings = self.settings()
        with self.cache_lock:
            if not force and self.cached and time.monotonic() - self.cached[0] < 15:
                return self.cached[1]
            if not settings["url"]:
                return {"error": "Chưa kết nối GPU. Mở Cấu hình GPU để nhập URL và token."}
            try:
                response = httpx.get(settings["url"] + "/health", headers={"Authorization": f"Bearer {settings['api_token']}"}, timeout=5, follow_redirects=False)
                response.raise_for_status()
                data = response.json()
                self.check_contract(data)
                if not isinstance(data.get("models"), list):
                    raise RuntimeError("GPU health thiếu danh sách model.")
            except httpx.HTTPStatusError as error:
                data = {"error": f"GPU worker trả HTTP {error.response.status_code}; kiểm tra URL và token."}
            except (httpx.RequestError, ValueError, RuntimeError, TypeError) as error:
                data = {"error": str(error) if isinstance(error, RuntimeError) else "Không kết nối được GPU worker; kiểm tra URL và máy GPU."}
            self.cached = (time.monotonic(), data)
            return data

    def catalog(self, force: bool = False) -> list[dict]:
        settings = self.settings()
        if settings["mode"] == "mac":
            health = {"models": self.mac_runtime.verify()}
        else:
            health = self.remote_health(force) if settings["mode"] == "remote" else {"models": self.runtime.status()}
        statuses = {item["id"]: item for item in health.get("models", []) if isinstance(item, dict) and item.get("id") in PRESETS}
        results = []
        for model_id, spec in PRESETS.items():
            status = statuses.get(model_id, {})
            matches = set(status.get("classes", [])) == set(GUIDELINE_LABELS)
            ready = status.get("ready") is True and matches and not health.get("error")
            results.append({"id": model_id, "name": spec["name"], "classes": NUSCENES_CLASSES, "ready": bool(ready), "backend": settings["mode"], "profile": "10 nhãn theo DOCX · LiDAR một frame · box nháp có thể chỉnh sửa", "reason": health.get("error") or status.get("reason") or "Worker chưa khai báo đủ 10 nhãn/model.", "config_env": "V3_GPU_API_URL", "checkpoint_env": "V3_GPU_API_TOKEN", "checkpoint_url": spec["checkpoint"]})
        return results

    def infer(self, points: np.ndarray, model_id: str, threshold: float) -> list[Cuboid]:
        settings = self.settings()
        state = next(item for item in self.catalog() if item["id"] == model_id)
        if not state["ready"]:
            raise RuntimeError(state["reason"])
        if settings["mode"] == "mac":
            raw = self.mac_runtime.infer(points, model_id, threshold, settings["intensity_scale"])
        elif settings["mode"] == "local":
            raw = self.runtime.infer(points, model_id, threshold, settings["intensity_scale"])
        else:
            try:
                response = httpx.post(settings["url"] + f"/infer/{model_id}", params={"threshold": threshold, "intensity_scale": settings["intensity_scale"]}, content=np.asarray(points, dtype="<f4").tobytes(), headers={"Authorization": f"Bearer {settings['api_token']}", "Content-Type": "application/octet-stream"}, timeout=httpx.Timeout(300, connect=10), follow_redirects=False)
                response.raise_for_status()
                data = response.json()
                self.check_contract(data)
                if data.get("model_id") != model_id:
                    raise RuntimeError("Worker trả kết quả của model khác.")
                raw = data.get("boxes")
            except httpx.HTTPStatusError as error:
                try:
                    detail = error.response.json().get("detail", "Inference thất bại.")
                except ValueError:
                    detail = "Inference thất bại."
                raise RuntimeError(f"GPU HTTP {error.response.status_code}: {detail}") from error
            except (httpx.RequestError, ValueError) as error:
                raise RuntimeError("Không nhận được kết quả từ GPU worker; phiên hiện tại được giữ nguyên.") from error
        if not isinstance(raw, list) or len(raw) > 10000:
            raise RuntimeError("GPU worker trả danh sách box không hợp lệ.")
        result = []
        for item in raw:
            if not isinstance(item, dict) or item.get("label") not in GUIDELINE_LABELS:
                raise RuntimeError("GPU worker trả nhãn ngoài 10 class của DOCX.")
            score = item.get("confidence")
            if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise RuntimeError("Confidence của box không hợp lệ.")
            if score < threshold:
                continue
            try:
                result.append(Cuboid(id=uuid4().hex, label=item["label"], center=item["center"], size=item["size"], yaw=item["yaw"], confidence=score, source=model_id))
            except (KeyError, ValueError, TypeError) as error:
                raise RuntimeError("GPU worker trả geometry của box không hợp lệ.") from error
        return result


detector_service = DetectorService(Path(__file__).resolve().parents[1] / "data/detector_settings")
