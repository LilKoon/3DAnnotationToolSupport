# V4 annotation workspace UX
2026-10-03

Subject: LiDAR cuboid annotation, where the central viewport is the primary working surface.
Design: keep the existing navy/teal palette, small restrained borders, native system font and compact 12/14px type. No decorative cards in the viewport.
Palette: canvas #0f1924; panels #101b27; raised surfaces #172431; borders #355064; accent #54c9b7; foreground #dce7ef.
Layout: left edge rail | optional task panel | flexible 3D canvas | optional object panel | right edge rail.
Canvas owns remaining height after the header and compact navigation. Optional Top/Front/Side row occupies 22%, not 30%. Display controls move out of the viewport.
Left: Data (file/CVAT and axis conventions), AI (model detection and advanced evaluation), Display (point appearance, ground analysis, filters, ground controls, help).
Right: Objects (list, review, cuboid editor, measurements), Camera (reference images and camera assistance), Quality (box/GT checks).
Preserve original control elements, IDs and event handlers when moving them; never clone annotation inputs. Async V4 panels must route into their correct groups after loading.
Independent rails collapse to 40px; opening a different group selects it. Small/medium displays permit one expanded side at a time and never push a panel below the canvas.
Remember panel/page/projection choices, recover from invalid storage. Focus mode temporarily hides both panels and projections, restoring previous choices.
Keyboard: native button navigation and visible focus; Shift+backslash toggles focus outside editable fields; Escape closes panels on narrow layouts.
Verification: all 4 label/axis option combinations, sidebar/page toggles, focus restore, projection visibility, persistence, asynchronous panel routing, unique IDs and original handlers, actual canvas resize. Verify 320/768/1024/1440 using explicit iframe viewports when browser viewport overrides are ineffective.

## Cách thao tác

- Nhấn nhóm trên rail trái/phải để mở đúng công cụ; nhấn lại cùng nhóm hoặc nút ‹ / › trong tiêu đề để thu sát mép.
- **Tập trung** ẩn hai bảng và ba hình chiếu, nhấn lại để khôi phục. **Hình chiếu** bật/tắt riêng Top/Front/Side.
- **Hiển thị → Object & góc nhìn** chứa hai tùy chọn riêng cho nhãn và trục, cùng góc nhìn dưới ground, X-ray và xuất ảnh.
- **Objects** chứa danh sách, duyệt, chỉnh cuboid và đo khoảng cách; chọn object sẽ mở bảng này khi đang ở bố cục thông thường.
- Các chức năng ít dùng nằm trong details. Trạng thái sidebar/nhóm/hình chiếu được nhớ trên trình duyệt.
- Shift + backslash: chuyển chế độ tập trung; Enter: kích hoạt nút đang focus; Escape: đóng drawer trên màn hình hẹp. Phím tắt không chạy khi nhập liệu.

Skill discovery used [find-skills](https://www.skills.sh/) to verify [Anthropic frontend-design](https://www.skills.sh/anthropics/skills/frontend-design), with [official source instructions](https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md). Local frontend-ui-engineering supplied implementation/accessibility guidance. No global skill installation was performed.

Completed validation: 96 Python / 12 JavaScript groups, actual 320/768/1024/1440 viewports without page overflow, unique IDs, original selection/editor behavior, all label/axis combinations, focus restore (including reload), projection toggle and keyboard collapse. See TEST_REPORT.md for measurements and scope.
