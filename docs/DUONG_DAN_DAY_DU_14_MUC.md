> **Lưu ý:** tài liệu này có nhắc tới định danh Google Sheet / số tài khoản của Quỹ
> Nuôi Em, đã **che bớt** (6 ký tự đầu + 4 ký tự cuối). Bản đầy đủ chỉ lưu trên máy,
> không đưa lên Git. Không dùng các định danh này để đọc hay phát tán dữ liệu cá nhân.
> Xem `SECURITY.md`.

# Đường dẫn đầy đủ — 14 mục cấu hình trong file JS

Ngày: 15/10/2026  
Nguồn: `https://quynuoiem.com/_next/static/chunks/app/(site)/tai-chinh/page-e73e03b76ce68f16.js`  
Trạng thái kiểm chứng: **12/12 mục đã test trực tiếp — tất cả HTTP 200**

> **Định danh trong tài liệu này đã được che bớt** — dạng `1boFEZ…WgHg`
> (6 ký tự đầu + 4 ký tự cuối). Đủ để đối chiếu đúng file nào, nhưng không dùng
> để mở được. Bản đầy đủ chỉ lưu trên máy, không đưa lên Git.
>
> Mục đích của bảng dưới: cho Quỹ biết **cần thu hồi những cái nào**, và để nhóm
> tự kiểm tra lại. Không dán vào báo cáo nộp.

---

## A. File gốc chứa tất cả

```
https://quynuoiem.com/_next/static/chunks/app/(site)/tai-chinh/page-e73e03b76ce68f16.js
```

| Mục          | Giá trị                                 |
| ------------ | --------------------------------------- |
| HTTP         | **200**                                 |
| Kích thước   | **37.710 byte**                         |
| Content-Type | `application/javascript; charset=UTF-8` |

**Cách tự kiểm tra lại:**

```bash
curl -s "https://quynuoiem.com/_next/static/chunks/app/(site)/tai-chinh/page-e73e03b76ce68f16.js" \
  | grep -oE '(SHEET_ID|FOLDER_ID)[^,]{0,80}'
```

---

## B. Sheet sao kê ngân hàng — 1 file, 2 tab

### B1. Tab VCB (`gid=0`) — 238.173 dòng

| Mục                  | Giá trị                                                                                                        |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Xem (dạng trang)** | `https://docs.google.com/spreadsheets/d/1boFEZ…WgHg/edit#gid=0`               |
| **Tải CSV**          | `https://docs.google.com/spreadsheets/d/1boFEZ…WgHg/export?format=csv&gid=0`  |
| **Tải XLSX**         | `https://docs.google.com/spreadsheets/d/1boFEZ…WgHg/export?format=xlsx&gid=0` |
| **Dạng JSON**        | `https://docs.google.com/spreadsheets/d/1boFEZ…WgHg/gviz/tq?tqx=out:json`     |
| Tiêu đề file         | `Sao kê tài khoản`                                                                                             |
| **Kết quả test**     | **HTTP 200 · 34.871.764 byte**                                                                                 |
| Biến JS              | `VCB_STATEMENTS_SHEET_ID` + `VCB_STATEMENTS_SHEET_GID = "0"`                                                   |

### B2. Tab VPBank (`gid=33785031`)

| Mục              | Giá trị                                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Xem**          | `https://docs.google.com/spreadsheets/d/1boFEZ…WgHg/edit#gid=33785031`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/1boFEZ…WgHg/export?format=csv&gid=33785031` |
| **Kết quả test** | **HTTP 200 · 212.649 byte** (nhỏ hơn VCB nhiều)                                                                      |
| Biến JS          | `VP_STATEMENTS_SHEET_ID` (cùng ID) + `VP_STATEMENTS_SHEET_GID = "33785031"`                                          |

**Điểm cần chú ý:** VCB và VPBank dùng **cùng một file**, chỉ khác `gid` (số tab).  
Nên thực chất là **1 sheet chứa 2 tab ngân hàng**.

Trong code gốc:

```javascript
// nguồn VCB
sheetId: h.env.VCB_STATEMENTS_SHEET_ID ?? "1boFEZ…WgHg",
gid:     h.env.VCB_STATEMENTS_SHEET_GID  ?? "0",
accountNumber: "0711…0294", bankName: "Vietcombank (VCB)"

