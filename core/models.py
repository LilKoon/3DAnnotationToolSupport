from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import numpy as np

from .geometry import Cuboid
from .detector_service import detector_service
from .lidar_presets import PRESETS


CATALOG = {
    "geometry-cpu": {"name": "Đề xuất hình học · CPU", "classes": ["Car", "Pedestrian", "Cyclist"], "profile": "Chạy trên Apple Silicon, không cần checkpoint; cần kiểm tra từng box", "config_env": "", "checkpoint_env": ""},
    "open3d-ml-pointpillars": {"name": "Open3D-ML PointPillars", "classes": ["Car", "Pedestrian", "Cyclist"], "profile": "Chạy qua Open3D-ML (hỗ trợ Mac CPU tốt hơn)", "config_env": "V3_O3D_CONFIG", "checkpoint_env": "V3_O3D_CHECKPOINT"},
    "remote-api": {"name": "API Cloud / Colab", "classes": ["Car", "Pedestrian", "Cyclist"], "profile": "Gửi dữ liệu lên API Server (ví dụ: Colab) để tính toán", "config_env": "V3_REMOTE_API_URL", "checkpoint_env": ""},
    "pointpillars-kitti": {"name": "MMDet3D PointPillars", "classes": ["Car", "Pedestrian", "Cyclist"], "profile": "Baseline nhanh (yêu cầu CUDA/MMDetection3D)", "config_env": "V3_POINTPILLARS_CONFIG", "checkpoint_env": "V3_POINTPILLARS_CHECKPOINT"},
    "centerpoint": {"name": "MMDet3D CenterPoint", "classes": ["Car", "Pedestrian", "Cyclist"], "profile": "Cân bằng; chọn checkpoint đúng bộ dữ liệu", "config_env": "V3_CENTERPOINT_CONFIG", "checkpoint_env": "V3_CENTERPOINT_CHECKPOINT"},
    "pv-rcnn-kitti": {"name": "MMDet3D PV-RCNN", "classes": ["Car", "Pedestrian", "Cyclist"], "profile": "Chính xác hơn trên KITTI Car, cần nhiều tài nguyên hơn", "config_env": "V3_PVRCNN_CONFIG", "checkpoint_env": "V3_PVRCNN_CHECKPOINT"},
}


def configured_models() -> list[dict]:
    import os
    result = detector_service.catalog()
    for key, spec in CATALOG.items():
        if key == "geometry-cpu":
            result.append({"id": key, **spec, "ready": True})
            continue
        if key == "remote-api":
            url = os.getenv(spec["config_env"], "")
            result.append({"id": key, **spec, "ready": bool(url)})
            continue
        config = os.getenv(spec["config_env"], "")
        checkpoint = os.getenv(spec["checkpoint_env"], "")
        result.append({"id": key, **spec, "ready": bool(config and checkpoint and Path(config).is_file() and Path(checkpoint).is_file())})
    return result


def detect(points: np.ndarray, model_id: str, threshold: float = 0.3, input_path: Path | None = None) -> list[Cuboid]:
    import os

    if model_id in PRESETS:
        return detector_service.infer(points, model_id, threshold)
    if model_id not in CATALOG:
        raise ValueError("Unknown 3D model")
    if model_id == "geometry-cpu":
        return detect_geometry(points)
    
    spec = CATALOG[model_id]
    
    if model_id == "remote-api":
        url = os.getenv(spec["config_env"], "")
        if not url:
            raise ValueError("Set V3_REMOTE_API_URL environment variable to the Colab/Cloud API endpoint")
        return detect_remote(input_path, url, threshold)

    config = os.getenv(spec["config_env"], "")
    checkpoint = os.getenv(spec["checkpoint_env"], "")
    if not config or not checkpoint or not Path(config).is_file() or not Path(checkpoint).is_file():
        raise ValueError("Set the model config and checkpoint paths shown in the model catalog")

    if model_id == "open3d-ml-pointpillars":
        return detect_open3d_ml(points, config, checkpoint, threshold)

    # Standard MMDetection3D flow
    try:
        from mmdet3d.apis import init_model, inference_detector
    except ImportError as error:
        raise RuntimeError("MMDetection3D is not installed; use a compatible CUDA environment") from error
    import torch

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = init_model(config, checkpoint, device=device)
    if input_path is None or not input_path.is_file():
        raise RuntimeError("Inference requires the saved session BIN path")
    samples, _ = inference_detector(model, str(input_path))
    sample = samples[0] if isinstance(samples, (list, tuple)) else samples
    predictions = sample.pred_instances_3d
    classes = list(model.dataset_meta.get("classes", spec["classes"]))
    return predictions_to_cuboids(
        predictions.bboxes_3d.tensor.detach().cpu().numpy(),
        predictions.scores_3d.detach().cpu().numpy(),
        predictions.labels_3d.detach().cpu().numpy(),
        classes,
        model_id,
        threshold,
    )


