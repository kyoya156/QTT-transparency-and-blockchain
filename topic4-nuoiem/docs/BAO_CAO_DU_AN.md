> **Lưu ý:** tài liệu này có nhắc tới định danh Google Sheet / số tài khoản của Quỹ
> Nuôi Em, đã **che bớt** (6 ký tự đầu + 4 ký tự cuối). Bản đầy đủ chỉ lưu trên máy,
> không đưa lên Git. Không dùng các định danh này để đọc hay phát tán dữ liệu cá nhân.
> Xem `SECURITY.md`.

# BÁO CÁO DỰ ÁN — Nuôi Em Topic 4

## Bảng điều khiển minh bạch tài chính

> Ngày: 15/10/2026 · Swinburne Project A/B · Quỹ Nuôi Em  
> Phạm vi: Topic 4 (làm trước) → Topic 2 (làm sau)

**Cách vào xem:** mở PowerShell, chạy `run.ps1`, rồi mở  
**<http://127.0.0.1:8765>**

---

# PHẦN 1 — ĐỀ BÀI LÀ GÌ

## 1.1 Bối cảnh nhóm

| Thành viên                 | Phụ trách                                      |
| -------------------------- | ---------------------------------------------- |
| 2 bạn AI                   | Topic 2 — Chatbot/RAG, làm độc lập trước       |
| 1 bạn Data Science         | Topic 4 — cùng bạn (Cyber)                     |
| 1 bạn Cyber Security (bạn) | Topic 4 — security design, control, evaluation |

Yêu cầu của nhóm: giải quyết **vấn đề thật** của doanh nghiệp, đủ chiều sâu cho đồ án tốt nghiệp, **đo lường được**, không chỉ là một màn hình demo.

## 1.2 Vấn đề doanh nghiệp

Handoff của mentor ghi rõ: "Nhu cầu không chỉ là dashboard đẹp, mà là một **chuỗi bằng chứng có thể kiểm tra**":

```
Tiền vào → nhận diện giao dịch → ghép ACN → phân bổ nguồn tiền
→ học sinh/điểm trường → đề nghị chi của trường → phê duyệt
→ giao dịch tiền ra → chứng từ/xác nhận → báo cáo công khai có phiên bản
```

**Sự kiện thật làm đề bài nặng hơn** (Quỹ công bố 05/06/2026): cơ quan chức năng đã xác minh Quỹ (17/12/2025 – 24/04/2026). Kết luận: **không có vi phạm hình sự, không chiếm đoạt**. Nhưng Quỹ tự nhận đã vận hành dự án lớn **qua tài khoản cá nhân**, dòng tiền lẫn lộn, không theo chuẩn kế toán, và **quản lý bằng Excel gây ra sai mã, trùng mã và lỗi dữ liệu**.

→ Topic 4 không phải "làm dashboard cho đẹp". Nó là **câu trả lời trực tiếp** cho một thất bại quản trị đã được ghi nhận công khai.

## 1.3 Trong phạm vi / ngoài phạm vi

**Trong phạm vi MVP:** chỉ tiền vào + quan hệ dữ liệu. Dashboard tổng quan, tìm kiếm/lọc, quan hệ ACN–học sinh–trường, truy vết lineage, phát hiện vấn đề chất lượng dữ liệu, API chỉ đọc.

**Ngoài phạm vi MVP:** đăng nhập/phân quyền production, webhook Casso thật, luồng tiền ra có chứng từ, chữ ký số, chatbot AI.

## 1.4 Nguyên tắc bắt buộc từ bài toán (Notion)

- Không công bố dữ liệu trẻ em ngoài các trường đã được duyệt.
- AI **chỉ gợi ý**, con người phê duyệt.
- Mọi thay đổi ghép mã tài chính cần **audit log**.
- **"Excel-compatible first"**.
- Dashboard công khai chỉ hiển thị số tổng hợp / dữ liệu đã duyệt.
- **Mobile-first** — "vì hành trình người dùng thường đi từ fanpage/Facebook sang website".

Thứ tự ưu tiên trong 10 topic: Topic 2 là **#2**, Topic 4 là **#5**. Nhưng thứ tự *triển khai* là Topic 4 trước — quyết định của nhóm, và nó hợp lý (xem §7).

---

# PHẦN 2 — FILE MẪU MENTOR CUNG CẤP ĐƯỢC GÌ

## 2.1 Nội dung

