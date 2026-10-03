"""Cached MMDetection3D inference for the two fixed nuScenes checkpoints."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import threading
from urllib.request import urlopen
from uuid import uuid4

import numpy as np

from .lidar_presets import PRESETS, NUSCENES_CLASSES, GUIDELINE_LABELS, model_points


class LidarRuntime:
    def __init__(self, repo: Path | None = None, weights: Path | None = None):
        root = Path(__file__).resolve().parents[1]
        self.repo = repo or Path(os.getenv("V3_MMDET3D_ROOT", root / "gpu_worker/dependencies/mmdetection3d"))
        self.weights = weights or Path(os.getenv("V3_LIDAR_WEIGHTS", root / "gpu_worker/checkpoints"))
        self.models = {}
        self.lock = threading.Lock()

    def paths(self, model_id: str) -> tuple[Path, Path]:
        spec = PRESETS[model_id]
        return self.repo / spec["config"], self.weights / spec["checkpoint"].rsplit("/", 1)[-1]

    def status(self) -> list[dict]:
        reason = ""
        try:
            if importlib.util.find_spec("mmdet3d") is None:
                reason = "Chưa cài MMDetection3D 1.4.0 trong môi trường GPU."
            else:
                import torch
                import mmdet3d
                if mmdet3d.__version__ != "1.4.0":
                    reason = "Backend này cần MMDetection3D 1.4.0."
                elif not torch.cuda.is_available():
                    reason = "Cần GPU NVIDIA/CUDA; MPS trên Mac không chạy backend này."
                else:
                    import mmcv.ops  # Ensure the compiled CUDA extension imports.
        except (ImportError, OSError, RuntimeError) as error:
            reason = f"Môi trường GPU chưa sẵn sàng: {type(error).__name__}"
        result = []
        for key, spec in PRESETS.items():
            config, checkpoint = self.paths(key)
            missing = not config.is_file() or not checkpoint.is_file()
            detail = reason or ("Chưa tải config/checkpoint. Chạy prepare_models.py trên máy GPU." if missing else "Sẵn sàng trên CUDA.")
            result.append({"id": key, "name": spec["name"], "classes": list(NUSCENES_CLASSES), "ready": not reason and not missing, "reason": detail, "loaded": key in self.models})
        return result

    def prepare(self, model_ids: list[str]) -> list[str]:
        """Download official checkpoints; retain interrupted downloads for recovery."""
        self.weights.mkdir(parents=True, exist_ok=True)
        outputs = []
        for model_id in model_ids:
            config, checkpoint = self.paths(model_id)
            if not config.is_file():
                raise RuntimeError(f"Không tìm thấy config {config}. Cài repo MMDetection3D v1.4.0 trước.")
            expected_hash = checkpoint.stem.rsplit("-", 1)[-1]
            if checkpoint.is_file():
                digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
                if not digest.startswith(expected_hash):
                    raise RuntimeError(f"Checkpoint có checksum sai: {checkpoint}. File được giữ nguyên.")
            else:
                staging = self.weights / f"{checkpoint.name}.download-{uuid4().hex}"
                digest = hashlib.sha256()
                with urlopen(PRESETS[model_id]["checkpoint"], timeout=120) as response, staging.open("xb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                        digest.update(chunk)
                if not digest.hexdigest().startswith(expected_hash):
                    raise RuntimeError(f"Checksum tải về không đúng; giữ file tại {staging}.")
                if checkpoint.exists():
                    raise RuntimeError(f"Checkpoint vừa được tạo bởi tiến trình khác; giữ file tại {staging}.")
                staging.rename(checkpoint)
            outputs.append(str(checkpoint))
        return outputs

    def infer(self, points: np.ndarray, model_id: str, threshold: float, intensity_scale: float = 1.0) -> list[dict]:
        if model_id not in PRESETS:
            raise ValueError("Model phải là PointPillars hoặc CenterPoint nuScenes.")
        if not 0 <= threshold <= 1:
            raise ValueError("Confidence threshold phải trong [0, 1].")
        adapted = model_points(points, model_id, intensity_scale)
        state = next(item for item in self.status() if item["id"] == model_id)
        if not state["ready"]:
            raise RuntimeError(state["reason"])
        # Serialize GPU inference; load each checkpoint once and reuse it.
        with self.lock:
            from mmengine import Config
            from mmdet3d.apis import init_model, inference_detector
            if model_id not in self.models:
                config, checkpoint = self.paths(model_id)
                cfg = Config.fromfile(str(config))
                spec = PRESETS[model_id]
                # Uploaded frames have XYZI and no sweep poses/timestamps.
                # Do not reshape Nx4 into Nx5 or fabricate neighbouring sweeps.
                pipeline = [
                    dict(type="LoadPointsFromFile", coord_type="LIDAR", load_dim=spec["channels"], use_dim=spec["channels"]),
                    dict(type="PointsRangeFilter", point_cloud_range=spec["range"]),
                    dict(type="Pack3DDetInputs", keys=["points"]),
                ]
                cfg.test_dataloader.dataset.pipeline = pipeline
                self.models[model_id] = init_model(cfg, str(checkpoint), device="cuda:0")
            model = self.models[model_id]
            classes = list(model.dataset_meta.get("classes", NUSCENES_CLASSES))
            if len(classes) != 10 or set(classes) != set(GUIDELINE_LABELS):
                raise RuntimeError("Checkpoint không có đúng 10 nhãn của guideline.")
            sample, _ = inference_detector(model, adapted)
            prediction = sample.pred_instances_3d
            boxes = prediction.bboxes_3d
            # MMDet's LiDAR gravity_center avoids origin and height ambiguities.
            centers = boxes.gravity_center.detach().cpu().numpy()
            sizes = boxes.dims.detach().cpu().numpy()
            yaws = boxes.yaw.detach().cpu().numpy()
            scores = prediction.scores_3d.detach().cpu().numpy()
            labels = prediction.labels_3d.detach().cpu().numpy()
            results = []
            for center, size, yaw, score, label in zip(centers, sizes, yaws, scores, labels):
                if not np.isfinite(score) or score < threshold or score > 1:
                    continue
                if not np.isfinite([*center, *size, yaw]).all() or np.any(size <= 0):
                    continue
                if not 0 <= int(label) < len(classes):
                    continue
                results.append({"label": classes[int(label)], "center": center.tolist(), "size": size.tolist(), "yaw": float(yaw), "confidence": float(score)})
            return results