def detect_remote(input_path: Path | None, url: str, threshold: float) -> list[Cuboid]:
    """Send point cloud to remote server (like Colab) for detection."""
    import requests
    if input_path is None or not input_path.is_file():
        raise RuntimeError("Inference requires the saved session BIN path")
    try:
        with open(input_path, "rb") as f:
            response = requests.post(url, files={"file": f}, data={"threshold": threshold})
        response.raise_for_status()
        data = response.json()
        boxes = []
        from uuid import uuid4
        for item in data.get("boxes", []):
            boxes.append(Cuboid(
                id=uuid4().hex,
                label=item["label"],
                center=item["center"],
                size=item["size"],
                yaw=item["yaw"],
                confidence=item.get("confidence", 1.0),
                source="remote-api"
            ))
        return boxes
    except Exception as e:
        raise RuntimeError(f"API Colab request failed: {e}")


def detect_open3d_ml(points: np.ndarray, config: str, checkpoint: str, threshold: float) -> list[Cuboid]:
    """Detect using Open3D-ML on CPU."""
    try:
        import open3d.ml.torch as ml3d
    except ImportError as e:
        raise RuntimeError("Open3D-ML is not installed (pip install open3d).") from e
    
    cfg = ml3d.utils.Config.load_from_file(config)
    model = ml3d.models.PointPillars(**cfg.model)
    pipeline = ml3d.pipelines.ObjectDetection(model)
    pipeline.load_ckpt(checkpoint)
    
    data = {
        'point': points[:, :3].astype(np.float32),
        'feat': None,
        'calib': None
    }
    
    # Run inference
    from uuid import uuid4
    results = pipeline.run_inference(data)
    boxes = []
    classes = cfg.dataset.get("classes", ["Car", "Pedestrian", "Cyclist"])
    
    for result in results:
        for obj in result:
            score = float(obj.confidence)
            if score < threshold:
                continue
            # Open3D-ML returns label index or string depending on version, handle safely
            label = classes[int(obj.label_class)] if isinstance(obj.label_class, (int, np.integer)) and 0 <= int(obj.label_class) < len(classes) else str(obj.label_class)
            
            # center, dimensions, yaw
            # Note: Open3D-ML box format might differ slightly, this is a standard mapping
            boxes.append(Cuboid(
                id=uuid4().hex,
                label=label,
                center=[float(obj.center[0]), float(obj.center[1]), float(obj.center[2])],
                size=[float(obj.size[0]), float(obj.size[1]), float(obj.size[2])],
                yaw=float(obj.yaw),
                confidence=score,
                source="open3d-ml-pointpillars"
            ))
    return boxes


