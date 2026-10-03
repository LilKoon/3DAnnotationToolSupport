# Kế hoạch mở rộng hỗ trợ Windows & ONNX (Option A)

## Context
Công cụ hiện tại sử dụng YOLO11 (Pytorch `.pt`) và bash script (`run.sh`), phù hợp cho môi trường macOS/Linux. Mục tiêu là mở rộng để chạy ổn định, native và nhẹ nhàng trên Windows bằng cách chuyển đổi model sang chuẩn ONNX và tạo batch script cho Windows.

## Các công việc cần thực hiện (Implementation Plan)

1. **Tạo Script Khởi Chạy cho Windows (`run.bat`)**
   - Viết `run.bat` tương đương với `run.sh` hiện tại.
   - Script sẽ kích hoạt virtual environment của Windows (`venv\Scripts\activate`) và chạy `uvicorn`.

2. **Chuyển đổi Model sang ONNX (ONNX Export)**
   - Tạo một script `tools/export_onnx.py`.
   - Script này sử dụng thư viện `ultralytics` để convert `models/yolo11n.pt` thành `models/yolo11n.onnx`.

3. **Cập nhật Logic Inference (Backend)**
   - Sửa file `core/image_detector_v4.py`.
   - Thay vì load `.pt` mặc định, hệ thống sẽ ưu tiên tìm và load `.onnx` bằng `onnxruntime`. Nếu không có, dự phòng (fallback) về PyTorch/Ultralytics như cũ.
   - Đảm bảo logic inference vẫn trả ra định dạng bbox và confidence chuẩn.

4. **Cập nhật Requirements**
   - Thêm `onnxruntime` (và `onnxruntime-directml` nếu cần GPU trên Windows) vào tài liệu hoặc `requirements.txt`.

## Lợi ích đạt được
- Ứng dụng chạy mượt mà trên Windows (Native).
- Tận dụng chuẩn ONNX giúp rút gọn thư viện cần cài đặt lúc chạy (không bắt buộc cài PyTorch full nếu chỉ chạy inference ảnh).
- Tốc độ load và infer nhanh hơn trên các thiết bị Windows thông thường.