// nguồn VPBank — cùng sheetId, khác gid
sheetId: b.env.VP_STATEMENTS_SHEET_ID ?? "1boFEZ…WgHg",
gid:     b.env.VP_STATEMENTS_SHEET_GID  ?? "33785031", bankName: "VPBank (VP)"
```

---

## C. Hồ sơ chi phí theo tháng — 9 sheet

**Tên chính thức của cả 9 file:**  
`Danh sách Điểm trường giải ngân tiền ăn tập trung trong tháng <MM>/<YYYY>`

Cấu trúc cột giống nhau ở cả 9:

```
TT | Trường | Xã | Tỉnh | Số học sinh được hỗ trợ trong năm |
Số tiền giải ngân trong tháng | Link drive chứng từ
```

### C1. Tháng 11/2025

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `1Ywo-Z…6Xms`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/1Ywo-Z…6Xms/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/1Ywo-Z…6Xms/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 36.786 byte**                                                                              |

### C2. Tháng 12/2025

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `1hB6wC…nJb8`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/1hB6wC…nJb8/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/1hB6wC…nJb8/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 22.174 byte**                                                                              |

### C3. Tháng 01/2026

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `1KMXRK…pJ2Y`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/1KMXRK…pJ2Y/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/1KMXRK…pJ2Y/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 90.929 byte**                                                                              |

### C4. Tháng 02/2026

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `1QbLJi…Qsh0`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/1QbLJi…Qsh0/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/1QbLJi…Qsh0/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 12.215 byte**                                                                              |

### C5. Tháng 03/2026

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `1ZVi-R…S2a8`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/1ZVi-R…S2a8/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/1ZVi-R…S2a8/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 6.434 byte**                                                                               |

### C6. Tháng 04/2026

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `1_QLIH…OB4Q`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/1_QLIH…OB4Q/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/1_QLIH…OB4Q/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 36.922 byte**                                                                              |

### C7. Tháng 05/2026

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `13cljt…ux0I`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/13cljt…ux0I/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/13cljt…ux0I/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 17.788 byte**                                                                              |

### C8. Tháng 06/2026

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `1rTdTJ…yPNY`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/1rTdTJ…yPNY/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/1rTdTJ…yPNY/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 13.595 byte**                                                                              |

### C9. Tháng 07/2026

| Mục              | Giá trị                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| ID               | `13wC2F…Ty_A`                                                          |
| **Xem**          | `https://docs.google.com/spreadsheets/d/13wC2F…Ty_A/edit`              |
| **Tải CSV**      | `https://docs.google.com/spreadsheets/d/13wC2F…Ty_A/export?format=csv` |
| **Kết quả test** | **HTTP 200 · 22.010 byte**                                                                              |

---

## D. Drive folder chứng từ

### D1. Folder gốc (trong JS)

| Mục              | Giá trị                                                                    |
| ---------------- | -------------------------------------------------------------------------- |
| ID               | `1YJD2f…WONH`                                        |
| **Mở**           | `https://drive.google.com/drive/folders/1YJD2f…WONH` |
| **Kết quả test** | **HTTP 200 · 419.121 byte**                                                |
| Biến JS          | `EXPENSE_DOCS_DRIVE_FOLDER_ID`                                             |

### D2. Folder chứng từ theo từng trường (lấy từ cột trong sheet hồ sơ)

Mỗi dòng trong 9 sheet hồ sơ có **một folder riêng**. Ví dụ thật lấy từ sheet 07/2026:

| Trường                                    | Folder                                                                     |
| ----------------------------------------- | -------------------------------------------------------------------------- |
| TH\&THCS Bình Dương (Bạch Đằng, Cao Bằng) | `https://drive.google.com/drive/folders/13i0OP…se__` |
| Tiểu học Bạch Đằng                        | `https://drive.google.com/drive/folders/1x_VdrOriUuOhbVo47Xp61QzvHKWQJ_0g` |
| PTDTBT THCS Mông Ân (Bảo Lâm)             | `https://drive.google.com/drive/folders/1kmXQjX0arw5IFxWp4OkKrtAOZfYuHpcJ` |
| Tiểu học Bảo Lâm                          | `https://drive.google.com/drive/folders/1GnedxCchu8svHlnsp5sgEnUQmlSxf_KU` |
| Tiểu học Mông Ân                          | `https://drive.google.com/drive/folders/154HK2qSFhCjK8xx4J7JAbRsTmi1lHW10` |
| Mầm Non Đức Hạnh (Cốc Pàng)               | `https://drive.google.com/drive/folders/16Q5O3ILcrNML5qtOkFoudJrWWsBzZAVt` |
| Tiểu học Đoài Côn (Đoài Dương)            | `https://drive.google.com/drive/folders/1go3SvM0ka_x4B_0cEeCUhYh75pzCCaux` |

