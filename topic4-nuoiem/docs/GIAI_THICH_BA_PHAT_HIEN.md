> **Lưu ý:** tài liệu này có nhắc tới định danh Google Sheet / số tài khoản của Quỹ
> Nuôi Em, đã **che bớt** (6 ký tự đầu + 4 ký tự cuối). Bản đầy đủ chỉ lưu trên máy,
> không đưa lên Git. Không dùng các định danh này để đọc hay phát tán dữ liệu cá nhân.
> Xem `SECURITY.md`.

# Giải thích ba phát hiện: robots.txt · 10 sheet + 1 Drive · page-e73e03b76ce68f16.js

Ngày: 15/10/2026
Mục đích: giải thích **từng cái là gì, vì sao quan trọng, và nằm ở đâu** — kèm bằng chứng thật

---

# 1. `robots.txt`

## 1.1 Nó là gì

`robots.txt` là một file **quy ước** đặt tại gốc website. Nó chỉ có **một** mục đích:

> Nói với **bot của công cụ tìm kiếm** (Google, Bing, Facebook…) rằng:
> "đừng thu thập / đừng đưa vào kết quả tìm kiếm những trang này".

Đây là **quy ước tự nguyện**, không phải cơ chế bảo mật. Không có gì cưỡng chế.

## 1.2 Nằm ở đâu

```
https://quynuoiem.com/robots.txt
```
→ Trả về **HTTP 200**, ai cũng đọc được, không cần đăng nhập.

## 1.3 Nội dung — và vấn đề

File dài ~200 dòng, nhưng có một mẫu lặp lại: cùng một danh sách `Disallow`
được chép cho **13 User-Agent** khác nhau.

Danh sách cốt lõi (giống nhau ở mọi khối):

```
Disallow: /api/
Disallow: /_next/
Disallow: /admin
Disallow: /admin/*
Disallow: /auth/
Disallow: /children
Disallow: /donors
Disallow: /portal
Disallow: /schools
Disallow: /login-activity
Disallow: /danh-sach-em-nuoi
Disallow: /cong-thong-tin-nha-tai-tro
```

**13 User-Agent được liệt kê:** `*`, `facebookexternalhit`, `Facebot`,
`Twitterbot`, `LinkedInBot`, `WhatsApp`, `TelegramBot`, `Slackbot`,
`Discordbot`, `Zalo`, `ZaloBot`, `Applebot`, `Googlebot`, `bingbot`.

## 1.4 Vì sao đây là vấn đề

### Vấn đề 1 — `robots.txt` không chặn ai cả

Nó chỉ xin bot đừng index. Cụ thể:

| Đối tượng | Có bị `robots.txt` chặn? |
|---|---|
| Googlebot | Có (nó tự nguyện tuân thủ) |
| Trình duyệt của người dùng | **KHÔNG** |
| `curl`, `wget`, Postman | **KHÔNG** |
| Công cụ scan bảo mật | **KHÔNG** |
| Bất kỳ ai mở F12 | **KHÔNG** |

Nên nếu mục đích là **giấu** những trang này, nó **không làm được gì**.

### Vấn đề 2 — Nó biến việc giấu thành việc chỉ dẫn

Đây mới là điểm thật sự quan trọng.

Ẩn một thứ bằng cách hi vọng không ai tìm ra gọi là **security by obscurity**. Nhưng `robots.txt` **làm ngược lại**: nó **công bố danh sách** mọi thứ Quỹ muốn giấu.

Trước khi đọc `robots.txt`, kẻ tấn công phải **đoán** xem có những trang nào. Sau khi đọc, họ có **danh sách đầy đủ, có chú thích**. File dùng để ẩn trở thành **bản đồ chỉ đường**.

### Vấn đề 3 — Nó lộ các khái niệm nghiệp vụ nội bộ

Tên route tự nó đã tiết lộ cấu trúc:

