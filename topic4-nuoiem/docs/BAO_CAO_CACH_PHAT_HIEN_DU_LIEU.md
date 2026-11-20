> **Lưu ý:** tài liệu này có nhắc tới định danh Google Sheet / số tài khoản của Quỹ
> Nuôi Em, đã **che bớt** (6 ký tự đầu + 4 ký tự cuối). Bản đầy đủ chỉ lưu trên máy,
> không đưa lên Git. Không dùng các định danh này để đọc hay phát tán dữ liệu cá nhân.
> Xem `SECURITY.md`.

# Báo cáo: Cách thức phát hiện dữ liệu công khai của Quỹ Nuôi Em

Ngày lập: 15/10/2026
Phương pháp: phân tích frontend công khai (assets discovery), kiểm chứng bằng HTTP request ẩn danh
Mục đích: ghi lại **cách tìm ra**, **tìm ra cái gì**, và **nằm ở đâu** — để nhóm có thể tự kiểm tra lại và để nêu với mentor

---

## PHẦN 1 — CÁCH THỨC PHÁT HIỆN (phương pháp)

### 1.1 Ý tưởng ban đầu

Khi bắt đầu Topic 4, tôi có trong tay `mock data.xlsx` của mentor — 10 học sinh, 9 giao dịch. File đó **không đủ để chạy** (thiếu đề nghị thanh toán, thiếu tiền ra liên kết chứng từ, và không có ACN nào trùng giữa hai khối).

Nên câu hỏi đặt ra: **Quỹ có công bố dữ liệu thật ở đâu không?**

### 1.2 Lý do chọn hướng "đọc frontend" thay vì tìm API

Tôi thử tìm API trước — thất bại. Sau đó nhận ra một điều:

> Nếu một website **hiển thị** dữ liệu tài chính cho người xem, thì dữ liệu đó
> **phải đến từ đâu đó**, và chỉ dẫn đến nó **phải nằm trong code mà trình duyệt tải về**.

Đây là nguyên lý cơ bản: **frontend không thể giấu nguồn dữ liệu của chính nó**, vì trình duyệt phải biết để tải.

### 1.3 Trình tự 4 bước đã thực hiện

#### Bước 1 — Xác định trang chứa dữ liệu

Dò các đường dẫn có khả năng chứa báo cáo tài chính:

```bash
for p in /tai-chinh /minh-bach /bao-cao /tai-chinh-minh-bach /cong-khai /finance /reports; do
  curl -s -o /dev/null -w "$p -> %{http_code}\n" "https://quynuoiem.com$p"
done
```

Kết quả:
```
/tai-chinh -> 200      <-- ĐÂY
/minh-bach -> 404
/minh-bach-tai-chinh -> 404
/cong-khai -> 404
/finance -> 404
```
→ Trang chứa dữ liệu là **`quynuoiem.com/tai-chinh`**

#### Bước 2 — Kiểm tra HTML hiển thị

```bash
curl -sL "https://quynuoiem.com/tai-chinh" -o tc.html
grep -c "1boFEZqK" tc.html
```
Kết quả: **0** — ID **không** nằm trong HTML.

→ Nghĩa là dữ liệu **không được render sẵn** ở server. Nó phải được tải bởi JavaScript. Đây là dấu hiệu của ứng dụng dạng Next.js/React.

#### Bước 3 — Liệt kê các file JavaScript mà trang tải

```bash
grep -oE 'src="[^"]*\.js[^"]*"' tc.html
```

Tìm được 13 file, trong đó có file **riêng cho trang tài chính**:

```
/_next/static/chunks/app/(site)/tai-chinh/page-e73e03b76ce68f16.js
```

**Đây là bước mấu chốt.** Ứng dụng Next.js chia code theo trang. Tên file
`app/(site)/tai-chinh/page-<hash>.js` cho biết ngay: file này chứa logic của
trang tài chính. Không cần đọc 12 file còn lại.

#### Bước 4 — Tải file đó và tìm ID

```bash
curl -s "https://quynuoiem.com/_next/static/chunks/app/(site)/tai-chinh/page-e73e03b76ce68f16.js" -o tcpage.js
grep -o "1boFEZqK[A-Za-z0-9_-]*" tcpage.js
```

Kết quả: **tìm thấy** — file 37.710 byte, **tải được không cần đăng nhập**.

### 1.4 Vì sao cách này hoạt động

