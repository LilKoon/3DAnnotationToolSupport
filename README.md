# CVAT Auto Annotation V4

V4 triển khai ground display và camera assist trên nền V3. Source và dữ liệu V4 nằm riêng; các checkpoint LiDAR hiện có được tham chiếu từ V3.

## 🚀 Hướng dẫn Cài đặt (Setup Guide)

Dự án hỗ trợ chạy trên cả **macOS/Linux** và **Windows** thông qua thư viện ONNX Runtime.

### 1. Tạo môi trường ảo và cài đặt thư viện
Từ thư mục gốc của project (có chứa file `requirements.txt`):

**Trên macOS/Linux:**
```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Trên Windows:**
```bat
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```
*(Nếu bạn có Card màn hình NVIDIA trên Windows, hãy chạy thêm: `pip install onnxruntime-directml` để tăng tốc AI).*

### 2. Tải và cấu hình Model AI
Chạy script tự động tải model YOLO (nếu bạn chưa có):
```sh
python tools/setup_image.py
```
*Tùy chọn cho Windows (Option A)*: Để model chạy nhẹ hơn trên môi trường Windows mà không cần load toàn bộ PyTorch, hãy chuyển đổi model `.pt` sang `.onnx` bằng lệnh sau:
```sh
python tools/export_onnx.py
```
*(Hệ thống sẽ ưu tiên load file `.onnx` nếu tìm thấy, hoặc tự động lùi về dùng `.pt` như cũ nếu không có).*

### 3. Khởi chạy Server
**Trên macOS/Linux:**
```sh
./run.sh
```

**Trên Windows:** Nhấp đúp vào file `run.bat` (hoặc chạy qua Terminal):
```bat
run.bat
```
👉 Mở trình duyệt và truy cập: http://127.0.0.1:8004

## Các phase đã triển khai

1. Audit point cloud, camera và trạng thái calibration/đồng bộ. Chỉ xác nhận đơn vị mét và hệ trục khi đã kiểm tra dataset.
2. Quét ground hình học cục bộ; làm mờ, ẩn hoặc thay điểm ground bằng các ô bề mặt có dữ liệu hỗ trợ. Điểm chưa chắc vẫn được giữ. Có tự quét khi mở frame, focus box, lọc XY/Z và quay về điểm gốc.
3. Detect ảnh camera, chiếu cuboid/point cloud vào ảnh, đối chiếu nhãn và bằng chứng LiDAR. Camera thiếu calibration chỉ để tham khảo. Có đề xuất box pending từ cụm LiDAR phù hợp detection chưa khớp; thao tác tạo box là chủ động.
4. Khoảng cách tới cảm biến, khoảng cách tâm và khoảng hở footprint XY; kiểm tra tiếp xúc ground, chồng lấn và đánh giá với annotation độc lập.
5. Backup review, kiểm thử hồi quy/API/Chrome và benchmark dữ liệu thật. Import backup tạo session mới, giữ session đang mở.

## Camera assist

Import ảnh vào frame tương ứng, chạy nhận diện ảnh và chọn mapping nhãn. `person` được map sang `pedestrian` nếu job có nhãn đó; lớp chưa map được bỏ qua.

Calibration dùng camera pinhole, ma trận K 3×3 và T_camera_from_lidar 4×4 (đổi điểm LiDAR sang hệ camera optical: Z hướng ra trước camera). width/height phải khớp ảnh gốc. Ví dụ cấu trúc dưới đây chỉ là minh họa, không phải calibration cho dataset:

```json
{
  "model": "pinhole",
  "camera_id": "front",
  "K": [[800, 0, 640], [0, 800, 360], [0, 0, 1]],
  "T_camera_from_lidar": [[0, -1, 0, 0], [0, 0, -1, 0], [1, 0, 0, 0], [0, 0, 0, 1]],
  "width": 1280,
  "height": 720,
  "distortion": [0, 0, 0, 0, 0],
  "units": "metres",
  "reviewed": false,
  "frame_pairing": "unknown"
}
```

Kiểm tra overlay trên dữ liệu thật trước khi xác nhận reviewed; xác nhận ảnh/LiDAR cùng frame trước khi bật đối chiếu. Crop/resize phải cập nhật intrinsics. Fisheye chưa hỗ trợ. Camera assist không tự tăng confidence hay chấp nhận/publish box. Trường hợp nhiều cụm hoặc nhiều box gần tương đương được báo ambiguous.

## Đo lường, review và backup

Số đo lấy từ hình học 3D hiện có; chỉ hiển thị mét khi metadata đã xác nhận. Không suy ra khoảng cách mét chỉ từ kích thước vật thể trong một ảnh. Khoảng hở XY dùng footprint toàn bộ 8 đỉnh cuboid, kể cả pitch/roll.

Export JSON lưu review, calibration và kết quả camera assist; không chứa credentials, point cloud hoặc ảnh. Restore cần point cloud trùng fingerprint và camera tương ứng; tạo session mới. Đây là backup review, không thay thế backup dataset.

Đánh giá cần predictions và ground truth độc lập, đầy đủ. Chỉ số hiện tại là matching theo khoảng cách tâm, precision/recall, sai số tâm/góc và IoU cho cặp box upright. Không gọi kết quả này là mAP; tilted boxes bị loại khỏi chỉ số IoU và được ghi rõ.

## Kiểm thử

Từ V4:

```sh
../venv/bin/python tools/verify_v4.py
node tools/browser_verify_handoff.cjs
```

Browser script dùng Chrome và Playwright trong bundled Codex runtime trên máy hiện tại, server cổng 8004. Các report và ảnh chụp được lưu ở thư mục verification riêng cho mỗi lần chạy. Xem [TEST_REPORT.md](TEST_REPORT.md) và [tasks/todo.md](tasks/todo.md).

## Giới hạn cần giữ khi sử dụng

Ground là ước lượng hình học, chưa phải segmentation semantic của vùng đường có thể lái xe. Bề mặt không nối qua vùng thiếu dữ liệu hoặc mức cao không tương thích. Cây, dốc, cầu nhiều tầng và ground thưa cần kiểm tra trực quan; điểm unknown luôn giữ lại.

Camera-guided proposal là trợ giúp hình học, chưa phải model fusion được huấn luyện. Chưa có calibration/time/pose được kiểm chứng cùng bộ held-out annotation để xác nhận tăng độ chính xác. Learned fusion và temporal aggregation có gate riêng trong kế hoạch; không mở bằng calibration giả. Journals, cache và báo cáo kiểm thử được giữ lại, chưa có tác vụ tự dọn dữ liệu.

### Ground refresh fix
Sau khi chạy model trên cùng frame, ground và chế độ hiển thị được giữ nguyên. Chọn Mờ/Ẩn ground/Bề mặt liền sẽ tự quét nếu frame chưa có ground. Chuyển sang frame khác vẫn reset dữ liệu ground để tránh dùng nhầm mask.

## Ground đặc / góc nhìn rõ trên-dưới
Main view đã có WebGL depth, X-ray, mặt đáy nâu sọc, khóa nhìn dưới mặc định, sàn tham chiếu kín và nhãn/trục gọn. Nút Quét mặt đất từ chế độ raw bật surface. Xem [GROUND_SOLID.md](GROUND_SOLID.md) để dùng và hiểu giới hạn của sàn tham chiếu.

## Bố cục thao tác mới
Canvas lớn ở giữa; rail trái Dữ liệu / AI / Hiển thị, rail phải Objects / Camera / Kiểm tra. Nhấn nhóm để mở hoặc thu panel. Tập trung và Hình chiếu nằm ở đầu canvas. Nhãn/trục được tách riêng trong Hiển thị → Object & góc nhìn. Hướng dẫn: [WORKSPACE_UX.md](WORKSPACE_UX.md).
