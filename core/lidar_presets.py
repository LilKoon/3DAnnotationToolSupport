"""nuScenes detector contracts matching the student's DOCX taxonomy.

Keep annotation display order separate from checkpoint class-index order.
"""
from __future__ import annotations

import numpy as np

GUIDELINE_LABELS = [
    "car", "truck", "bus", "trailer", "construction_vehicle", "pedestrian",
    "motorcycle", "bicycle", "traffic_cone", "barrier",
]
NUSCENES_CLASSES = [
    "car", "truck", "construction_vehicle", "bus", "trailer", "barrier",
    "motorcycle", "bicycle", "pedestrian", "traffic_cone",
]
MMDET3D_VERSION = "v1.4.0"
PROTOCOL = "v3-lidar-1"
COORDINATES = "lidar-z-up-geometric-center-dx-dy-dz-yaw-radians"
PRESETS = {
    "pointpillars-nuscenes": {
        "name": "PointPillars · nuScenes · 10 nhãn",
        "config": "configs/pointpillars/pointpillars_hv_fpn_sbn-all_8xb4-2x_nus-3d.py",
        "checkpoint": "https://download.openmmlab.com/mmdetection3d/v1.0.0_models/pointpillars/hv_pointpillars_fpn_sbn-all_4x8_2x_nus-3d/hv_pointpillars_fpn_sbn-all_4x8_2x_nus-3d_20210826_104936-fca299c1.pth",
        "channels": 4,
        "range": [-50, -50, -5, 50, 50, 3],
    },
    "centerpoint-nuscenes": {
        "name": "CenterPoint · nuScenes · 10 nhãn",
        "config": "configs/centerpoint/centerpoint_pillar02_second_secfpn_head-circlenms_8xb4-cyclic-20e_nus-3d.py",
        "checkpoint": "https://download.openmmlab.com/mmdetection3d/v1.0.0_models/centerpoint/centerpoint_02pillar_second_secfpn_circlenms_4x8_cyclic_20e_nus/centerpoint_02pillar_second_secfpn_circlenms_4x8_cyclic_20e_nus_20220811_031844-191a3822.pth",
        "channels": 5,
        "range": [-51.2, -51.2, -5, 51.2, 51.2, 3],
    },
}


def model_points(points: np.ndarray, model_id: str, intensity_scale: float = 1.0) -> np.ndarray:
    """Adapt V3 XYZI to each checkpoint; the single-sweep time offset is zero."""
    spec = PRESETS[model_id]
    points = np.asarray(points, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 4 or not len(points) or not np.isfinite(points).all():
        raise ValueError("Point cloud phải có các điểm float32 x/y/z/intensity hữu hạn.")
    if not np.isfinite(intensity_scale) or intensity_scale <= 0:
        raise ValueError("Intensity scale phải lớn hơn 0 và hữu hạn.")
    result = np.zeros((len(points), spec["channels"]), dtype=np.float32)
    result[:, :4] = points
    result[:, 3] *= intensity_scale
    extent = np.asarray(spec["range"])
    inside = ((result[:, :3] >= extent[:3]) & (result[:, :3] < extent[3:])).all(axis=1)
    if not inside.any():
        raise ValueError("Không có điểm trong phạm vi model; kiểm tra đơn vị mét và trục Z hướng lên.")
    return result[inside]


def validate_label_map(mapping: dict[str, str], labels: list[str]) -> None:
    """Map supported checkpoint classes to existing job labels, including grouped labels."""
    allowed = {name.casefold(): name for name in labels}
    for source, target in mapping.items():
        if source not in GUIDELINE_LABELS:
            raise ValueError(f"Nhãn model không thuộc DOCX: {source}")
        if target != "__skip__" and (target not in labels):
            raise ValueError(f"Nhãn đích không tồn tại trong job: {target}.")
