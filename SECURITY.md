# Cảnh báo về dữ liệu trong repo này

Repo này là một **bài tập học thuật** (Swinburne, Project A/B — Topic 4). Nó chứa mã
nguồn và báo cáo phân tích về dòng tiền của **Quỹ Nuôi Em** (`quynuoiem.com`), dựa
trên dữ liệu mà chính Quỹ **đã công bố công khai** trên website của mình.

## 1. Repo này KHÔNG chứa dữ liệu gốc

Đã loại khỏi Git bằng `.gitignore`:

| File | Kích thước | Vì sao loại |
|---|---:|---|
| `data/real_vcb.csv` | 34 MB | Sao kê gốc — chứa tên, số điện thoại, email nhà tài trợ trong cột nội dung |
| `data/nuoi_em_mvp.sqlite` | 176 MB | Database sinh từ sao kê, cùng nội dung trên |

Repo chỉ chứa **mã nguồn** và **báo cáo tổng hợp**. Không có một dòng dữ liệu cá
nhân nào trong Git. Muốn chạy lại, bạn cần tự có file sao kê — xem `README.md`.

## 2. Định danh của bên thứ ba đã được che bớt

Một số tài liệu trong `docs/` có nhắc tới ID Google Sheet và số tài khoản ngân hàng
của Quỹ. Chúng được giữ lại **một phần**, dạng `1boFEZ…WgHg` — 6 ký tự đầu và
4 ký tự cuối, phần giữa thay bằng dấu ba chấm.

Giữ lại một phần thay vì xoá hẳn, vì:

- người đọc thấy phát hiện dựa trên định danh thật, không phải suy đoán;
- Quỹ đối chiếu được **đúng file nào cần thu hồi** mà không phải hỏi lại.

Che phần giữa, vì chuỗi đó không còn dùng để mở được file. Bản đầy đủ chỉ nằm trên
máy tác giả, không đưa lên Git.

Vì sao chuyện này đáng làm: những bảng tính đó chứa thông tin cá nhân của khoảng
**1.818 nhà tài trợ** — tên, số điện thoại, email nằm ngay trong nội dung chuyển
khoản. Một định danh đầy đủ và công khai là một đường dẫn thẳng tới dữ liệu đó, nên
nó không nên nằm trong một repo công khai.

Nếu bạn là thành viên Quỹ Nuôi Em và muốn các định danh này được gỡ hẳn, mở một
issue hoặc liên hệ tác giả; việc gỡ sẽ làm ngay, không tranh luận.

## 3. Những gì repo này không làm

- Không tấn công, không dò quét, không thử vượt quyền bất kỳ hệ thống nào.
- Không vượt qua bất kỳ ranh giới truy cập nào — toàn bộ dữ liệu dùng trong dự án
  đều đọc được bởi bất kỳ khách truy cập nào, không cần đăng nhập.
- Không công bố dữ liệu cá nhân. Báo cáo chỉ nêu **số lượng** (số dòng, số bản ghi)
  để chứng minh nguồn, không liệt kê danh tính.
- Không kết luận Quỹ vi phạm pháp luật. Kết luận của dự án là về **thiết kế hệ thống
  và kiểm soát dữ liệu**, không phải về ý định hay hành vi của cá nhân.

## 4. Cách báo cáo vấn đề

Nếu bạn thấy trong repo có dữ liệu cá nhân bị lộ ngoài ý muốn, hãy mở issue **chỉ
nêu đường dẫn file và loại dữ liệu**, không dán nội dung dữ liệu đó vào issue.