File `C:\Users\Tuna\Downloads\mock data.xlsx`, một worksheet, **ba khối dữ liệu**:

1. Hồ sơ học sinh và quan hệ với ACN, NE, trường/điểm trường.
2. Giao dịch chuyển khoản sau xử lý/ghép mã.
3. Sao kê trước xử lý cùng kết quả phân loại.

## 2.2 Nó cho được gì

- Đủ để dựng MVP đối soát tiền vào.
- Cho biết **hình dạng** của schema: giao dịch, ACN, NE, học sinh, trường là các bảng riêng.
- Cho biết quy trình nghiệp vụ: nhận ACN → chuyển khoản → tra mã.

## 2.3 Nó **KHÔNG** cho được gì — và đây là điểm quan trọng nhất

Bản review đầu tiên (tôi chạy thật, 7/7 test pass) phát hiện một điều nghiêm trọng:

> **Các mã ACN trong khối giao dịch mẫu KHÔNG trùng với mã ACN trong khối học sinh.**

Nghĩa là **không thể chứng minh một chuỗi hoàn chỉnh** `TX → ACN → AL → NE → HS → TR`. Giá trị cốt lõi của sản phẩm — nối tiền với em cụ thể — **vẫn chưa được chứng minh** bằng file của mentor.

Đây là **lỗ hổng dữ liệu thật**, không phải lỗi code.

## 2.4 Các câu hỏi cần mentor xác nhận

1. `Mã học sinh chính` có bền vững qua nhiều năm không?
2. `Mã NE trên ảnh` đại diện học sinh hay suất tài trợ?
3. Một giao dịch hỗ trợ nhiều NE thì **số tiền từng NE lưu ở đâu**?
4. Một ACN có thể thanh toán bằng nhiều giao dịch không?
5. Khi ACN phân bổ lại, hệ thống có giữ toàn bộ lịch sử?
6. Ngày trong file dùng `dd/mm`, `mm/dd` hay tháng/năm học?
7. Đơn giá `170` là 170 đồng hay 170.000 đồng?
8. ACN ↔ NE ↔ học sinh là 1–1, 1–n, hay thay đổi theo năm?
9. Trường và điểm trường là một entity hay quan hệ cha–con?
10. File/hệ thống nào là **source of truth** cho mỗi entity?

Kèm yêu cầu: **20–50 dòng đã ẩn danh cho mỗi nhóm**, giữ nguyên khoá liên kết, và quan trọng nhất là **ít nhất một chuỗi liên kết hoàn chỉnh**.

---

# PHẦN 3 — HƯỚNG GIẢI QUYẾT

## 3.1 Quyết định lớn nhất: bỏ file mẫu, dùng dữ liệu thật

Đây là bước ngoặt của dự án. Thay vì tiếp tục đắp code lên file mẫu khiếm khuyết, tôi đi tìm **dữ liệu thật của Quỹ**.

**Cách tìm:** đọc bundle JavaScript của trang tài chính trên web mới (`quynuoiem.com`) và phát hiện báo cáo tài chính **không phải API** mà là **Google Sheet**. Lấy được ID sheet nhúng trong code:

```
docs.google.com/spreadsheets/d/1boFEZ…WgHg
```

→ **238.173 dòng sao kê Vietcombank thật, 2018–2026**, do chính Quỹ công bố.

Điểm mấu chốt: file này **có** số liệu tổng do Quỹ công bố (Thu 553.550.809.401 / Chi 553.541.302.920). Nghĩa là mọi tính toán của tôi giờ **kiểm chứng được** với một con số bên ngoài, thay vì tự so với chính mình.

## 3.2 Kiến trúc dữ liệu

**Không nối thẳng giao dịch với học sinh.** Một giao dịch ngân hàng có thể viện dẫn **tới 20 mã NE**. Nếu nhân số tiền cho số mã thì tổng tiền vào phồng lên nhiều lần.

```
BankTransaction ──< TransactionAllocation >── ACN/Donor
       │                       │
       │                       └── NE / Student / School
       │
       └── ReconciliationStatus + Exception + AuditEvent
```

Ba quy tắc:

- Tiền lưu **một lần** ở giao dịch; phần chia lưu ở bảng nối.
- **Bất biến:** tổng các dòng phân bổ **phải bằng đúng** tổng giao dịch được liên kết.
- Idempotency key để webhook/nhập lại **không làm tăng tổng tiền**.

