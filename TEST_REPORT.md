# V4 test report — 2026-10-03

## Kết quả
- Python: **93 tests passed**, không skip. Bao gồm regression V3 và ground, calibration, evidence/proposals, measurement/evaluation, cache/journal edge cases, concurrency và backup.
- JavaScript: **8 test-file groups passed**; có unit test save queue khi response về sau khi chuyển session.
- Syntax: **71 file** kiểm tra Python AST/Node.
- **49 source V3** khớp hash snapshot, không phát hiện thay đổi.
- Chrome thật: **18 workflow checks passed**, không page errors, console errors hoặc HTTP failures. Không tràn ngang ở width 320/768/1024/1440.

[Verification JSON](data/verification/1790966484266437000/verification.json), [Python log](data/verification/1790966484266437000/python_tests.log), [JS log](data/verification/1790966484266437000/javascript_tests.log).

[Chrome report](data/verification/1790966686127/browser-report.json) kiểm tra demo, đơn vị, ground modes, chọn/sửa/lưu box, late save khi đổi frame, focus, measurement, YOLO thật, reference-only, reload, calibration chưa reviewed, quality, backup fork, automatic ground, upload cloud thật, height filter và redraw timing. Ảnh chụp trong cùng thư mục.

## Performance tại máy hiện tại

[Benchmark](data/verification/1790964626846441000/benchmark.json): macOS arm64, Python 3.13.15; ba cloud V3 chỉ đọc, hash trước/sau khớp.

| Điểm đầu vào | Quét ground | Bề mặt | Tam giác |
| --- | ---: | ---: | ---: |
| 298,752 | 360.55 ms | 8.50 ms | 1,424 |
| 298,500 | 342.88 ms | 8.99 ms | 1,384 |
| 299,322 | 349.38 ms | 8.43 ms | 1,368 |

YOLO11n CPU trên fixture bus.jpg của Ultralytics: 5 detections bus/person, 1,156.33 ms gồm load model; peak process RSS khoảng 458 MB. Browser headless vẽ 99,584 điểm: p50 11.4 ms, p95 14.5 ms trong probe redraw. Đây là phép đo cục bộ, không phải cam kết latency trên mọi máy/dataset.

## Regression / review đáng chú ý

- Invalid/nonfinite calibration, rigid reflection, behind-camera/near-plane geometry.
- Unknown/sparse và bề mặt chồng tầng không bị xóa theo ground không chắc.
- Sampling cache đúng 100k point budget và đúng index nguồn.
- JSON NaN không tạo artifact mới; journal dang dở bị bỏ qua khi đọc.
- Tám request cùng revision: chỉ một save thành công, bảy conflict.
- Evidence không sửa confidence; proposal pending chỉ tạo khi có LiDAR hỗ trợ.
- Khoảng hở và focus dùng toàn bộ rotation; IoU tilted không bị báo là upright.
- Save response không sửa revision của session mới; report UI không giữ dữ liệu session cũ.
- Backup restore tạo session mới và kiểm tra dataset/camera binding.

## Phạm vi chưa xác minh

CVAT import/publish được kiểm thử regression bằng mocked responses; không publish vào CVAT production. Không có bộ sensor thật đủ calibration/đồng bộ/held-out GT để đo lợi ích accuracy của camera assist. Browser calibration là dữ liệu tổng hợp chưa reviewed. Ground benchmark đo tốc độ, không đo segmentation accuracy. Không khẳng định V4 đã huấn luyện fusion hay temporal tracking.

Server bàn giao chạy cổng 8004. Các profiles, báo cáo và lần chạy thử được giữ lại; không có thao tác dọn/xóa file.

## Ground refresh bugfix — 2026-10-03
Root cause: model completion calls openSession on the same frame; the V4 ground hook unconditionally cleared mask/surface and mode. Preserve derived ground and scene settings for the same session, reset on a different frame, and scan automatically when selecting a non-raw mode without ground. A repeated scan preserves the selected mode; a raw choice while scanning remains raw.

Regression: 93 Python tests and **9 JS test-file groups** passed; [new verification](data/verification/1790970397124170000/verification.json). Added ground-lifecycle-v4.test.cjs for same-frame refresh, new-frame reset, lazy scan, repeated scan mode and pending raw selection.

Verified in the user's in-app browser on 298,752-point frame: selected surface without manual scan, then ran actual LiDAR Auto detect in append mode. Revision changed r1→r2, 6 existing boxes kept, 0 new boxes/7 duplicate proposals skipped. Surface stayed selected with 113,872 ground points and 1,424 triangles. Browser captured no warning/error logs. No publish to CVAT.

## Solid ground / WebGL release
Latest full verification: [verification JSON](data/verification/1790995136567695000/verification.json). **96 Python tests**, **10 JavaScript test-file groups**, **77 syntax files** passed, no skipped tests. All 49 V3 source hashes unchanged.

Actual WebGL fixture: **8 pixel checks passed** (above/below point visibility and occlusion, distinct upper/underside materials, X-ray, world height clipping). This tests the GPU renderer itself, beyond CPU geometry assertions.