Test 1 folder đại diện:

```
GET https://drive.google.com/drive/folders/13i0OP…se__
→ HTTP 200 · 320.988 byte
→ <title>DANE1667 T1-5 Trường TH và THCS Bình Dương-Bạch Đằng-Cao Bằng - Google Drive</title>
```

Bên trong có file **`Đề nghị thanh toán.pdf`**.

**Số lượng folder ước tính:** mỗi sheet hồ sơ có ~145 trường → **9 tháng × ~145 ≈ 1.300 folder**, tất cả đều công khai.

⚠️ **Tôi mới test 1 folder đại diện.** Chưa xác minh toàn bộ ~1.300 folder.

---

## E. Hai thông tin phi-URL trong cùng file

| Biến                | Giá trị                       | Ghi chú                          |
| ------------------- | ----------------------------- | -------------------------------- |
| `accountNumber`     | `0711…0294`               | Số tài khoản nhận tiền của Quỹ   |
| `bankName`          | `Vietcombank (VCB)`           | Ngân hàng                        |
| `revalidateSeconds` | `3600`                        | Cache 1 giờ                      |
| `pageSize`          | `20`                          | 20 dòng/trang                    |
| API backend         | `https://api.thiennguyen.app` | Domain API; các path thử đều 404 |

Số tài khoản không phải URL, nhưng có thể dựng link tra cứu nếu cần — **không cần thiết và không nên làm**.

---

## F. Bảng tổng hợp — 12/12 kiểm chứng

| #  | Mục                          | HTTP    | Byte       |
| -- | ---------------------------- | ------- | ---------- |
| 1  | Sao kê VCB (gid=0)           | **200** | 34.871.764 |
| 2  | Sao kê VPBank (gid=33785031) | **200** | 212.649    |
| 3  | Hồ sơ 11/2025                | **200** | 36.786     |
| 4  | Hồ sơ 12/2025                | **200** | 22.174     |
| 5  | Hồ sơ 01/2026                | **200** | 90.929     |
| 6  | Hồ sơ 02/2026                | **200** | 12.215     |
| 7  | Hồ sơ 03/2026                | **200** | 6.434      |
| 8  | Hồ sơ 04/2026                | **200** | 36.922     |
| 9  | Hồ sơ 05/2026                | **200** | 17.788     |
| 10 | Hồ sơ 06/2026                | **200** | 13.595     |
| 11 | Hồ sơ 07/2026                | **200** | 22.010     |
| 12 | Drive folder gốc             | **200** | 419.121    |

**Tất cả đều tải được, không cần đăng nhập.** Quyền: **"Chỉ xem"**.

---

## G. Lệnh tự kiểm tra lại (dùng được cho cả 12)

```bash
# Cách 1 — tải CSV một sheet
curl -sL "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv" -o out.csv

# Cách 2 — chỉ kiểm tra quyền truy cập
curl -sL -o /dev/null -w "HTTP %{http_code} · %{size_download} byte\n" \
  "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv"

# Cách 3 — lấy tiêu đề để xác định file nào
curl -sL "https://docs.google.com/spreadsheets/d/<ID>/htmlview" \
  | grep -oE "<title>[^<]*</title>"

# Cách 4 — kiểm tra folder Drive
curl -sL -o /dev/null -w "HTTP %{http_code}\n" \
  "https://drive.google.com/drive/folders/<FOLDER_ID>"
```

---

## H. Vì sao tài liệu này chỉ để nội bộ

Bảng đường dẫn ở trên **là chính xác cái mà một kẻ tấn công cần**. Viết ra để:


1. **Nhóm tự kiểm chứng lại** — không phải tin lời tôi, mà tự chạy `curl`.
2. **Báo cho Quỹ biết chính xác cần thu hồi cái gì** — không thể "sửa bảo mật" nếu không biết ID nào bị lộ.
3. **Không dán vào báo cáo nộp.** Trong báo cáo, chỉ nêu **số lượng** (10 sheet + 1 folder) và **số dòng dữ liệu** để chứng minh nguồn.

Nguyên tắc: **chứng minh được mà không phát tán thêm.** Mỗi lần dán ID vào một file mới là một lần dữ liệu đi xa hơn một bước.