## 3.3 Hiệu năng

Đo trên **1 triệu dòng** thật (không phải phỏng đoán):

| Truy vấn                                            | Trước        | Sau        |
| --------------------------------------------------- | ------------ | ---------- |
| `WHERE direction=? ORDER BY tx_time DESC LIMIT 100` | **4.188 ms** | **1,6 ms** |

Nguyên nhân: thiếu thống kê `sqlite_stat1` nên SQLite chọn kế hoạch thảm hoạ. Sửa bằng `ANALYZE` + chỉ số tổng hợp `idx_tx_direction_time`.

Ghi chú kèm theo: `OFFSET 500000` chỉ mất **34 ms** — tức `OFFSET` **không** phải nút cổ chai. Ghi lại để không ai tối ưu sai chỗ.

## 3.4 Bảo mật — phần của bạn

| Kiểm soát              | Cách làm                                                |
| ---------------------- | ------------------------------------------------------- |
| RBAC / least privilege | Vai trò seed trong CSDL (**chưa cưỡng chế**)            |
| Maker-checker          | Maker không thể tự duyệt → `PermissionError`            |
| Audit log              | Append-only, mỗi dòng chứa hash dòng trước              |
| Trigger chặn sửa/xoá   | UPDATE/DELETE thường bị chặn ở tầng CSDL                |
| PII guard              | Danh sách trường cấm kiểm tra trên **mọi** phản hồi API |
| Chống trùng            | Idempotency key SHA-256                                 |
| Chỉ đọc                | Mọi POST/PUT/PATCH/DELETE → 405                         |

---

# PHẦN 4 — ĐÃ LÀM NHƯ NÀO

## 4.1 Bảng thành phần

| File                  | Vai trò                                                             |
| --------------------- | ------------------------------------------------------------------- |
| `build_database.py`   | Đọc CSV → SQLite. Định vị cột **theo tiêu đề**, không theo toạ độ ô |
| `parsers.py`          | Tách mã ACN/NE khỏi nội dung chuyển khoản                           |
| `schema.py`           | 16 bảng + chỉ số                                                    |
| `reconciliation.py`   | Chia tiền, audit chain, maker-checker                               |
| `app.py`              | HTTP API chỉ đọc (9 endpoint)                                       |
| `verify_real_data.py` | Đối chiếu với số Quỹ công bố                                        |
| `static/`             | Giao diện (HTML/CSS/JS, mobile-first, không build step)             |
| `tests/test_app.py`   | **69 bài kiểm thử**                                                 |

## 4.2 Bốn lỗi thật đã tìm ra và sửa

### Lỗi 1 — Mã NE giả sinh từ ngày và số trace (nghiêm trọng nhất)

Bộ tách mã đọc **mọi** chuỗi `NE<số>`, kể cả khi `<số>` là metadata ngân hàng:

```
483019.171024.133756.BCG FOUNDATION NUOI 50 BE - NE00298-171024-13:36:06
```

Câu này cho ra **ba** mã: `NE00013`, `NE00298`, `NE171024`. Chỉ `NE00298` là thật.

**Hệ quả:** 145.000.000 đ bị chia ba → mã thật chỉ được ghi **48.333.333 đ**.

Cách sửa **không phải** siết thành `NE\d{5}` — làm vậy mất ~150 nghìn tham chiếu viết văn xuôi như `NE77, NE78, NE79`. Cách đúng:

1. Cắt tiền tố metadata ngân hàng (`strip_bank_metadata`).
2. Xoá giờ `HH:MM:SS` trước khi dò chuỗi.
3. Chặn số hạng ở **5 chữ số**.
4. Chỉ cho 6 chữ số đi qua khi nằm trong **lô liệt kê tường minh**: `NE140370, 140371, 140372`, kể cả dạng viết tắt `NE121215,16,17`.

**Kết quả:** 342 dòng có mã giả → **2** (đúng hai lô mã thật). Tổng tiền phân bổ **không đổi một đồng** — chứng minh sửa đúng mà không đụng tiền thật.

### Lỗi 2 — 7 giao dịch thật bị xem nhầm là trùng

Sao kê có 7 nhóm cùng số chứng từ + thời gian + số tiền nhưng **nội dung khác nhau**. Khoá idempotency cũ xoá nhầm chúng → mất 7 dòng và **6.274.000 đ**.