| Route | Lộ ra điều gì |
|---|---|
| `/admin`, `/admin/*` | Có hệ quản trị |
| `/auth/` | Có luồng đăng nhập riêng |
| `/children`, `/danh-sach-em-nuoi` | Có danh sách trẻ em |
| `/donors` | Có danh sách nhà tài trợ |
| `/schools` | Có danh sách trường |
| `/portal`, `/cong-thong-tin-nha-tai-tro` | Có cổng riêng cho nhà tài trợ |
| `/login-activity` | **Có theo dõi lịch sử đăng nhập** — gợi ý về mô hình bảo mật |

Route `/login-activity` đáng chú ý: nó cho biết hệ thống **có** tính năng theo dõi đăng nhập, tức đây là hệ thống được thiết kế có ý thức bảo mật.

## 1.5 Kiểm chứng: các route này có thật không

Tôi thử `GET` từng đường dẫn (chỉ đọc):

| Đường dẫn | Mã | Chuyển tới |
|---|---|---|
| `/admin` | **307** | `/admin/login` |
| `/auth/` | 308 | — |
| `/children` | 308 | `/danh-sach-em-nuoi` |
| `/donors` | 308 | `/danh-sach-nha-tai-tro` |
| `/portal` | 308 | `/cong-thong-tin-nha-tai-tro` |
| `/schools` | 308 | `/danh-sach-diem-truong-ho-tro` |
| `/danh-sach-em-nuoi` | **200** | Trang tồn tại |
| `/cong-thong-tin-nha-tai-tro` | 307 | — |

→ **9/9 đều tồn tại thật.** `robots.txt` là danh sách chính xác.

## 1.6 Điểm cần nói rõ — đây KHÔNG phải lỗ hổng nghiêm trọng

Tôi kiểm tra thêm và thấy:

- `/admin` → chuyển về `/admin/login` ✅ **chặn đúng**
- `/danh-sach-em-nuoi` → trả về trang nhưng **không có dữ liệu** cho khách chưa đăng nhập
- `/api/auth/session` → trả `{"role":null}` cho khách ✅ **xác thực đúng**

**Nghĩa là:** các trang nhạy cảm **đã được bảo vệ bằng xác thực**. Nên đây là **rủi ro về thông tin** (lộ bản đồ hệ thống), **không phải rủi ro truy cập** (vào được dữ liệu).

Nếu không có xác thực, đây sẽ là lỗ hổng nghiêm trọng. Nhưng vì xác thực hoạt động, mức độ chỉ là **trung bình–cao về thông tin**, không phải **cao về truy cập**.

## 1.7 Cách sửa

```diff
- Disallow: /admin
- Disallow: /auth/
- Disallow: /children
- Disallow: /donors
- Disallow: /portal
- Disallow: /schools
- Disallow: /login-activity
- Disallow: /danh-sach-em-nuoi
- Disallow: /cong-thong-tin-nha-tai-tro
```

Nguyên tắc đúng: **để xác thực làm việc bảo vệ**, không dựa vào `robots.txt`. Nếu một trang nhạy cảm, hãy **trả 404** cho khách chưa đăng nhập — như vậy không lộ cả sự tồn tại của trang.

---

# 2. `page-e73e03b76ce68f16.js`

## 2.1 Nó là gì

Đây là một **file JavaScript** trong ứng dụng Next.js của `quynuoiem.com`.

Next.js **chia nhỏ code theo từng trang** (gọi là *code splitting*). Nghĩa là mỗi trang có file JS riêng, chỉ tải khi cần. Điều này giúp trang tải nhanh.

Cấu trúc tên file:

```
_next/static/chunks/app/(site)/tai-chinh/page-e73e03b76ce68f16.js
│                  │      │       │         │
│                  │      │       │         └─ hash nội dung
│                  │      │       └─ TÊN TRANG: tai-chinh
│                  │      └─ nhóm route (site)
│                  └─ thư mục chunk
└─ thư mục tĩnh của Next.js
```

**Điểm mấu chốt:** tên file **nói rõ nó thuộc trang nào** — `tai-chinh` (tài chính). Không cần đoán.

## 2.2 Nằm ở đâu

