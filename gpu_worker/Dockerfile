FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-devel
WORKDIR /workspace/v3
RUN apt-get update && apt-get install -y git libgl1 libglib2.0-0 libgomp1
COPY gpu_worker/requirements.txt /workspace/requirements.txt
RUN python -m pip install numpy==1.26.4 torchvision==0.16.0
RUN python -m pip install mmcv==2.1.0 --only-binary=mmcv --no-deps -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.1/index.html
RUN python -m pip install -r /workspace/requirements.txt
RUN git clone --depth 1 --branch v1.4.0 https://github.com/open-mmlab/mmdetection3d.git /opt/mmdetection3d
RUN python -m pip install /opt/mmdetection3d --no-build-isolation
COPY core/lidar_presets.py core/lidar_runtime.py core/pointcloud.py ./core/
COPY gpu_worker/server.py gpu_worker/prepare_models.py gpu_worker/verify.py ./gpu_worker/
ENV V3_MMDET3D_ROOT=/opt/mmdetection3d
ENV V3_LIDAR_WEIGHTS=/workspace/checkpoints
EXPOSE 8013
CMD ["bash", "-c", "python -m gpu_worker.prepare_models && python -m gpu_worker.verify && exec uvicorn gpu_worker.server:app --host 0.0.0.0 --port 8013"]
