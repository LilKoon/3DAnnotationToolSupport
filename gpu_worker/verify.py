"""GPU smoke test of both real checkpoints; this does not measure accuracy."""
import numpy as np
from core.lidar_presets import PRESETS, GUIDELINE_LABELS
from core.lidar_runtime import LidarRuntime


def verify(runtime: LidarRuntime):
    rng = np.random.default_rng(42)
    road = np.column_stack([rng.uniform(-25, 25, 8000), rng.uniform(-25, 25, 8000), rng.normal(-1.6, .03, 8000), rng.uniform(0, 255, 8000)]).astype(np.float32)
    for model_id in PRESETS:
        boxes = runtime.infer(road, model_id, .3)
        if any(box["label"] not in GUIDELINE_LABELS for box in boxes):
            raise RuntimeError("Unexpected detector class")
        print(f"CUDA inference OK: {model_id} ({len(boxes)} synthetic-cloud predictions; accuracy is not evaluated)", flush=True)


if __name__ == "__main__":
    verify(LidarRuntime())
