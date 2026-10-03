# V4 completion checklist — 2026-10-03

## Phase 1 — Foundation / dữ liệu
- [x] Tách source và data V4, giữ nguyên 49 source V3 có hash.
- [x] Chạy regression V3 trên V4.
- [x] Audit point cloud/camera/calibration/pairing và xác nhận đơn vị/hệ trục chủ động.
- [x] Artifact journal/cache và kiểm soát revision theo session.

## Phase 2 — Ground / dễ nhìn
- [x] Ground segmentation local plane bảo thủ; giữ unknown/sparse/stacked returns.
- [x] Dim/hide/supported surface, raw reset, tự scan per-frame.
- [x] Focus theo cuboid 3D, giới hạn XY/Z, kiểm tra tiếp xúc ground.
- [x] Benchmark gần 300k điểm; cache đúng index mẫu hiển thị.

## Phase 3 — Camera / LiDAR assist
- [x] Calibration pinhole/rigid validation, near-plane clipping, overlay.
- [x] YOLO11n local CPU, không implicit download, provenance hash.
- [x] Mapping nhãn, gating calibration/pairing, ambiguity và evidence review.
- [x] Camera-guided pending proposals từ LiDAR; revision/conflict guards.
- [x] Tùy chọn camera assist sau detect 3D; không auto accept/publish.

## Phase 4 — Review / đo / đánh giá
- [x] Khoảng cách cảm biến/tâm/footprint, pitch/roll đầy đủ.
- [x] Quality diagnostics và comparison với annotation độc lập.
- [x] Review backup/restore thành session mới, fingerprint dataset/camera.
- [x] Save queue chống late response khi đổi frame, xóa trạng thái báo cáo cũ khỏi UI.

## Phase 5 — Verification / bàn giao
- [x] 93 Python tests; 8 JavaScript test-file groups; syntax 71 file.
- [x] Chrome E2E 18 checks, responsive 320–1440, không console/network errors.
- [x] Real point-cloud benchmark và real YOLO smoke.
- [x] Source integrity review, README và TEST_REPORT.

## Research gates — chưa triển khai thành model production
- [ ] T14 learned multimodal fusion: cần calibration/time được kiểm chứng, GT held-out, baseline và budget inference; chỉ mở khi cải thiện precision/recall thực nghiệm.
- [ ] T15 temporal aggregation/tracking: cần timestamps/ego pose và quy tắc identity/occlusion; chưa ghép frame không có pose.

Các gate trên là phần nghiên cứu sau MVP, không được đánh dấu đã hoàn thành. Không có kết quả accuracy trên dataset camera–LiDAR thật đủ calibration/GT trong lần bàn giao này.

## Solid ground enhancement — complete
- [x] Main WebGL depth, upper/underside materials, X-ray.
- [x] Above-ground orbit lock and visible underside warning.
- [x] Conservative small-hole closure and separate closed reference floor.
- [x] Selected-only labels/axes, supported footprints, relative-height filtering.
- [x] Depth-aware box/point/handle interactions; existing projection editors retained.
- [x] Exclusive local review snapshot with validation.
- [x] 96 Python / 10 JavaScript groups / 8 real GPU pixel checks; app and demo flows checked.
### Workspace UX completed
- [x] Separate object label/axis controls.
- [x] Central flexible canvas and collapsible edge rails.
- [x] Data / AI / Display and Objects / Camera / Quality grouping.
- [x] Focus/projection toggles and persisted layout.
- [x] Actual browser checks at 320/768/1024/1440, keyboard, editor selection and no duplicate IDs.
- [x] 96 Python tests and 12 JavaScript groups passed.
