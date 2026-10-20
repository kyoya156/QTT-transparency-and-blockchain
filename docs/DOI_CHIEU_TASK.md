# Đối chiếu 12 task ClickUp với trạng thái thật

Ngày: 20/10/2026
Nguồn task: ClickUp, danh sách giao cho bạn ngày 17/10 (12 mục).
Cách kiểm: mở code và database, không dựa vào trí nhớ.

---

## 1. Bảng đối chiếu

| # | Task | Trạng thái | Bằng chứng trong repo |
|---|---|---|---|
| 1 | Topic 4 Architecture flow diagram | **XONG** | `docs/KIEN_TRUC_DRAWIO.drawio` — 5 lớp, có bản SVG |
| 2 | Schema and ER diagram | **XONG** | `docs/ERD_VA_LUONG_LOI.md` + `.pdf` + `ERD_DRAWIO.drawio`; 11 khoá ngoại lấy từ `PRAGMA foreign_key_list` |
| 3 | Dashboard wireframes | **XONG, khác dạng** | Không có file wireframe — có UI thật `static/index.html` (9 khối). Nếu mentor cần **file wireframe riêng** thì đây là thiếu |
| 4 | Schema and migrations | **MỘT NỬA** | `schema.py` có `SCHEMA_VERSION = "2.0"`, 16 bảng, 24 index. **Không có migration** — đổi schema là dựng lại từ đầu |
| 5 | Excel and CSV import | **XONG** | CSV: `csv` stdlib. XLSX: `openpyxl` (import lazy). Vừa thêm `requirements.txt` |
| 6 | Roles and permissions | **CHƯA** | Bảng `roles` có 6 dòng seed, nhưng **không đăng nhập, không cưỡng chế**. Không có tác dụng gì |
| 7 | Audit log for financial changes | **XONG** | `audit_events` append-only + trigger chặn UPDATE/DELETE + chuỗi hash; API trả `chain_intact` |
| 8 | Privacy rules for children's data | **MỘT NỬA** | Có `FORBIDDEN_FIELDS`, `description_masked`, chặn tìm kiếm memo thô, DB deploy đã ẩn danh. **Thiếu văn bản chính sách** |
| 9 | Embed chatbot in the dashboard | **CHƯA** | Thuộc Topic 2, đã hoãn có chủ đích |
| 10 | Testing with fake data | **XONG** | 77 test, dựng DB tạm + dữ liệu tổng hợp trong `setUp` |
| 11 | Final demo (Beta) | **XONG** | Đã demo 17/10; link + `docs/KICH_BAN_DEMO.md` |
| 12 | Full mobile-first dashboard view | **MỘT NỬA** | Mobile-first CSS, breakpoint 560/860, `viewport-fit=cover`. **Chưa test trên máy thật** |

**Tổng: 7 xong · 3 một nửa · 2 chưa.**

---

## 2. Hai task chưa làm — và vì sao

**Roles and permissions (task 6).** Đây là thiếu sót thật, không phải hoãn. Bảng `roles`
đã tạo và có 6 vai trò, nhưng không có đăng nhập nên không có gì để phân quyền. Muốn
làm phải thêm: session, middleware kiểm vai trò, và ít nhất một endpoint ghi để bảo vệ.
Khoảng 1–2 ngày.

**Embed chatbot (task 9).** Thuộc Topic 2, không phải Topic 4. Hoãn có lý do kỹ thuật:
chatbot trả lời sai mã sẽ nhân sai sót lên, trong khi dashboard chỉ hiển thị sai một ô.
Nên làm sau khi việc tách mã đủ tin cậy.

---

## 3. Ba task "một nửa" — cần nói rõ nửa nào còn thiếu

| Task | Đã có | Còn thiếu | Ai làm được |
|---|---|---|---|
| 4. Migrations | Schema đầy đủ, version field | Công cụ migration (đổi schema không mất dữ liệu) | Code, ~1 ngày |
| 8. Privacy rules | Kiểm soát kỹ thuật đầy đủ | **Văn bản chính sách**: dữ liệu nào lưu, giữ bao lâu, ai xem được, xoá thế nào | Viết, ~2 giờ |
| 12. Mobile | CSS mobile-first đúng | Test trên điện thoại thật (Safari iOS, Chrome Android) | Thử, 15 phút |

Task 8 đáng chú ý: **phần khó đã xong, phần dễ lại chưa làm.** Kiểm soát kỹ thuật
(che PII, chặn tìm kiếm, ẩn danh) đã có và có test; nhưng chưa có một trang văn bản
nói rõ chính sách. Mentor hỏi "chính sách dữ liệu trẻ em của em là gì" thì hiện chưa
có gì để đưa.

---

## 4. Một chỗ tôi phải sửa lại điều mình đã nói

Trước đây tôi nói "**0 thư viện bên thứ ba**". Câu đó **chỉ đúng một phần**:

| Đường chạy | Cần gì |
|---|---|
| Chạy app, đọc API, nhập CSV | **Không cần gì** — chỉ thư viện chuẩn |
| Nhập file Excel `.xlsx` | Cần `openpyxl` |

`build_database.py` import `openpyxl` **bên trong** nhánh XLSX, nên đường CSV vẫn chạy
trên máy trắng. Nhưng repo **không có `requirements.txt`**, nghĩa là ai clone về rồi
thử nhập Excel sẽ gặp `ModuleNotFoundError` mà không biết vì sao.

Đã sửa: thêm `requirements.txt`, ghi rõ openpyxl chỉ cần cho XLSX.

Nên phát biểu lại cho đúng: **"runtime không có phụ thuộc; chỉ đường nhập Excel cần
một thư viện"**. Nói "0 phụ thuộc" mà không kèm điều kiện là nói quá — đúng loại lỗi
mà dự án này đang phê bình ở chỗ khác.

---

## 5. Việc nên làm tiếp, theo thứ tự

1. **Test mobile trên máy thật** — 15 phút, rủi ro bằng 0, mà task 12 đang treo vì đúng việc này.
2. **Viết chính sách dữ liệu trẻ em** — 2 giờ, biến task 8 từ "một nửa" thành "xong".
3. **Roles and permissions** — 1–2 ngày, biến task 6 từ "chưa" thành "xong".
4. Migration — chỉ cần khi schema bắt đầu đổi thường xuyên.
5. Chatbot — Topic 2, sau.
