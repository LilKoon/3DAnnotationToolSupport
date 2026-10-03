# V4 release review

## Kết luận
Các phase ứng dụng của V4 có kiểm thử tự động và Chrome E2E, không còn lỗi được quan sát trong phạm vi đã kiểm tra. Source V3 giữ nguyên hash. V4 là MVP ground/camera assist; nghiên cứu learned fusion và temporal vẫn có prerequisites chưa thỏa.

## Các chiều đã rà soát
- Correctness: conservative ground, index sampling, full cuboid rotations, pinhole validation, geometry ambiguity và independent evaluation.
- Data integrity: revision checks trước/sau inference, per-session locks, append-only derived artifacts; backup restore thành session khác; source integrity manifest.
- UX: raw reset, unknown points, explicit units/calibration/pairing, pending review, stale report clearing, responsive layout.
- Performance: spatial lookup cho tiles, bounded clustering/triangles/display points; benchmark cloud thật và inference CPU.
- Maintainability: modules/routes V4 riêng, regression V3 giữ nguyên; tài liệu commands, boundaries và limitations.

Các lỗi phát hiện trong vòng review đã có regression: interrupted journal, nonfinite serialization, concurrent stale writes, mapping person/pedestrian, late UI save và báo cáo còn giữ frame cũ. API camera không dùng inference ảnh để tự phát minh metric depth.

Thư mục project hiện không có Git repository; không tạo commit/PR. Những module phiên bản thử được giữ lại để tuân thủ quy tắc không xóa/ghi đè source. Khi có Git và cho phép refactor file hiện hữu, nên hợp nhất các additive adapter để giảm lớp override; đây là khoản bảo trì, không thay đổi kết quả kiểm thử hiện tại.

## Solid ground review
Renderer depth chỉ thay main canvas; projection editors/save API được giữ. GPU buffers tái sử dụng, point-color/mask/height cache gắn nguồn điểm và ground record; không viết vào dataset. Picking ground dùng ray/cuboid và intersection depth, chặn tay nắm bị ground che. Nối lỗ yêu cầu đủ 4 cardinal neighbors và chênh lệch cao <=0.15 tại tâm/các góc; bounded 6000 triangles. Reference floor là lớp thị giác riêng, không đưa vào ground_contact/measure/evaluation. Snapshot API giới hạn base64, PNG dimensions, validate session/key và exclusive UUID file; test chứng minh session không đổi. Eight actual GPU pixel tests passed. Live context-loss recovery and new mobile breakpoint coverage are not claimed.

Opposite-side correction reviewed: finite mesh edge leaks addressed by GPU side clipping, independent underside floor-only presentation, matched label/handle/picking filters and X-ray escape. Unknown-cell side filtering is explicitly display-only and uses reference elevation. 96 Python / 11 JS groups / 16 actual GPU assertions passed; no V3 changes or file deletions.

Workspace UI review: controls moved with stable IDs/handlers; no external UI dependencies or API mutations; narrow drawers stay on canvas edges; sidebar pages use hidden semantics and native accessible buttons; reduced motion respected. Keyboard collapse, selection/editor data, persistence and focus restore verified. 96 Python / 12 JS groups and actual four-viewport layout checks passed. Camera group had no real images in this session, so calibrated overlay rendering is not claimed as live-tested.
