"""Run from v3: python -m gpu_worker.prepare_models."""
import argparse
from core.lidar_presets import PRESETS
from core.lidar_runtime import LidarRuntime

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=list(PRESETS), default=list(PRESETS))
    args = parser.parse_args()
    for path in LidarRuntime().prepare(args.models):
        print(path)