**Kết quả:** khoá mới dùng định danh dòng ổn định. Tiền vào giờ khớp số Quỹ công bố **tuyệt đối, lệch 0 đồng** (trước là −6.274.000).

### Lỗi 3 — Cột ngày bị lẫn số dư (phát hiện hôm nay)

Ô ngày trong CSV chứa **hai giá trị** ngăn bởi xuống dòng:

```
'08/02/2018\nYG61.000093'        ← ngày + số chứng từ
'31/12/2020 9774.0008477811'     ← ngày + SỐ DƯ (khi xuống dòng thành khoảng trắng)
```

Hàm parse cũ chỉ tách `\n`, nên với dạng thứ hai nó lưu cả số dư vào trường ngày.

**Hệ quả:** **65.654 dòng (27,6%)** có ngày rác. Cột "khoảng thời gian" trên dashboard hiện `01-01-2024 5017 - 01218` — vô nghĩa. Và **27,6% giao dịch bị sắp xếp sai chỗ**.

**Tin tốt:** số tiền và số dư **không** bị lẫn (số dư nằm ở cột riêng, và tổng khớp tuyệt đối với số Quỹ công bố). Đây thuần là lỗi trường ngày.

**Kết quả:** ngày giờ sạch **2018-02-08 → 2026-02-25**, đúng phạm vi sao kê. Thêm 7 bài test để không tái diễn.

### Lỗi 4 — Hai bản cài đặt cho một kiểm soát an ninh

`app.py` từng **tự tính lại hash** chuỗi kiểm toán thay vì gọi `reconciliation.AuditChain.verify()`. Hai bản cài đặt của cùng một kiểm soát nghĩa là chỉ cần sửa một bên là chúng **âm thầm bất đồng**. Đã gom về một chỗ.

---

# PHẦN 5 — KẾT QUẢ RA SAO

## 5.1 Số liệu thật trên 238.173 dòng

| Chỉ số                  | Giá trị                                |
| ----------------------- | -------------------------------------- |
| Tổng giao dịch          | **238.173** (khớp CSV, không mất dòng) |
| Tiền vào                | 236.030 dòng · **553.550.809.401 đ**   |
| Tiền ra                 | 2.143 dòng · **553.541.302.920 đ**     |
| Dòng phân bổ theo mã NE | **140.661**                            |
| Mã NE phân biệt         | **31.050**                             |
| Thời gian phủ           | 2018-02-08 → 2026-02-25                |
| Cần rà soát             | 125.670 dòng                           |

## 5.2 Đối chiếu với số Quỹ tự công bố

| Kiểm tra                | Kết quả                         |
| ----------------------- | ------------------------------- |
| Tiền vào vs Quỹ công bố | **khớp tuyệt đối, lệch 0 đồng** |
| Tiền ra vs Quỹ công bố  | **khớp tuyệt đối, lệch 0 đồng** |
| Các phần = tổng         | **lệch 0 đồng**                 |
| Số dòng vs CSV          | **khớp, 238.173**               |


Điểm quan trọng: `verify_real_data.py` so với **số Quỹ công bố**, không so với số do chính code này sinh ra. Không có ngưỡng dung sai — lệch 1 đồng là thất bại.

## 5.3 Độ phủ — và đây là con số cần nói thật

**32,57%** tiền vào gắn được ít nhất một mã NE.

- Gắn được: **180.312.040.597 đ**
- Chưa gắn: **373.238.768.804 đ** (125.670 giao dịch)

Con số này **không phải lỗi hệ thống**. Theo quy định của Quỹ, khoản không gắn được mã **không hoàn lại và chuyển vào quỹ vô danh (xây trường)**. Nên đây là **đặc điểm nghiệp vụ**, và hệ thống **cố ý hiển thị nó** trên hàng đợi ngoại lệ thay vì ẩn đi.

## 5.4 Xử lý ngoại lệ — quyết định thiết kế

125.670 dòng vấn đề được gộp thành **1** mục hành động được.

Lý do: một hàng đợi 125.670 dòng là **một kiểm soát không hoạt động được**, vì không ai đọc hết. Gộp theo nhóm kèm số lượng và giá trị đang gặp rủi ro thì mới dùng được.

## 5.5 Kiểm thử