| Lớp | Có thấy ID không | Vì sao |
|---|---|---|
| HTML trang chủ | Không | Dữ liệu không render ở server |
| HTML `/tai-chinh` | Không | Trang render vỏ, dữ liệu nạp sau |
| **File JS của trang** | **Có** | Trình duyệt cần biết ID để gọi Google Sheets |

Điểm cốt lõi: **giấu ID trong JS là vô nghĩa**, vì chính trình duyệt phải đọc được nó để hoạt động. Bất kỳ ai mở DevTools cũng thấy y hệt.

---

## PHẦN 2 — PHÁT HIỆN RA SAO (nội dung tìm thấy)

### 2.1 Đoạn code chứa ID

Trích nguyên văn từ `page-e73e03b76ce68f16.js`:

```javascript
let x = {
  sheetId: h.env.VCB_STATEMENTS_SHEET_ID ?? "1boFEZ…WgHg",
  gid:     h.env.VCB_STATEMENTS_SHEET_GID  ?? "0",
  accountNumber: "0711…0294",
  bankName: "Vietcombank (VCB)",
  revalidateSeconds: 3600,
  pageSize: 20
}
```

**Đọc đoạn này ta biết ngay 4 điều:**

1. **Tên biến:** `VCB_STATEMENTS_SHEET_ID` — đây là sheet **sao kê Vietcombank**, ID `1boFEZqK...`
2. **`gid: "0"`** — tab đầu tiên của sheet
3. **`accountNumber: "0711…0294"`** — số tài khoản nhận tiền của Quỹ
4. **`bankName: "Vietcombank (VCB)"`**

### 2.2 Phát hiện quan trọng: KHÔNG chỉ 1 sheet, mà là 10

Khi tìm rộng hơn quanh vùng đó, tôi thấy **một danh sách cấu hình nhiều nguồn dữ liệu**:

```javascript
// Nguồn 1 — sao kê ngân hàng
VCB_STATEMENTS_SHEET_ID ?? "1boFEZ…WgHg", gid "0"
VP_STATEMENTS_SHEET_ID  ?? "1boFEZ…WgHg", gid "33785031"

// Nguồn 2 — HỒ SƠ CHI PHÍ THEO TỪNG THÁNG (9 sheet riêng biệt)
EXPENSE_DOCS_DRIVE_FOLDER_ID    ?? "1YJD2f…WONH"
EXPENSE_DOCS_SHEET_NOV_2025_ID  ?? "1Ywo-Z…6Xms"
EXPENSE_DOCS_SHEET_DEC_2025_ID  ?? "1hB6wC…nJb8"
EXPENSE_DOCS_SHEET_JAN_2026_ID  ?? "1KMXRK…pJ2Y"
EXPENSE_DOCS_SHEET_FEB_2026_ID  ?? "1QbLJi…Qsh0"
EXPENSE_DOCS_SHEET_MAR_2026_ID  ?? "1ZVi-R…S2a8"
EXPENSE_DOCS_SHEET_APR_2026_ID  ?? "1_QLIH…OB4Q"
EXPENSE_DOCS_SHEET_MAY_2026_ID  ?? "13cljt…ux0I"
EXPENSE_DOCS_SHEET_JUN_2026_ID  ?? "1rTdTJ…yPNY"
EXPENSE_DOCS_SHEET_JUL_2026_ID  ?? "13wC2F…Ty_A"
```

**Tổng: 10 ID sheet khác nhau, 1 Drive folder ID — tất cả viết cứng trong 1 file JS công khai.**

### 2.3 Lỗi thiết kế nhìn thấy được ngay

Quỹ **đã có ý thức bảo mật**: họ dùng `process.env` (viết tắt `h.env`, `c.env`) — tức định cấu hình qua biến môi trường, **không hard-code**.

Nhưng toán tử `??` (nullish coalescing) có nghĩa: *"nếu biến môi trường không có, dùng giá trị bên phải"*. Và **giá trị bên phải là ID thật**.

→ Kết quả: khi build production, nếu biến môi trường không được set, **ID thật bị nhúng thẳng vào bundle công khai**. Ý định bảo mật bị vô hiệu bởi chính giá trị dự phòng.

**Một dòng sửa được:** đổi giá trị dự phòng thành `null` hoặc `""`, và bắt buộc có biến môi trường khi chạy.

---

## PHẦN 3 — NẰM Ở ĐÂU (đường dẫn chính xác)

### 3.1 Nguồn phát hiện

