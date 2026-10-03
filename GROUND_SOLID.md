# Ground đặc và định hướng 3D

Bấm **Quét mặt đất** để bật bề mặt đặc; hoặc chọn **Mặt đất → Bề mặt liền**. Mở **Mặt đất đặc & góc nhìn** để điều chỉnh.

- **Theo dữ liệu ground**: các tile được LiDAR hỗ trợ, có lưới thưa. Mặc định chỉ nối ô trống nhỏ được bốn ô ground cùng mức cao bao quanh; không lấp vùng lớn hoặc nối hai tầng.
- **Sàn tham chiếu kín**: một sàn ngang kín trong phạm vi ground quan sát, tại mức cao trung vị của các ô ground. Chỉ để định hướng/che khuất; không phải bản dựng chính xác của đường dốc và không dùng đo hay sửa annotation.
- **Khóa nhìn dưới** mặc định. Bật Cho phép nhìn dưới khi cần; mặt đáy nâu sọc và dòng cảnh báo phân biệt rõ với mặt trên xanh xám. Nút Về góc nhìn phía trên đưa camera về góc an toàn.
- **X-ray** bật nhìn xuyên ground và depth. Tắt để ground che điểm/box phía sau.
- Mặc định chỉ box được chọn có nhãn và trục đầy đủ. Có checkbox hiện tất cả khi cần.
- Dấu chân box chỉ vẽ khi ground có support tại các góc đáy.
- Lọc Z theo độ cao trên ground dùng ground cục bộ từ dữ liệu. Vùng thiếu ground giữ lại; giá trị Z từ/Z đến lúc này là chiều cao tương đối, thay vì Z tuyệt đối.
- Xuất ảnh góc nhìn lưu PNG và caption vào file mới cục bộ; link tải xuất hiện sau khi lưu. File ảnh không thay đổi annotation.

Main view dùng WebGL có depth; Top/Front/Side vẫn giữ editor cũ. Chọn box/điểm và tay nắm bị ground che được kiểm tra trước khi tương tác. Box vẫn có thể chọn trong danh sách và review bằng X-ray/hình chiếu. Ground cùng mode được giữ khi model cập nhật cùng frame.

Nếu WebGL không khả dụng/mất context, giao diện báo đang dùng renderer dự phòng **không có che khuất**. Không dùng hình ảnh của fallback để kết luận rằng ground đang che vật thể.

Các thay đổi chỉ tác động lớp hiển thị, không biến sàn tham chiếu hoặc các ô nối thành ground truth. API snapshot lưu riêng dưới session/v4/view_snapshots; không có tự dọn/xóa dữ liệu.

## Verification
Xem TEST_REPORT.md. Fixture WebGL thật có thể chạy lại tại http://127.0.0.1:8004/static/solid-ground-fixture-v4.html bằng nút Run actual GPU depth tests. Các test hình học nằm trong tests/solid-ground-v4.test.cjs; snapshot API có test validation và exclusive save.

## Che hai phía và mặt đáy sạch

Trong **Bề mặt liền**, **Che toàn bộ phía đối diện** mặc định bật để điểm/cạnh box bên kia ground không lọt qua mép sàn. **Mặt đáy chỉ hiện sàn** cũng mặc định bật: khi xoay xuống dưới, chỉ hiển thị sàn nâu có sọc và trục định hướng. Tắt tùy chọn mặt đáy để kiểm tra điểm thực sự dưới ground; bật X-ray để xem xuyên toàn bộ.

Vùng không có ground dùng cao độ tham chiếu trung vị để lọc hiển thị. Đây là trợ giúp quan sát, không phải kết luận phân loại hay giá trị đo; dữ liệu gốc và geometry annotation giữ nguyên. Bộ lọc Z/Focus không khoét phần sàn che khi chế độ che phía đối diện đang bật.
