# Tự đánh giá mức độ hoàn thiện — Topic 4

Ngày: 17/10/2026
Phạm vi chấm: bản đang chạy tại `data/nuoi_em_mvp.sqlite` (238.173 giao dịch) và bản
deploy công khai.

---

## 1. Kết luận trước, số liệu sau

| Cách chấm | Điểm |
|---|---:|
| **Theo phạm vi Topic 4 đã cam kết** (đối soát tiền vào, minh bạch, mobile) | **77%** |
| **Như một hệ thống Quỹ dùng thật** (có phân quyền, có luồng chi, có đóng kỳ) | **~40%** |

Hai số khác nhau không phải vì chấm lung tung, mà vì **mẫu số khác nhau**. Phần đã
làm được làm khá chắc; phần chưa làm không phải làm dở mà là **chưa có dữ liệu để
làm**.

---

## 2. Bảng điểm theo khu vực

| Khu vực | Trọng số | Điểm | Căn cứ |
|---|---:|---:|---|
| Nạp & làm sạch dữ liệu thật | 20 | **18** | 238.173 dòng; 4 lớp lỗi parser đã sửa; nhập lặp không tăng tổng |
| Đối soát & bất biến | 15 | **15** | khớp 553.550.809.401 đ / 553.541.302.920 đ, lệch **0 đồng**; tổng phân bổ = tổng giao dịch |
| Truy vết tiền → học sinh → trường | 20 | **5** | `students`, `schools`, `student_supports` đều **0 dòng** — chỉ dừng ở mức mã NE |
| API & bảo mật | 15 | **13** | 9 route GET; POST/PUT/PATCH/DELETE → 405; DB `mode=ro`; chặn PII ở tầng phản hồi |
| Giao diện mobile-first | 10 | **8** | 10 khối; breakpoint 360/560/860; CSP-safe; chưa test trên máy thật |
| Kiểm thử | 10 | **9** | 77 test OK (1,2 s); `verify_real_data.py` 10/10; chưa test 1 triệu dòng |
| Tài liệu | 10 | **9** | 13 tài liệu; ERD 11 khoá ngoại; luồng lỗi 5 cổng; báo cáo tổng hợp 11 phần |
| **Tổng** | **100** | **77** | |

---

## 3. Phần đã chắc — có bằng chứng, không phải tự nhận

**Dữ liệu thật, không phải file mẫu.** 238.173 dòng sao kê Vietcombank, 02/2018 →
25/02/2026. File mẫu của mentor có 10 em nên không dùng để chứng minh được gì.

**Khớp số Quỹ tự công bố, lệch 0 đồng.** Đây là tiêu chí mạnh nhất, vì nó so với
nguồn bên ngoài chứ không so với số do chính code sinh ra:

| Chỉ số | Hệ thống | Quỹ công bố | Lệch |
|---|---:|---:|---:|
| Tiền vào | 553.550.809.401 đ | 553.550.809.401 đ | **0** |
| Tiền ra | 553.541.302.920 đ | 553.541.302.920 đ | **0** |

**Bất biến phân bổ giữ được.** Trên cả 110.317 giao dịch có mã, tổng các dòng phân
bổ luôn bằng đúng số tiền giao dịch — 0 trường hợp lệch.

**Không ghi được.** 9 route toàn GET, mọi phương thức ghi trả 405, SQLite mở
read-only. Nên đưa link công khai cũng không ai sửa được dữ liệu.

**PII không ra khỏi API.** `description_masked` thay cho memo thô; tìm kiếm trên
memo thô trả 0 dòng — có test cho chính bộ chặn này.

---

## 4. Phần còn trống — nói thẳng

Đây là chỗ quyết định vì sao không thể gọi là "xong":

| Bảng | Số dòng | Nghĩa là |
|---|---:|---|
| `students` | **0** | không biết mã NE nào là em nào |
| `schools` | **0** | không biết tiền về trường nào |
| `student_supports` | **0** | không có quan hệ nhà tài trợ ↔ học sinh |
| `school_payment_requests` | **0** | chưa có luồng đề nghị chi |
| `disbursements` | **0** | chưa gắn tiền ra với trường |
| `evidence_documents` | **0** | chưa có chứng từ số |
| `approval_tasks` | **0** | maker-checker mới có schema, chưa có thao tác để duyệt |
| `report_periods` | **0** | chưa có đóng kỳ / snapshot báo cáo |

Nói cách khác: hệ thống hiện trả lời được **"tiền vào bao nhiêu, gắn mã nào"**, chưa
trả lời được **"tiền đó tới em nào, trường nào"**. Tỷ lệ phủ 32,52% chính là hệ quả
trực tiếp — không phải lỗi code mà là thiếu danh mục.

Cần phân biệt rõ hai loại thiếu:

- **Thiếu dữ liệu (không sửa bằng code được):** danh mục học sinh, danh mục trường,
  bảng giá theo kỳ. Quỹ giữ, mình không có.
- **Thiếu code (làm được nếu có thời gian):** đăng nhập + cưỡng chế RBAC, đóng kỳ
  báo cáo, endpoint ghi có maker-checker, kiểm thử tải 1 triệu dòng.

---

## 5. Nếu chấm như hệ thống vận hành thật

Theo đúng roadmap trong `IMPLEMENTATION_PLAN.md`:

| Giai đoạn | Trạng thái | Ước lượng |
|---|---|---:|
| A. Xác nhận dữ liệu & nghiệp vụ | 8 câu hỏi cho mentor vẫn chưa có đáp án | 70% |
| B. Hoàn thiện tiền vào | chưa có webhook Casso, parser chưa version, chưa có maker-checker thao tác | 45% |
| C. Tiền ra & chứng từ | chỉ có schema | 10% |
| D. Báo cáo & hiệu năng | chưa đóng kỳ, chưa test 1 triệu dòng | 30% |
| E. Bảo mật | audit có; RBAC mới seed, chưa cưỡng chế; chưa test IDOR | 40% |

Trung bình có trọng số ≈ **40%**.

---

## 6. Làm gì để tăng điểm — xếp theo tỷ lệ ăn / công

| Việc | Tăng | Cần gì |
|---|---:|---|
| Danh mục học sinh (NE → em → trường) | **+10** | dữ liệu từ Quỹ, không phải code |
| Đăng nhập + cưỡng chế RBAC | +4 | code, ~1–2 ngày |
| Đóng kỳ + snapshot báo cáo | +3 | code, ~1 ngày |
| Test 1 triệu dòng + phân trang theo khoá | +3 | code, ~1 ngày |
| Bảng giá theo kỳ + số tháng mỗi em | +3 | dữ liệu + code |

Việc đầu tiên chiếm gần một nửa khoảng trống còn lại, và nó **không phải việc lập
trình**. Đây là câu nên nói với mentor trước khi bàn tới chuyện thêm tính năng.

---

## 7. Trạng thái deploy

- Link: `https://58572998c95f47f58fe38aefe20864dc.sg2.agentos-app.run`
- Đã kiểm tra lại lúc 18:07 ngày 17/10: trang chủ HTTP 200, `/api/summary` trả đúng
  số, `balanced: true`.
- Bản deploy dùng **DB đã ẩn danh** (xoá memo thô), nên không có PII trên host.
- Code trong thư mục deploy **giống hệt** source hiện tại → không cần deploy lại.
- **Rủi ro khi demo:** sandbox ngủ khi không có truy cập. Lần gọi đầu sau khi ngủ
  mất **hơn 25 giây** (lần hai: 0,21 giây). Nên mở link trước giờ demo 5 phút.