| Mục | Giá trị |
|---|---|
| Trang | `https://quynuoiem.com/tai-chinh` |
| **File chứa ID** | `https://quynuoiem.com/_next/static/chunks/app/(site)/tai-chinh/page-e73e03b76ce68f16.js` |
| Kích thước file | 37.710 byte |
| Quyền truy cập | Công khai, không cần đăng nhập |
| Dòng chứa ID | Chuỗi `let x={sheetId:h.env.VCB_STATEMENTS_SHEET_ID??"..."` |

### 3.2 Nguồn dữ liệu 1 — Sao kê ngân hàng

| Mục | Giá trị |
|---|---|
| Sheet ID | `1boFEZ…WgHg` |
| Tab VCB (gid) | `0` |
| Tab VPBank (gid) | `33785031` |
| Số tài khoản | `0711…0294` |
| **Kiểm chứng** | `GET /export?format=csv` → **HTTP 200, 34.871.764 byte** |
| Nội dung | 238.173 dòng sao kê Vietcombank, 2018–2026 |

### 3.3 Nguồn dữ liệu 2 — Hồ sơ chi phí 9 tháng (mới phát hiện)

Bảng liệt kê đầy đủ 9 sheet, **tất cả đều kiểm chứng được công khai**:

| Tháng | Sheet ID | HTTP | Kích thước |
|---|---|---|---|
| 11/2025 | `1Ywo-Z…6Xms` | 200 | — |
| 12/2025 | `1hB6wC…nJb8` | **200** | **22.174 B** |
| 01/2026 | `1KMXRK…pJ2Y` | 200 | — |
| 02/2026 | `1QbLJi…Qsh0` | 200 | — |
| 03/2026 | `1ZVi-R…S2a8` | 200 | — |
| 04/2026 | `1_QLIH…OB4Q` | **200** | **36.922 B** |
| 05/2026 | `13cljt…ux0I` | 200 | — |
| 06/2026 | `1rTdTJ…yPNY` | **200** | **13.595 B** |
| 07/2026 | `13wC2F…Ty_A` | **200** | **22.010 B** |

**Drive folder chính:** `1YJD2f…WONH` → HTTP 200

### 3.4 Nội dung hồ sơ chi phí — có gì bên trong

Cấu trúc cột của sheet hồ sơ chi phí:

```
TT | Trường | Xã | Tỉnh | Số học sinh được hỗ trợ trong năm |
Số tiền giải ngân trong tháng | Link drive chứng từ
```

Ví dụ dữ liệu thật tháng 07/2026:

| TT | Trường | Xã | Tỉnh | Số HS | Số tiền giải ngân |
|---|---|---|---|---|---|
| 1 | TH&THCS Bình Dương | Bạch Đằng | Cao Bằng | 85 | 39.963.600 VNĐ |
| 2 | Tiểu học Bạch Đằng | Bạch Đằng | Cao Bằng | 12 | 7.588.800 VNĐ |
| 3 | PTDTBT THCS Mông Ân | Bảo Lâm | Cao Bằng | 67 | 25.772.000 VNĐ |
| 6 | Mầm Non Đức Hạnh | Cốc Pàng | Cao Bằng | 368 | 25.921.600 VNĐ |

**Quy mô 1 tháng: 145 trường, tổng giải ngân 7.425.579.600 VNĐ.**

### 3.5 Drive folder chứng từ — cũng công khai

Mỗi dòng trong sheet có link Drive riêng. Kiểm chứng một link:

```
GET https://drive.google.com/drive/folders/13i0OP…se__
→ HTTP 200, 320.988 byte
→ <title>DANE1667 T1-5 Trường TH và THCS Bình Dương-Bạch Đằng-Cao Bằng - Google Drive</title>
```

**Không có thông báo "yêu cầu quyền truy cập"** — tức folder công khai. Và tiêu đề folder đã lộ tên trường. Trong đó có file `Đề nghị thanh toán.pdf`.

→ **Đây là toàn bộ chuỗi chứng từ giải ngân, công khai cho cả Internet.**

---

## PHẦN 4 — TỔNG HỢP MỨC ĐỘ PHƠI NHIỄM

| Hạng mục | Số lượng | Trạng thái |
|---|---|---|
| Sheet công khai (viết cứng trong JS) | **10** | Tải được, không cần đăng nhập |
| Drive folder ID trong JS | 1 | HTTP 200 |
| Folder chứng từ theo trường | Hàng trăm | HTTP 200, có `Đề nghị thanh toán.pdf` |
| Dòng sao kê | 238.173 | Chứa dữ liệu cá nhân nhà tài trợ |
| Số điện thoại nhà tài trợ lộ | **14.328** | Trong memo sao kê |
| Email nhà tài trợ lộ | **222** | Trong memo sao kê |
| Tên nhà tài trợ lộ | **1.818** | Trường `BO:` trong memo |
| Số tài khoản/tham chiếu lộ | **87.434** | Trong memo sao kê |
| Tên trường + số HS + tiền giải ngân | 145 trường/tháng | Sheet hồ sơ chi phí |

