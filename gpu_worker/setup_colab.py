"""Prepare an isolated Python 3.10/CUDA worker inside a Colab GPU runtime.

Run from the generated notebook. Existing folders and packages are preserved.
"""
from pathlib import Path
import os
import subprocess
import sys


def setup(root: Path) -> Path:
    # The notebook creates a fresh unique root for each run.
    bootstrap = root / "bootstrap"
    subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(bootstrap), "uv==0.8.22"], check=True)
    uv = bootstrap / "bin/uv"
    if not uv.is_file():
        uv = bootstrap / "uv/uv"
    environment = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(root / "pythons"), UV_CACHE_DIR=str(root / "cache"), UV_PYTHON_BIN_DIR=str(root / "bin"))
    envdir = root / "env"
    subprocess.run([str(uv), "venv", str(envdir), "--python", "3.10", "--seed"], check=True, env=environment)
    python = envdir / "bin/python"
    def pip(*args):
        subprocess.run([str(python), "-m", "pip", *args], check=True, env=environment)
    pip("install", "numpy==1.26.4")
    pip("install", "torch==2.1.0", "torchvision==0.16.0", "--index-url", "https://download.pytorch.org/whl/cu118")
    pip("install", "mmcv==2.1.0", "--only-binary=mmcv", "--no-deps", "-f", "https://download.openmmlab.com/mmcv/dist/cu118/torch2.1/index.html")
    v3 = root / "v3"
    pip("install", "-r", str(v3 / "gpu_worker/requirements.txt"))
    repo = v3 / "gpu_worker/dependencies/mmdetection3d"
    repo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", "--branch", "v1.4.0", "https://github.com/open-mmlab/mmdetection3d.git", str(repo)], check=True)
    pip("install", str(repo), "--no-build-isolation")
    subprocess.run([str(python), "-c", "import torch; import mmcv.ops; assert torch.cuda.is_available(), 'Select a GPU runtime in Colab'; print(torch.cuda.get_device_name(0))"], check=True)
    subprocess.run([str(python), "-m", "gpu_worker.prepare_models"], cwd=v3, check=True)
    return python