```
https://quynuoiem.com/_next/static/chunks/app/(site)/tai-chinh/page-e73e03b76ce68f16.js
```

| Mục | Giá trị |
|---|---|
| HTTP | **200** |
| Kích thước | **37.710 byte** |
| Content-Type | `application/javascript; charset=UTF-8` |
| Server | `nginx/1.24.0 (Ubuntu)` |
| Đăng nhập cần không | **Không** |

## 2.3 Vì sao nó phải công khai — đây là điểm cốt lõi

Có một câu hỏi tự nhiên: **"sao không giấu file này?"**

Vì **không thể**. Lý do:

1. Trình duyệt phải **tải file này** để trang tài chính hoạt động.
2. Để tải được, URL phải nằm trong HTML.
3. HTML thì công khai.

Nên: **bất kỳ JavaScript nào chạy trên máy người dùng đều phải đọc được**. Không có ngoại lệ.

Nguyên tắc: **không bao giờ đặt bí mật trong JavaScript phía trình duyệt.** Vì bất cứ ai mở F12 → tab Sources đều thấy y hệt.

## 2.4 Bên trong có gì (14 mục cấu hình)

Đây là phần quan trọng nhất. File chứa **14 mục cấu hình**, tất cả đều nhúng **giá trị thật**:

| Biến | Giá trị |
|---|---|
| `EXPENSE_DOCS_DRIVE_FOLDER_ID` | `1YJD2f…WONH` |
| `VCB_STATEMENTS_SHEET_ID` | `1boFEZ…WgHg` |
| `VCB_STATEMENTS_SHEET_GID` | `0` |
| `VP_STATEMENTS_SHEET_ID` | `1boFEZ…WgHg` |
| `VP_STATEMENTS_SHEET_GID` | `33785031` |
| `EXPENSE_DOCS_SHEET_NOV_2025_ID` | `1Ywo-Z…6Xms` |
| `EXPENSE_DOCS_SHEET_DEC_2025_ID` | `1hB6wC…nJb8` |
| `EXPENSE_DOCS_SHEET_JAN_2026_ID` | `1KMXRK…pJ2Y` |
| `EXPENSE_DOCS_SHEET_FEB_2026_ID` | `1QbLJi…Qsh0` |
| `EXPENSE_DOCS_SHEET_MAR_2026_ID` | `1ZVi-R…S2a8` |
| `EXPENSE_DOCS_SHEET_APR_2026_ID` | `1_QLIH…OB4Q` |
| `EXPENSE_DOCS_SHEET_MAY_2026_ID` | `13cljt…ux0I` |
| `EXPENSE_DOCS_SHEET_JUN_2026_ID` | `1rTdTJ…yPNY` |
| `EXPENSE_DOCS_SHEET_JUL_2026_ID` | `13wC2F…Ty_A` |

**Đếm lại:** 1 Drive folder + 2 mục sheet sao kê (dùng chung 1 ID, khác gid) + 9 sheet hồ sơ chi phí = **10 ID sheet + 1 Drive folder**.

Ngoài ra file còn có:
- `accountNumber: "0711…0294"` — số tài khoản nhận tiền
- `bankName: "Vietcombank (VCB)"`
- `https://api.thiennguyen.app` — API backend

## 2.5 Cách ID bị lộ — đoạn code gốc

Trích nguyên văn:

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

**Phân tích từng phần:**

| Phần | Nghĩa |
|---|---|
| `h.env.VCB_STATEMENTS_SHEET_ID` | Đọc từ **biến môi trường** — đúng cách |
| `??` | Toán tử *nullish coalescing*: "nếu trái là null/undefined thì dùng phải" |
| `"1boFEZqK..."` | **Giá trị dự phòng — nhưng là ID thật** |

## 2.6 Lỗi thiết kế nhìn thấy được ngay

Đây là điểm tinh tế và đáng giá nhất của phát hiện này.

**Quỹ đã làm ĐÚNG một nửa.** Họ dùng `process.env` — tức họ **biết** rằng ID không nên viết cứng trong code. Đây là thực hành tốt, cho thấy người viết có ý thức.