In-app browser on 298,752 raw points / 99,584 displayed points:
- Data surface rendered 1,434 triangles, including 5 conservatively filled small cells.
- Reference floor rendered a closed two-triangle plane; explicit reference warning.
- Upward-only lock held when dragging below; opt-in below mode showed brown/striped underside and warning.
- X-ray toggled the depth view and explicit HUD.
- Ground scan from raw selected surface by default.
- Relative-height filters exercised on an isolated demo.
- Main-view box drag on demo persisted revision r2 and Z=-1.77 through reload.
- Snapshot persisted to a new local PNG; invalid PNG/unknown key/exclusive save are API-tested.
- Runtime error logs checked empty on app and demo. No external CVAT publish.

The in-app browser viewport override did not change reported innerWidth (735 CSS px); no overflow at that effective width. New 320/1440 breakpoint coverage is not claimed for this release; earlier V4 Chrome responsive coverage remains separately recorded. Context-loss fallback is implemented but not live fault-injected.

An actual underside capture is retained at data/sessions/323dbe7d4a2a4359a483c3d4bbea54af/v4/view_snapshots/6b6a115893794fcb877059b5d9d9e3f6.png. The visible points on the near/below side and outside the floor extent intentionally remain; the floor does not delete unknown returns.

### Final actual-model regression

On session `323dbe7d4a2a4359a483c3d4bbea54af`, actual MPS auto-detection completed from revision r2 to r3: zero new boxes, seven duplicate proposals skipped, and six existing boxes retained. Surface mode and the opaque two-triangle reference floor remained active after detection; ground classification counts were retained. Browser error logs were empty. No annotations were published to CVAT.

## Opposite-side visibility correction — 2026-10-03

The previous opaque mesh occluded only rays intersecting its finite footprint. Points beyond its edge remained visible, Z/Focus filters could discard occluding fragments, and genuine returns below the reference elevation still appeared on the brown underside.

Correction:
- Surface mode defaults to **Che toàn bộ phía đối diện**. GPU clips point and cuboid line fragments by the viewed ground side, independent of screen-space mesh coverage. Supported local planes are used in data mode; unknown cells use the median reference elevation for display only.
- **Mặt đáy chỉ hiện sàn** defaults on: below-ground views hide all point/box geometry and corresponding labels/handles/picking. The orientation widget remains visible. X-ray restores geometry; disabling floor-only allows inspection of native below-ground returns.
- The solid occluder survives Z/Focus clipping when full side isolation is enabled. Neither source cloud nor box geometry is rewritten.

Verification:
- 96 Python tests and 11 JavaScript test-file groups passed; 77 syntax files checked and 49 V3 source hashes unchanged.
- Final report: `data/verification/1790996235319190000/verification.json`.
- 16 actual WebGL pixel checks passed in `static/ground-side-fixture-v4.html`: reproduces edge leak with isolation off, verifies both viewing directions, outside-footprint points, Z and Focus, cuboid edges, floor-only and X-ray.
- Verified current user cloud in browser: bottom view is a solid brown striped floor with points/boxes hidden. X-ray restores geometry. Returned to above view with X-ray off; browser error logs empty.
- Proof: `data/sessions/323dbe7d4a2a4359a483c3d4bbea54af/v4/view_snapshots/47cef2cda05b4ee3a4c424d2249412c9.png`.
- No model inference or annotation edits were requested during this correction; no CVAT publication was performed.

## Canvas-first workspace UI — 2026-10-03

Implemented a central flexible viewport with two 40px edge rails and independently collapsible task panels. Left groups: Data / AI / Display; right groups: Objects / Camera / Quality. Point/ground settings and help moved out of the viewport. Display is ordered as point appearance, object/view options, scene filters, advanced ground options, audit, and help. Original controls are moved rather than cloned; original IDs/handlers and annotation data remain intact.

Label and axis display are independent controls, default off for unselected objects. Selected-object highlighting/edit handles retain their previous behavior. Focus hides panels/projections and restores prior choices. Reloading while focused restores the saved pre-focus layout. Projection visibility and selected panel/page persist. On narrow screens a panel opens as an overlay and the other side closes; it is never stacked below the workspace. Selecting an object routes the editor to the Objects group.

Validation:
- Full suite: 96 Python tests, 12 JavaScript test-file groups, 79 syntax files, 49 unchanged V3 source hashes. Final report: `data/verification/1790997542020013000/verification.json`.
- Four label/axis combinations verified in browser; renderer vertex probe confirmed 24 box-edge vertices with axes off and 30 with axes on, independent of label toggle.
- Real application iframe viewports at 320, 768, 1024 and 1440 px: document scrollWidth equals viewport width; no duplicate control IDs. Canvas widths were 240, 688, 704 and 1086.4 px under tested saved panel states. Desktop/narrow panel bounds were inspected; a 320px drawer stayed within [40,280].
- Focus changed the user tab canvas from 655×678.4 to 655×937 CSS px, restored exactly, and restored correctly after reloading while focused.
- Projection toggling, keyboard Enter collapse, page routing, persisted panel state, and actual selection/editor population (car, X=-5.59) verified without editing geometry.
- Current cloud has no camera images; the Camera grouping and resize refresh hook were verified, not a live calibrated overlay.
- Browser error logs empty. No model inference, annotation edits or CVAT publication were performed for this UI task.
- Actual main-canvas capture: `data/sessions/323dbe7d4a2a4359a483c3d4bbea54af/v4/view_snapshots/3abd45ffdf964949a58f25ebbbcc8208.png`.

Skill discovery: find-skills used to inspect the skills.sh leaderboard and the official Anthropic frontend-design source; local frontend-ui-engineering applied. No new skill installation or UI dependencies were needed.