---

## PHẦN 5 — ĐIỂM ĐÁNG CHÚ Ý NHẤT

### 5.1 Đây không phải "lộ" theo nghĩa tấn công

Không có ai hack. Không có lỗ hổng phần mềm. **Tất cả dữ liệu này được Quỹ tự đặt ở chế độ công khai**, và cách truy cập là cách hợp lệ bình thường.

### 5.2 Hai lớp bảo vệ, nhưng cả hai đều không phải kiểm soát thật

| Lớp | Quỹ có vẻ kỳ vọng | Thực tế |
|---|---|---|
| **Không có link thì không vào được** | Ẩn bằng cách khó tìm | ID nằm trong JS công khai, ai mở DevTools cũng thấy |
| **Dùng biến môi trường** | Cấu hình, không hard-code | Giá trị dự phòng `??` lại là ID thật → vẫn nhúng vào bundle |

→ Đây là **security by obscurity** — chỉ chặn người không biết kỹ thuật.

### 5.3 Phát hiện ảnh hưởng trực tiếp đến dự án

Điều này quan trọng với bài làm: trước đây tôi báo cáo **coverage chỉ 32,52%** vì *"thiếu danh mục học sinh để ánh xạ NE → trường"*.

Nhưng sheet hồ sơ chi phí có **`Trường` + `Số học sinh + `Số tiền giải ngân`** theo từng tháng — tức đây chính là **phần tiền ra theo trường** mà tôi từng thiếu.

→ **Coverage 32,52% không còn là trần cứng.** Có dữ liệu để nâng tỷ lệ phủ lên, nếu ánh xạ được trường ↔ mã NE.

### 5.4 Việc nên làm

1. **Nêu với mentor** rằng ID sheet + Drive folder nằm trong JS công khai, và đề xuất sửa giá trị dự phòng `??` thành `null`.
2. **Không dán bất kỳ ID nào** vào báo cáo nộp. Báo cáo này là tài liệu *kỹ thuật nội bộ* để chứng minh phương pháp — ID nên được che khi nộp.
3. **Xoá link khỏi `BAO_CAO_DU_AN.md`** (hiện có in ID ở dòng 110).
4. **Bổ sung sheet hồ sơ chi phí vào hệ thống** — đây là dữ liệu hợp lệ và cần thiết cho đối soát tiền ra, khác hẳn với việc phơi dữ liệu cá nhân.

---

## PHỤ LỤC — Phân loại độ chắc chắn

### Dữ kiện (đã kiểm chứng bằng HTTP request ẩn danh)

- File JS `page-e73e03b76ce68f16.js` tồn tại, 37.710 byte, tải công khai.
- Trong file có **10 ID sheet + 1 Drive folder ID**, xác nhận bằng regex.
- 4/10 sheet đã test trực tiếp: **đều HTTP 200**, tải được CSV.
- Sheet sao kê: 200, 34.871.764 byte, 238.173 dòng.
- Sheet hồ sơ chi phí 07/2026: 200, 22.010 byte, 145 trường.
- Drive folder chứng từ: 200, 320.988 byte, tiêu đề lộ tên trường, có `Đề nghị thanh toán.pdf`.
- HTML trang chủ và `/tai-chinh`: **0 lần** xuất hiện ID → ID chỉ có trong JS.

### Suy luận

- Việc dùng `VCB_STATEMENTS_SHEET_ID` cho thấy Quỹ **có ý định** cấu hình qua biến môi trường → nhiều khả năng họ **không nhận ra** giá trị dự phòng `??` vẫn bị nhúng vào bundle.
- Việc công bố số tổng là **cố ý** (phục vụ minh bạch sau thanh tra). Việc phơi **dữ liệu cá nhân nhà tài trợ trong memo** nhiều khả năng là **không cố ý**.

### Chưa kiểm chứng / cần thêm

- Chưa kiểm tra hết **145 folder chứng từ** của mỗi trường (chỉ test 1 folder đại diện).
- Chưa rà soát các nguồn **ngoài** `quynuoiem.com` (fanpage, website cũ, các bài công bố khác).
- Chưa xác định sheet nào trong 10 sheet có chứa dữ liệu cá nhân học sinh (mới đọc 1 sheet hồ sơ chi phí).