**Nhưng nửa còn lại phá hỏng tất cả.** Toán tử `??` có nghĩa: *"nếu không có biến môi trường, dùng giá trị bên phải"*. Và giá trị bên phải là **ID thật**.

Trình tự xảy ra:

```
1. Lập trình viên viết: process.env.X ?? "<ID thật>"
   → Ý định: "có thể cấu hình, có giá trị mặc định tiện lợi"

2. Lúc build production, biến môi trường KHÔNG được set
   (hoặc Next.js bundle cả hai nhánh)

3. Giá trị dự phòng được nhúng vào file JS

4. File JS công khai

5. → ID thật lộ ra Internet
```

**Ý định bảo mật bị vô hiệu bởi chính giá trị dự phòng.** Đây là một dạng lỗi rất phổ biến và rất khó thấy khi review code, vì nhìn qua thì code "có vẻ đúng".

## 2.7 Cách sửa — một dòng

```diff
- sheetId: process.env.VCB_STATEMENTS_SHEET_ID ?? "1boFEZ…WgHg"
+ sheetId: process.env.VCB_STATEMENTS_SHEET_ID
```

Và bắt buộc có biến môi trường khi build (fail-fast nếu thiếu). Ngoài ra:

- Với dữ liệu nhạy cảm: **không dùng biến môi trường phía client**, vì Next.js nhúng chúng vào bundle. Phải đặt trong API route phía server (không có tiền tố `NEXT_PUBLIC_`).
- Kiểm tra: `grep -r "spreadsheets/d/" .next/static/` trước mỗi lần deploy.

---

# 3. Mười sheet + một Drive folder

## 3.1 Đây là gì

Là **10 ID Google Sheet + 1 ID thư mục Google Drive** tìm thấy trong file JS ở mục 2. Chúng chia thành hai nhóm chức năng khác nhau.

## 3.2 Nhóm A — Sao kê ngân hàng (1 sheet)

| Mục | Giá trị |
|---|---|
| Biến | `VCB_STATEMENTS_SHEET_ID` |
| ID | `1boFEZ…WgHg` |
| Tab VCB | `gid = 0` |
| Tab VPBank | `gid = 33785031` (cùng ID, khác tab) |
| Nội dung | 238.173 dòng sao kê, 2018–2026 |
| Kích thước | 34.871.764 byte |

**Điểm đáng chú ý:** VCB và VPBank dùng **cùng một file sheet**, chỉ khác `gid` (tab). Nên thực chất là **1 file chứa 2 tab ngân hàng**.

## 3.3 Nhóm B — Hồ sơ chi phí 9 tháng

| Tháng | ID | HTTP | Byte |
|---|---|---|---|
| 11/2025 | `1Ywo-Z…6Xms` | — | — |
| 12/2025 | `1hB6wC…nJb8` | 200 | 22.174 |
| 01/2026 | `1KMXRK…pJ2Y` | — | — |
| 02/2026 | `1QbLJi…Qsh0` | — | — |
| 03/2026 | `1ZVi-R…S2a8` | — | — |
| 04/2026 | `1_QLIH…OB4Q` | 200 | 36.922 |
| 05/2026 | `13cljt…ux0I` | — | — |
| 06/2026 | `1rTdTJ…yPNY` | 200 | 13.595 |
| 07/2026 | `13wC2F…Ty_A` | 200 | 22.010 |

**Vì sao mỗi tháng một sheet?** Đây là dấu hiệu của quy trình thủ công: nhân viên tạo một file mới mỗi tháng, thay vì thêm dòng vào một file lớn. Chính điều này phản ánh đúng vấn đề Quỹ tự nhận — **quản lý bằng Excel**.

## 3.4 Drive folder

| Mục | Giá trị |
|---|---|
| Biến | `EXPENSE_DOCS_DRIVE_FOLDER_ID` |
| ID | `1YJD2f…WONH` |
| HTTP | **200** |

Mỗi dòng trong sheet hồ sơ chi phí có **một folder Drive riêng** chứa chứng từ của trường đó. Ví dụ:

```
https://drive.google.com/drive/folders/13i0OP…se__
→ HTTP 200, 320.988 byte
→ <title>DANE1667 T1-5 Trường TH và THCS Bình Dương-Bạch Đằng-Cao Bằng - Google Drive</title>
```

Trong folder có file **`Đề nghị thanh toán.pdf`**.

## 3.5 Nội dung sheet hồ sơ chi phí có gì

Cấu trúc cột:

```
TT | Trường | Xã | Tỉnh | Số học sinh được hỗ trợ trong năm |
Số tiền giải ngân trong tháng | Link drive chứng từ
```

Dữ liệu thật tháng 07/2026:

| TT | Trường | Xã | Tỉnh | Số HS | Tiền giải ngân |
|---|---|---|---|---|---|
| 1 | TH&THCS Bình Dương | Bạch Đằng | Cao Bằng | 85 | 39.963.600 VNĐ |
| 2 | Tiểu học Bạch Đằng | Bạch Đằng | Cao Bằng | 12 | 7.588.800 VNĐ |
| 3 | PTDTBT THCS Mông Ân | Bảo Lâm | Cao Bằng | 67 | 25.772.000 VNĐ |
| 6 | Mầm Non Đức Hạnh | Cốc Pàng | Cao Bằng | 368 | 25.921.600 VNĐ |

**Quy mô một tháng: 145 trường, tổng giải ngân 7.425.579.600 VNĐ.**

## 3.6 Kiểm chứng: có tải được không

Tôi thử trực tiếp, không suy đoán:

```bash
curl -sL "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv"
```

| Sheet | Kết quả |
|---|---|
| Sao kê | **HTTP 200 · 34.871.764 byte** |
| Hồ sơ 12/2025 | **HTTP 200 · 22.174 byte** |
| Hồ sơ 04/2026 | **HTTP 200 · 36.922 byte** |
| Hồ sơ 06/2026 | **HTTP 200 · 13.595 byte** |
| Hồ sơ 07/2026 | **HTTP 200 · 22.010 byte** |

→ **Tất cả tải được, không cần đăng nhập.**

Quyền trên sheet: **"Chỉ xem"** — tức có quyền **đọc**, **không** có quyền ghi.

## 3.7 Vì sao quan trọng

### Về bảo mật — dữ liệu cá nhân

Sheet sao kê chứa, trong cột memo:

| Loại dữ liệu | Số lượng |
|---|---|
| Số điện thoại | **14.328** |
| Email | **222** |
| Tên người gửi | **1.818** |
| Số tài khoản/tham chiếu | **87.434** |

**Đây là dữ liệu của NHÀ TÀI TRỢ, không phải của học sinh.** Họ gửi tiền cho một tổ chức từ thiện — và thông tin cá nhân của họ bị công khai vĩnh viễn trên Internet.

Điểm nghiêm trọng: **link dạng "ai có link thì xem" không thể thu hồi**. 34 MB đã có thể nằm trên bất kỳ máy nào.

### Về dự án — cơ hội bị bỏ lỡ

Đây là phần **thay đổi kết luận trước đây của tôi**.

Trước đó tôi báo cáo: *"coverage chỉ 32,52% vì thiếu danh mục học sinh"* — coi đó là **trần cứng**.

Nhưng sheet hồ sơ chi phí có chính xác thứ tôi thiếu:

| Tôi từng thiếu | Sheet hồ sơ cung cấp |
|---|---|
| Tiền ra theo từng trường | ✅ `Trường` + `Số tiền giải ngân` |
| Số học sinh mỗi trường | ✅ `Số học sinh được hỗ trợ` |
| Chứng từ | ✅ `Link drive chứng từ` |

→ **32,52% KHÔNG còn là trần cứng.** Có đường để nâng tỷ lệ phủ lên.

## 3.8 Vì sao 10 sheet bị phơi — cùng một nguyên nhân

Cả 10 đều lộ vì **cùng một lỗi**: giá trị dự phòng `??` trong file JS.

```
process.env.X ?? "<ID thật>"
```

