"""Create a self-contained Colab notebook without overwriting an existing one."""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import base64
import json
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def cell(kind, source):
    entry = {"cell_type": kind, "metadata": {}, "source": textwrap.dedent(source).strip().splitlines(keepends=True)}
    if kind == "code":
        entry.update(execution_count=None, outputs=[])
    return entry


def build():
    bundle = BytesIO()
    sources = ["core/lidar_presets.py", "core/lidar_runtime.py", "core/pointcloud.py", "gpu_worker/server.py", "gpu_worker/prepare_models.py", "gpu_worker/verify.py", "gpu_worker/setup_colab.py", "gpu_worker/requirements.txt"]
    with ZipFile(bundle, "w", ZIP_DEFLATED) as archive:
        for name in sources:
            archive.writestr("v3/" + name, (ROOT / name).read_bytes())
    encoded = base64.b64encode(bundle.getvalue()).decode()
    cells = [cell("markdown", """
        # V3 LiDAR auto detect trên Google Colab GPU

        Chọn **Runtime → Change runtime type → GPU (T4)** rồi chạy các cell theo thứ tự.
        Notebook tải checkpoint **PointPillars nuScenes FPN** và **CenterPoint nuScenes Pillar02** với đủ 10 nhãn DOCX:
        `car`, `truck`, `bus`, `trailer`, `construction_vehicle`, `pedestrian`, `motorcycle`, `bicycle`, `traffic_cone`, `barrier`.

        Dữ liệu đầu vào là một frame XYZI float32, đơn vị mét, Z hướng lên. Model được huấn luyện bằng nhiều sweep của nuScenes;
        kết quả một frame cần kiểm tra bằng point cloud và camera trong V3.
        Notebook chỉ chuẩn bị model và tạo worker; point cloud của bạn chỉ được gửi khi bạn bấm **Chạy model** trong V3.
        URL HTTPS và token ở cell cuối dùng để kết nối từ Mac. Giữ notebook mở trong khi annotation.
        Mỗi lần chạy tạo thư mục riêng, giữ lại dữ liệu và thư mục cũ.
    """), cell("code", """
        from pathlib import Path
        from uuid import uuid4
        from io import BytesIO
        from zipfile import ZipFile
        import base64, subprocess, os, sys
        subprocess.run(['nvidia-smi'], check=True)
        ROOT = Path('/content') / ('v3-lidar-' + uuid4().hex)
        ROOT.mkdir()
        PAYLOAD = '__BUNDLE__'
        with ZipFile(BytesIO(base64.b64decode(PAYLOAD))) as archive:
            archive.extractall(ROOT)
        V3 = ROOT / 'v3'
        sys.path.insert(0, str(V3))
        print('Workspace mới:', ROOT)
    """.replace("__BUNDLE__", encoded)), cell("markdown", """
        **Cài môi trường và tải checkpoint.** Bước này tạo Python 3.10 riêng và cần vài phút.
        Nếu wheel CUDA không tải được, xem lỗi ở cell này; chưa tiếp tục khi cài đặt thất bại.
    """), cell("code", """
        from gpu_worker.setup_colab import setup
        PYTHON = setup(ROOT)
        print('Môi trường và checkpoint đã chuẩn bị:', PYTHON)
    """), cell("markdown", """
        **Chạy thật cả hai model trên GPU.** Point cloud tổng hợp chỉ kiểm tra khả năng thực thi.
        Dòng `CUDA inference OK` phải xuất hiện cho cả hai model; đây không phải đánh giá độ chính xác trên dữ liệu bài tập.
    """), cell("code", """
        subprocess.run([str(PYTHON), '-m', 'gpu_worker.verify'], cwd=V3, check=True)
    """), cell("code", """
        import secrets, socket, time, json
        from urllib.request import Request, urlopen
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            PORT = probe.getsockname()[1]
        TOKEN = secrets.token_urlsafe(32)
        LOG = ROOT / 'worker.log'
        worker_log = LOG.open('xb')
        worker_process = subprocess.Popen([str(PYTHON), '-m', 'uvicorn', 'gpu_worker.server:app', '--host', '127.0.0.1', '--port', str(PORT)], cwd=V3, env=dict(os.environ, V3_WORKER_TOKEN=TOKEN), stdout=worker_log, stderr=subprocess.STDOUT)
        for _ in range(60):
            if worker_process.poll() is not None:
                raise RuntimeError(LOG.read_text(errors='replace'))
            try:
                request = Request(f'http://127.0.0.1:{PORT}/health', headers={'Authorization': 'Bearer ' + TOKEN})
                with urlopen(request, timeout=3) as response:
                    health = json.load(response)
                assert all(item['ready'] for item in health['models']), health
                print('Worker sẵn sàng:', [item['id'] for item in health['models']])
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError('Worker chưa sẵn sàng. Xem ' + str(LOG))
    """), cell("markdown", """
        **Tạo kết nối HTTPS tới V3 trên Mac.** Cloudflare Quick Tunnel tạo URL tạm cho worker có token.
        URL đổi khi tạo tunnel mới. Không chia sẻ token; chỉ dán vào V3 của bạn.
    """), cell("code", """
        import queue, re, threading
        cloudflared = ROOT / 'cloudflared'
        with urlopen('https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64', timeout=120) as response, cloudflared.open('xb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        cloudflared.chmod(0o755)
        tunnel_process = subprocess.Popen([str(cloudflared), 'tunnel', '--no-autoupdate', '--protocol', 'http2', '--url', f'http://127.0.0.1:{PORT}'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = queue.Queue()
        def read_tunnel():
            for line in tunnel_process.stdout:
                lines.put(line)
        threading.Thread(target=read_tunnel, daemon=True).start()
        deadline = time.monotonic() + 90
        URL = None
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=1)
            except queue.Empty:
                if tunnel_process.poll() is not None:
                    raise RuntimeError('Tunnel dừng; kiểm tra mạng Colab và thử tạo tunnel mới.')
                continue
            found = re.search(r'https://[a-zA-Z0-9-]+\\.trycloudflare\\.com', line)
            if found:
                URL = found.group(0)
                break
        if not URL:
            raise RuntimeError('Không lấy được URL tunnel trong 90 giây.')
        print('Dán vào V3 → Cấu hình GPU / Colab → Lưu và kiểm tra kết nối')
        print('URL:', URL)
        print('Token:', TOKEN)
        print('Chọn PointPillars hoặc CenterPoint trong Auto detect.')
    """), cell("markdown", """
        Trong V3, mở frame → kiểm tra ánh xạ 10 nhãn → **Chạy model** → kéo/chỉnh cuboid và hướng XYZ → chấp nhận box.
        Khi Colab hết phiên, tạo worker mới và cập nhật URL/token. Quick Tunnel dành cho thử nghiệm; inference quá lâu có thể bị timeout.

        Nguồn: [PointPillars](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/configs/pointpillars/metafile.yml),
        [CenterPoint](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/configs/centerpoint/metafile.yml),
        [MMDetection3D inference](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/mmdet3d/apis/inference.py).
    """)]
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"accelerator": "GPU", "colab": {"name": "V3_LiDAR_Colab.ipynb"}, "kernelspec": {"name": "python3", "display_name": "Python 3"}}, "cells": cells}
    for index, item in enumerate(cells):
        item["id"] = f"v3-lidar-{index}"
    target = ROOT / "gpu_worker/V3_LiDAR_Colab.ipynb"
    with target.open("x", encoding="utf-8") as output:
        json.dump(notebook, output, ensure_ascii=False, indent=2)
    return target


if __name__ == "__main__":
    print(build())