def predictions_to_cuboids(tensor: np.ndarray, scores: np.ndarray, labels: np.ndarray, classes: list[str], model_id: str, threshold: float) -> list[Cuboid]:
    boxes = []
    for values, score, label_index in zip(tensor, scores, labels):
        if float(score) < threshold:
            continue
        x, y, bottom_z, dx, dy, dz, yaw = map(float, values[:7])
        if min(dx, dy, dz) <= 0 or not np.isfinite(values[:7]).all():
            continue
        label = classes[int(label_index)] if 0 <= int(label_index) < len(classes) else str(label_index)
        boxes.append(Cuboid(id=uuid4().hex, label=label, center=[x, y, bottom_z + dz / 2], size=[dx, dy, dz], yaw=yaw, confidence=float(score), source=model_id))
    return boxes


def detect_geometry(points: np.ndarray) -> list[Cuboid]:
    """Conservative local LiDAR proposals, useful where CUDA detectors cannot run."""
    from scipy.spatial import cKDTree

    xyz = points[:, :3]
    # Cap clustering cost, while keeping deterministic sampling across refreshes.
    xyz = xyz[::max(1, int(np.ceil(len(xyz) / 60_000)))]
    # Estimate road elevation in two-metre cells; discard cells without enough returns.
    cells = np.floor(xyz[:, :2] / 2).astype(np.int32)
    unique, inverse, counts = np.unique(cells, axis=0, return_inverse=True, return_counts=True)
    ground = np.full(len(unique), np.nan)
    for index in np.where(counts >= 8)[0]:
        heights = xyz[inverse == index, 2]
        ground[index] = np.quantile(heights, .12)
    global_ground = float(np.quantile(xyz[:, 2], .07))
    ground = np.where(np.isfinite(ground), ground, global_ground)
    elevated = (xyz[:, 2] - ground[inverse] > .25) & (xyz[:, 2] - ground[inverse] < 4.5)
    candidates = xyz[elevated]
    if len(candidates) < 8:
        return []
    tree = cKDTree(candidates)
    visited = np.zeros(len(candidates), dtype=bool)
    result: list[Cuboid] = []
    for seed in range(len(candidates)):
        if visited[seed]:
            continue
        neighbors = tree.query_ball_point(candidates[seed], .7)
        if len(neighbors) < 6:
            visited[seed] = True
            continue
        pending = list(neighbors)
        cluster = []
        visited[neighbors] = True
        while pending and len(cluster) <= 12000:
            index = pending.pop()
            cluster.append(index)
            nearby = tree.query_ball_point(candidates[index], .7)
            if len(nearby) >= 6:
                new = [other for other in nearby if not visited[other]]
                visited[new] = True
                pending.extend(new)
        if len(cluster) < 25 or len(cluster) > 12000:
            continue
        cloud = candidates[cluster]
        centre_xy = np.median(cloud[:, :2], axis=0)
        covariance = np.cov((cloud[:, :2] - centre_xy).T)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        principal = eigenvectors[:, np.argmax(eigenvalues)]
        yaw = float(np.arctan2(principal[1], principal[0]))
        c, s = np.cos(yaw), np.sin(yaw)
        local = (cloud[:, :2] - centre_xy) @ np.array([[c, -s], [s, c]])
        low = np.quantile(local, .02, axis=0)
        high = np.quantile(local, .98, axis=0)
        zlow, zhigh = np.quantile(cloud[:, 2], [.02, .98])
        dims = [float(high[0] - low[0]), float(high[1] - low[1]), float(zhigh - zlow)]
        length, width = sorted(dims[:2], reverse=True)
        if not (.3 <= width <= 3.5 and .3 <= length <= 9 and .6 <= dims[2] <= 4):
            continue
        label = "Pedestrian" if length < 1.4 and width < 1.3 else "Cyclist" if length < 2.7 and width < 1.6 else "Car"
        midpoint = (low + high) / 2
        xy = centre_xy + midpoint @ np.array([[c, s], [-s, c]])
        result.append(Cuboid(id=uuid4().hex, label=label, center=[float(xy[0]), float(xy[1]), float((zlow + zhigh) / 2)], size=dims, yaw=yaw, confidence=None, source="geometry-cpu"))
    return result