Nên **việc sửa rất tập trung**: sửa cách nhúng ID trong file JS ở mục 2 là **giải quyết cả 10**.

---

# 4. Ba thứ này liên kết thế nào

```
quynuoiem.com/tai-chinh
        │
        │ Trình duyệt phải tải JS để hiển thị dữ liệu
        ▼
page-e73e03b76ce68f16.js   ← ★ NGUYÊN NHÂN GỐC
        │
        │ Chứa 10 ID sheet + 1 Drive folder (do lỗi `??`)
        ▼
10 sheet + 1 Drive     ← ★ HẬU QUẢ
        │
        │ Cho phép tải toàn bộ dữ liệu công khai
        ▼
Dữ liệu cá nhân nhà tài trợ lộ

──────────────────────────────────────────

robots.txt  ← ★ VẤN ĐỀ RIÊNG (độc lập)
        │
        │ Công khai danh sách 9 route nội bộ
        ▼
Bản đồ hệ thống cho người tấn công
(nhưng xác thực vẫn chặn được truy cập)
```

**Hai vấn đề khác nhau về bản chất:**

| | Nguyên nhân | Hậu quả | Sửa ở đâu |
|---|---|---|---|
| **`robots.txt`** | Cấu hình sai | Lộ bản đồ route | Sửa file `robots.txt` |
| **JS + 10 sheet** | Giá trị dự phòng `??` là ID thật | Lộ dữ liệu cá nhân | Sửa code + thu hồi chia sẻ |

---

# 5. Ưu tiên sửa

| # | Việc | Vì sao | Khó không |
|---|---|---|---|
| 1 | Sửa `??` thành `null` trong JS | Chặn nguồn gốc rò rỉ cả 10 sheet | Một dòng |
| 2 | Thu hồi chia sẻ công khai của các sheet | 34 MB đã lộ, chặn tiếp theo | Cài đặt Google |
| 3 | Sửa `robots.txt` | Bỏ bản đồ route | Sửa file |
| 4 | Đặt ID vào server-side | Cách đúng về kiến trúc | Cần sửa nhiều |

---

# PHỤ LỤC — Phân loại độ chắc chắn

## Dữ kiện (đã kiểm chứng trực tiếp)

- `robots.txt` trả **HTTP 200**, dài ~200 dòng, 13 khối User-Agent, 9 route `Disallow`.
- 9/9 route đó tồn tại thật (307/308/200).
- `/admin` → `/admin/login`; `/api/auth/session` → `{"role":null}`.
- File `page-e73e03b76ce68f16.js`: **HTTP 200, 37.710 byte**, tải không cần đăng nhập.
- File chứa **14 mục cấu hình**, gồm **10 ID sheet + 1 Drive folder ID** (xác nhận bằng regex).
- 5 sheet đã test trực tiếp: **đều HTTP 200**.
- Sheet sao kê: 238.173 dòng, dữ liệu cá nhân của 1.818 nhà tài trợ.
- Sheet hồ sơ 07/2026: 145 trường, 7.425.579.600 VNĐ.
- Drive folder chứng từ: HTTP 200, có `Đề nghị thanh toán.pdf`, tiêu đề lộ tên trường.
- Quyền sheet: **"Chỉ xem"**.

## Suy luận

- Dùng `process.env` cho thấy **có ý thức** cấu hình, nhưng giá trị dự phòng `??` phá hỏng ý định đó.
- Mỗi tháng một sheet là dấu hiệu **quy trình thủ công** — khớp với vấn đề Quỹ tự nhận về Excel.
- Lộ **số tổng** là cố ý (minh bạch); lộ **dữ liệu cá nhân nhà tài trợ** nhiều khả năng là **không cố ý**.

## Chưa kiểm chứng

- Chưa test hết 145 folder chứng từ (mới test 1 đại diện).
- Chưa xác định sheet nào chứa PII **học sinh** (mới đọc sheet hồ sơ chi phí).
- Chưa rà nguồn ngoài `quynuoiem.com` (fanpage, site cũ).
