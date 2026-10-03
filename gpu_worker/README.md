# PointPillars và CenterPoint cho 10 nhãn DOCX

Hai checkpoint nuScenes có đủ `car`, `truck`, `bus`, `trailer`, `construction_vehicle`, `pedestrian`, `motorcycle`, `bicycle`, `traffic_cone`, `barrier`. Thứ tự chỉ số class lấy từ metadata checkpoint, không lấy từ thứ tự trong bảng DOCX.

V3 gửi XYZI float32 của frame hiện tại tới worker. PointPillars FPN dùng bốn feature. CenterPoint Pillar02 circle NMS dùng thêm timestamp bằng 0 cho một sweep. Worker không giả lập sweep lân cận. Box trả về dùng gravity center, kích thước dx/dy/dz, yaw radian trong hệ LiDAR Z hướng lên. Camera ở lại trên Mac để kiểm tra class; calibration không cần cho hai detector LiDAR này.

## Google Colab GPU

1. Tải `V3_LiDAR_Colab.ipynb` từ phần **Cấu hình GPU / Colab** của V3, rồi mở notebook trong Colab.
2. Chọn **Runtime → Change runtime type → GPU** (T4 phù hợp với stack CUDA 11.8 trong notebook). Chạy lần lượt các cell.
3. Notebook cài Python 3.10 riêng, PyTorch 2.1.0 / CUDA 11.8, MMCV 2.1.0, MMDetection3D 1.4.0; tải hai checkpoint chính thức và kiểm checksum SHA256 từ tên checkpoint.
4. Cell kiểm tra gọi thực sự cả hai detector trên point cloud tổng hợp. Đây chỉ là kiểm tra thực thi, không đánh giá độ chính xác.
5. Cell cuối in URL HTTPS của tunnel và token. Dán hai giá trị vào V3 → **Lưu và kiểm tra kết nối**.
6. Chọn PointPillars hoặc CenterPoint, mở frame PCD/BIN hoặc CVAT job, rà ánh xạ nhãn, bấm **Chạy model**.

Khi Colab ngắt runtime, URL cũ không còn chạy; giữ notebook mở và cập nhật URL/token sau mỗi lần tạo worker. Cloudflare Quick Tunnel dành cho thử nghiệm, có thể giới hạn thời gian request. Với frame lớn hoặc inference lâu, dùng worker NVIDIA qua mạng trực tiếp hay SSH tunnel.

## Linux với NVIDIA và Docker

Máy cần Docker và NVIDIA Container Toolkit. Giải nén bundle vào một thư mục mới, vào thư mục `v3` có các thư mục `core` và `gpu_worker`:

```sh
docker build -f gpu_worker/Dockerfile -t v3-lidar-worker .
export V3_WORKER_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
docker run --gpus all --name v3-lidar-worker -p 127.0.0.1:8013:8013 -e V3_WORKER_TOKEN -v v3-lidar-checkpoints:/workspace/checkpoints v3-lidar-worker
```

Container tự tải checkpoint và chạy kiểm tra GPU trước khi mở API. Dùng SSH tunnel từ Mac tới máy GPU:

```sh
ssh -L 8013:127.0.0.1:8013 username@gpu-host
```

Trong V3 nhập URL `http://127.0.0.1:8013` cùng token của worker. Nếu V3 chạy ngay trên máy CUDA có môi trường trên, chọn **CUDA trên máy đang chạy V3**, đặt `V3_MMDET3D_ROOT` trỏ repo và `V3_LIDAR_WEIGHTS` trỏ thư mục checkpoint trước khi chạy V3.

## Review và dữ liệu

- Phiên PCD/BIN mới dùng đúng 10 nhãn lowercase. Phiên cục bộ cũ có thể dùng nút **Dùng 10 nhãn DOCX**; chỉ đổi khác biệt chữ hoa/thường, không ép `Cyclist` sang `bicycle`.
- Phiên CVAT luôn dùng nhãn thật từ job. Class thiếu trong job được hiển thị và bỏ qua; V3 không tự tạo hoặc thay đổi nhãn job.
- Ánh xạ của hai preset chỉ cho đúng class tương ứng hoặc **Bỏ qua**. Không gộp truck với trailer và không tạo rider.
- Box mới ở trạng thái pending, có confidence và source riêng của model. Kéo box, sửa nhãn/kích thước/yaw, đảo XYZ rồi chấp nhận trước khi publish.
- Chạy lại giữ nguyên box cũ kể cả chỉnh sửa và rejected. Đề xuất cùng nhãn (hoặc cùng model sau khi đổi nhãn) có IoU 3D ít nhất 0.5 được bỏ qua để hạn chế trùng. Đây là heuristic; người review vẫn cần rà box trùng và object đứng sát nhau.
- Checkpoint được huấn luyện bằng nhiều sweep của nuScenes; frame XYZI đơn có thể cho kết quả kém hơn benchmark. Kiểm tra đơn vị mét, trục Z hướng lên, sensor origin và thang intensity trước khi tin kết quả. Không khẳng định chất lượng trên sensor chưa biết.
- Cấu hình kết nối lưu thành các bản mới trong `data/detector_settings`, quyền 0600; token không trả về trình duyệt. Không đưa thư mục `data` vào bundle GPU.

## Nguồn chính thức

- [PointPillars config và checkpoint MMDetection3D v1.4.0](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/configs/pointpillars/metafile.yml)
- [CenterPoint config và checkpoint MMDetection3D v1.4.0](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/configs/centerpoint/metafile.yml)
- [Inference API và CPU limitations](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/mmdet3d/apis/inference.py)
- [uv Python environments](https://docs.astral.sh/uv/pip/environments/)
- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

Phần tích hợp API và UI được kiểm tra trên Mac bằng fixture detector. Chỉ khi cell kiểm tra CUDA hoặc worker `verify.py` thành công mới xác nhận hai checkpoint chạy trên GPU của bạn.