| Lớp                    | Kết quả                    |
| ---------------------- | -------------------------- |
| Unit tests             | **69 bài, OK** (~4 giây)   |
| Đối chiếu dữ liệu thật | **ALL CHECKS PASSED**      |
| HTTP end-to-end        | **ALL HTTP CHECKS PASSED** |

## 5.6 Vector tấn công đã kiểm chứng

| Vector                                  | Kết quả                             |
| --------------------------------------- | ----------------------------------- |
| `' OR 1=1--` trong `q`, `tx`, `ne`      | Vô hại — tham số hoá toàn bộ        |
| Path traversal `/../app.py`, `/%2e%2e/` | Bị chặn                             |
| POST/PUT/PATCH/DELETE                   | 405                                 |
| Tìm kiếm nội dung sao kê thô            | Trả 0 dòng                          |
| SĐT / số tiền làm từ khoá               | Trả 0 dòng                          |
| Trường PII trong phản hồi               | Bị chặn + có test cho chính bộ chặn |
| Sửa/xoá audit log                       | Chuỗi đứt, báo đúng `id`            |
| Maker tự duyệt                          | `PermissionError`                   |
| Nạp lại cùng file                       | Idempotent, tổng không đổi          |

**Còn thiếu:** IDOR/BOLA (chưa có nhiều vai trò), rate limiting, upload chứng từ.

---

# PHẦN 6 — MỘT QUYẾT ĐỊNH BẢO MẬT QUAN TRỌNG

## 6.1 Nội dung chuyển khoản bị chặn khỏi API

Bản đầu của tôi **trả về** nội dung sao kê thô và **cho tìm kiếm** trên đó.

Đó là **lỗ hổng thật**. Nội dung chuyển khoản chứa **tên nhà tài trợ, số tài khoản, số điện thoại**. Cho tìm kiếm full-text nghĩa là biến API công khai thành **công cụ tra cứu dữ liệu cá nhân** — ai cũng dò được "ai đã chuyển tiền" bằng cách thử từ khoá.

**Đã sửa:**

- `raw_description` bị thay bằng `description_masked` ("Đã nhận diện mã: NE05517").
- Tìm kiếm văn xuôi **bị chặn hẳn**.
- Nội dung thô **vẫn nằm trong CSDL** để điều tra nội bộ — handoff yêu cầu giữ raw payload.

**Nguyên tắc:** giữ đủ để điều tra, nhưng không mở thành bề mặt tra cứu.

## 6.2 Giới hạn của audit log — nói thẳng

Audit log là **tamper-evident**, **không phải bất biến tuyệt đối**.

- Trigger chặn UPDATE/DELETE thông thường. ✓
- Hash chain phát hiện thay đổi không được băm lại. ✓
- **Nhưng:** người có toàn quyền CSDL vẫn gỡ được trigger và **xây lại cả chuỗi**.

→ Production cần **neo hash ra hệ thống độc lập** hoặc kho WORM.

---

# PHẦN 7 — HƯỚNG VẬN HÀNH & GIẢI THÍCH

## 7.1 Cách chạy

```powershell
cd "C:\Users\Tuna\WorkBuddy AI\2026-10-15-13-47-28\topic4-nuoiem"
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Mở **<http://127.0.0.1:8765>**

Xây lại database: `python build_database.py data\real_vcb.csv` (~1–2 phút).

## 7.2 Ba lớp kiểm tra — lớp nào cũng phải xanh

```powershell
python -m unittest discover -s tests -v   # 69 bài logic
python verify_real_data.py                 # đối chiếu số Quỹ công bố
python app.py                              # rồi mở trình duyệt kiểm tra
```

`verify_real_data.py` là bài **quan trọng nhất** — nó là bài duy nhất so với nguồn bên ngoài.

## 7.3 Ba điều phải nói khi trình bày

**1. "Số liệu suy ra, không phải số Quỹ đã xác nhận."**  
Quỹ **không** công bố số tiền theo từng mã NE. Số tiền mỗi mã do hệ thống **chia ra** từ giao dịch. Mỗi con số đều mang nhãn `allocation_policy` và giao diện ghi chú rõ. **Không được trích dẫn như số liệu chính thức.**

**2. "Chỉ là một nguồn, một khoảng thời gian."**  
Chỉ có **Vietcombank**, từ **01/01/2018 đến 25/02/2026**. Chưa có VPBank/MB. Không được hiểu là toàn bộ dữ liệu tài chính hiện tại của Quỹ.

**3. "Tiền vào/ra là chuyển động ngân hàng, chưa phải doanh thu/chi phí."**  
Chưa tự động là số kế toán cho tới khi có chứng từ và quy tắc phân loại.

## 7.4 Giao diện có gì

- **Banner** nói rõ số liệu là suy ra — ngay màn hình đầu.
- **4 ô KPI:** tiền vào, tiền ra, mã NE phân bổ được, cần rà soát.
- **Đối soát:** các phần vs tổng, kèm nhãn CÂN KHỚP / LỆCH.
- **Độ phủ:** thanh tỷ lệ + giải thích phần chưa gắn mã.
- **Tra cứu:** nhập mã NE → mở drawer truy vết (giao dịch → từng mã → trường).
- **Hàng đợi ngoại lệ** (gộp nhóm).
- **Nhật ký kiểm toán** + trạng thái chuỗi.
- **Mobile-first:** nền là 1 cột cho màn 360 px, mở rộng ở 560/860 px.

## 7.5 Vì sao Topic 4 trước Topic 2 — quan trọng cho bảo vệ

Topic 2 (chatbot) trả lời câu hỏi **bằng cách đọc dữ liệu đã tách mã**. Nếu việc tách mã sai, chatbot sẽ **nhân sai sót lên** và trả lời sai một cách tự tin — tệ hơn nhiều so với việc chỉ hiển thị sai một ô trên dashboard.

Phần dùng chung đã sẵn: `students`, `schools`, `student_supports`, và trường `ne_code`. Chatbot chỉ cần **API chỉ đọc** và **dữ liệu đã kiểm duyệt** — đúng như handoff yêu cầu.

---

# PHẦN 8 — CHƯA CÓ GÌ (nói thẳng để không bị hỏi khó)

| Hạng mục               | Trạng thái                                                              |
| ---------------------- | ----------------------------------------------------------------------- |
| Đăng nhập / phân quyền | **Chưa có.** Vai trò đã seed trong CSDL nhưng **chưa cưỡng chế**        |
| Luồng chi có chứng từ  | **Mới có schema.** Chưa có API/UI                                       |
| Danh mục học sinh      | **Chưa có.** Nên mã NE → trường hiện "chưa biết", không phải "không có" |
| Webhook Casso          | Chưa có                                                                 |
| Chữ ký số              | Chưa có                                                                 |
| Nguồn VPBank/MB        | Chưa nhập                                                               |
| Dữ liệu sau 25/02/2026 | Chưa có                                                                 |

**Ba việc quan trọng nhất cần làm tiếp:**

1. **Xin mentor một chuỗi end-to-end đã ẩn danh** — đây là việc quan trọng nhất, vì nó chứng minh giá trị cốt lõi của sản phẩm.
2. **Cưỡng chế RBAC** — vai trò đã có, chỉ cần chặn ở tầng API.
3. **Làm luồng tiền ra** (đề nghị chi → phê duyệt → chứng từ) — schema đã sẵn.

---

# PHỤ LỤC — CÁC CÂU HỎI CẦN MENTOR XÁC NHẬN

Ghi rõ **fact / inference / question** để không lẫn:

| Loại          | Nội dung                                                                                      |
| ------------- | --------------------------------------------------------------------------------------------- |
| **Fact**      | Quỹ có quy trình ACN → chuyển khoản → tra mã → công khai tài chính                            |
| **Fact**      | Quỹ từng vận hành qua tài khoản cá nhân; cơ quan chức năng xác minh, không có vi phạm hình sự |
| **Fact**      | Sao kê VCB 238.173 dòng, tổng Thu/Chi khớp số Quỹ công bố                                     |
| **Inference** | Một giao dịch chia đều cho các mã NE nó viện dẫn                                              |
| **Inference** | NE00001S / NE00001T là hai mã, hai nhà tài trợ, một em ăn hai bữa                             |
| **Question**  | Số tiền theo từng mã NE thật sự lưu ở đâu trong hệ thống Quỹ?                                 |
| **Question**  | Mã NE có giữ nguyên khi em được nhà nước tiếp nhận không?                                     |
| **Question**  | Quỹ có thông báo cho nhà tài trợ khi mã NE được gán lại không?                                |
| **Question**  | Đơn giá 170 là 170 đồng hay 170.000 đồng?                                                     |
| **Question**  | Trường tự đăng ký xin hỗ trợ hay phải qua cơ quan giáo dục?                                   |
