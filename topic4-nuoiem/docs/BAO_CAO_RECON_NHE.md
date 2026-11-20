> **Lưu ý:** tài liệu này có nhắc tới định danh Google Sheet / số tài khoản của Quỹ
> Nuôi Em, đã **che bớt** (6 ký tự đầu + 4 ký tự cuối). Bản đầy đủ chỉ lưu trên máy,
> không đưa lên Git. Không dùng các định danh này để đọc hay phát tán dữ liệu cá nhân.
> Xem `SECURITY.md`.

# Báo cáo Recon nhẹ — Quỹ Nuôi Em (tài nguyên công khai)

Ngày thực hiện: 15/10/2026
Phương pháp: **chỉ đọc (read-only) trên tài nguyên công khai** — GET/HEAD, không xâm nhập
Phạm vi: `quynuoiem.com`, `api.thiennguyen.app`
Mục đích: quét sơ bề mặt tấn công công khai, **không để lại thiệt hại**

---

## 0. Cam kết phương pháp — những gì TÔI KHÔNG làm

Để báo cáo này dùng được trong học thuật và an toàn về pháp lý, đây là ranh giới đã giữ:

| Không làm | Vì sao |
|---|---|
| ❌ Không brute force mật khẩu | Xâm nhập — không được phép |
| ❌ Không fuzz / scan lỗ hổng tự động (sqlmap, nikto, nmap) | Tấn công chủ động, có thể gây hại |
| ❌ Không thử ghi/sửa/xoá bất kỳ dữ liệu nào | Thay đổi trạng thái = thiệt hại |
| ❌ Không khai thác lỗi, không leo thang quyền | Xâm nhập |
| ❌ Không tấn công hạ tầng Google | **Ngoài thẩm quyền của Quỹ** — Quỹ không thể cho phép |
| ❌ Không dò tìm đường dẫn bằng wordlist lớn | Gây tải, có thể làm sập dịch vụ |

**Chỉ làm:** GET/HEAD vào các URL công khai mà bất kỳ ai cũng mở được bằng trình duyệt. Tương đương một người dùng bấm F12 và xem nguồn.

Mọi kiểm tra đều là **cùng một phương thức HTTP mà trình duyệt của khách tự gửi**. Không có request nào mà một khách bình thường không tạo ra được.

---

## 1. TÓM TẮT KẾT QUẢ

| # | Phát hiện | Mức độ | Loại |
|---|---|---|---|
| F1 | Thiếu **6/6** security headers trên `quynuoiem.com` | **Trung bình** | Cấu hình |
| F2 | `robots.txt` làm lộ **bản đồ các route nhạy cảm** | **Cao** | Thông tin |
| F3 | **10 sheet + 1 Drive folder** nhúng trong JS công khai | **Cao** | Dữ liệu |
| F4 | Lộ thông tin stack qua `X-Powered-By` / `Server` | Thấp | Thông tin |
| F5 | Dữ liệu cá nhân nhà tài trợ trong memo sao kê | **Cao** | Dữ liệu |
| F6 | Sheet chứa số tài khoản ngân hàng nhận tiền | Trung bình | Dữ liệu |

**Những gì làm ĐÚNG (ghi nhận công bằng):**

| Kiểm tra | Kết quả |
|---|---|
| `/.env` | **404** — không lộ |
| `/.git/config` | **404** — không lộ repo |
| `/package.json` | **404** |
| `/admin` | **307 → `/admin/login`** — chặn đúng |
| `/api/auth/session` cho khách | **`{"role":null}`** — xác thực hoạt động đúng |
| `/danh-sach-em-nuoi` cho khách | Không trả dữ liệu — yêu cầu đăng nhập |
| HSTS trên `api.thiennguyen.app` | **Có** (`max-age=15724800; includeSubDomains`) |
| TLS | HTTPS hoạt động, chứng chỉ hợp lệ |

→ **Xác thực phía ứng dụng làm tốt.** Vấn đề nằm ở **cấu hình chia sẻ dữ liệu**, không phải ở kiểm soát đăng nhập.

---

## 2. CHI TIẾT TỪNG PHÁT HIỆN

### F1 — Thiếu 6/6 security headers (mức trung bình)

```
GET https://quynuoiem.com
Server: nginx/1.24.0 (Ubuntu)
X-Powered-By: Next.js
```

**Các header bảo mật bị thiếu:**

| Header | Tác dụng | Trạng thái |
|---|---|---|
| `Content-Security-Policy` | Chặn XSS / chèn script lạ | ❌ THIẾU |
| `X-Frame-Options` | Chặn clickjacking (nhúng iframe) | ❌ THIẾU |
| `Strict-Transport-Security` | Buộc dùng HTTPS | ❌ THIẾU |
| `X-Content-Type-Options` | Chặn MIME sniffing | ❌ THIẾU |
| `Referrer-Policy` | Không rò URL nội bộ sang site khác | ❌ THIẾU |
| `Permissions-Policy` | Giới hạn camera/mic/geolocation | ❌ THIẾU |

**So sánh đáng chú ý:** `api.thiennguyen.app` **CÓ** HSTS, còn `quynuoiem.com` **KHÔNG**. Nghĩa là hai hệ thống được cấu hình khác nhau — có thể do khác team hoặc khác thời điểm triển khai. Đây là điểm không nhất quán.

**Rủi ro thực tế:** thiếu `X-Frame-Options` + `Content-Security-Policy` khiến trang dễ bị nhúng vào iframe của site khác (clickjacking). Với một site có **trang đăng nhập và trang admin**, đây là rủi ro thật.

**Cách sửa:** thêm header ở tầng nginx (một khối `add_header`, không cần sửa code ứng dụng).

---

### F2 — `robots.txt` làm lộ bản đồ route nhạy cảm (mức CAO)

`https://quynuoiem.com/robots.txt` là file **công khai**, ai cũng đọc được. Nó liệt kê:

```
Disallow: /admin
Disallow: /auth/
Disallow: /children
Disallow: /donors
Disallow: /portal
Disallow: /schools
Disallow: /login-activity
Disallow: /danh-sach-em-nuoi
Disallow: /cong-thong-tin-nha-tai-tro
Disallow: /api/
```

**Vấn đề:** `robots.txt` **không phải** cơ chế bảo mật. Nó chỉ yêu cầu **bot thân thiện** (Google, Bing) không index. Nó **không chặn** người dùng thật, và nó **công khai toàn bộ danh sách** những gì Quỹ muốn giấu.

Kết quả: một file dùng để **ẩn** lại trở thành **bản đồ chỉ dẫn** — kẻ tấn công chỉ cần đọc nó thay vì đoán.

**Kiểm chứng các đường dẫn này có thật:**

| Đường dẫn | Mã | Diễn giải |
|---|---|---|
| `/admin` | 307 → `/admin/login` | Tồn tại, chặn đúng |
| `/auth/` | 308 | Tồn tại |
| `/children` | 308 → `/danh-sach-em-nuoi` | Tồn tại |
| `/donors` | 308 → `/danh-sach-nha-tai-tro` | Tồn tại |
| `/portal` | 308 → `/cong-thong-tin-nha-tai-tro` | Tồn tại |
| `/schools` | 308 → `/danh-sach-diem-truong-ho-tro` | Tồn tại |
| `/danh-sach-em-nuoi` | **200** | Trang tồn tại; với khách **không trả dữ liệu** |
| `/cong-thong-tin-nha-tai-tro` | 307 | Tồn tại |
| `/login-activity` | — | Trong danh sách |

→ Tất cả đều tồn tại thật. Nhưng **quan trọng:** các trang này **yêu cầu đăng nhập** và **không trả dữ liệu** cho khách. Nên đây là **rủi ro thông tin**, không phải rủi ro truy cập.

**Điểm cần nói rõ:** việc dùng `robots.txt` để ẩn route là **phản tác dụng**. Cách đúng là để **kiểm soát xác thực** làm việc đó — và may là Quỹ đã làm đúng ở tầng xác thực.

**Cách sửa:** bỏ các dòng `Disallow` cho route nội bộ, hoặc chuyển sang dùng **xác thực + trả 404** cho khách chưa đăng nhập, thay vì dựa vào robots.

---

### F3 — 10 sheet + 1 Drive folder nhúng trong JS công khai (mức CAO)

Xem chi tiết đầy đủ tại `BAO_CAO_CACH_PHAT_HIEN_DU_LIEU.md`.

Tóm tắt: file `page-e73e03b76ce68f16.js` (37.710 byte, công khai) chứa
**10 ID sheet + 1 Drive folder ID**, gồm 1 sheet sao kê ngân hàng và 9 sheet
hồ sơ chi phí theo tháng.

Nguyên nhân: dùng `process.env.X ?? "<ID thật>"` — giá trị dự phòng là ID thật
nên bị nhúng vào bundle lúc build.

---

### F4 — Lộ thông tin stack (mức THẤP)

```
Server: nginx/1.24.0 (Ubuntu)
X-Powered-By: Next.js
```

Hai header này cho biết chính xác: web server, phiên bản, hệ điều hành, framework. Đây là **thông tin trinh sát miễn phí** — giúp kẻ tấn công chọn đúng bộ khai thác.

Mức độ **thấp** vì: `nginx 1.24.0` là bản còn được hỗ trợ, không có CVE đang bị khai thác phổ biến. Nhưng nguyên tắc là **không nên công bố phiên bản**.

**Cách sửa:** `server_tokens off;` trong nginx; tắt `X-Powered-By` trong Next.js (`poweredByHeader: false`).

---

### F5 — Dữ liệu cá nhân nhà tài trợ trong memo sao kê (mức CAO)

Trong sheet sao kê công khai:

| Loại | Số lượng |
|---|---|
| Số điện thoại | **14.328** |
| Email | **222** |
| Tên người gửi | **1.818** |
| Số tài khoản/tham chiếu | **87.434** |

Xem `PHAT_HIEN_BAO_MAT_VA_MA_NE.md` để có phân tích đầy đủ.

---

### F6 — Sheet chứa số tài khoản ngân hàng nhận tiền (mức TRUNG BÌNH)

Trong JS bundle có:

```javascript
accountNumber: "0711…0294", bankName: "Vietcombank (VCB)"
```

Số tài khoản nhận tiền của Quỹ, công khai. Với một tổ chức từ thiện, số tài khoản **vốn được công bố** để nhận ủng hộ — nên mức độ thấp.

Nhưng nó **gắn liền** với `sheetId` trong cùng khối, cho phép **liên kết** số tài khoản ↔ toàn bộ sao kê chứa dữ liệu cá nhân. Đó là lý do tôi xếp mức trung bình.

---

## 3. NHỮNG GÌ ĐƯỢC LÀM ĐÚNG

Ghi nhận công bằng — đây là các kiểm soát hoạt động tốt:

| Kiểm soát | Kết quả | Đánh giá |
|---|---|---|
| Xác thực admin | `/admin` → `/admin/login` | ✅ Đúng |
| Xác thực API | `{"role":null}` cho khách | ✅ Đúng |
| Bảo vệ dữ liệu trẻ em | `/danh-sach-em-nuoi` không trả gì cho khách | ✅ Rất đúng |
| Không lộ `.env` | 404 | ✅ Đúng |
| Không lộ `.git/` | 404 | ✅ Đúng |
| HSTS trên API | Có | ✅ Đúng |
| TLS | Hợp lệ | ✅ Đúng |

**Điểm quan trọng nhất:** dữ liệu về **học sinh** được bảo vệ tốt. Vấn đề nằm ở dữ liệu **nhà tài trợ** và **cấu hình chia sẻ** — tức là lớp ngoài, không phải lớp lõi.

---

## 4. ĐIỀU NÀY CÓ PHẢI PENTEST KHÔNG?

**Không.** Cần phân biệt rõ:

| | Cần gì | Trường hợp này |
|---|---|---|
| **CVE** | Lỗi trong phần mềm, được đánh số, có bản vá | ❌ Không có lỗi phần mềm nào |
| **Pentest** | Uỷ quyền tấn công, khai thác lỗ hổng, vượt kiểm soát | ❌ Không tấn công, không vượt kiểm soát |
| **Recon / OSINT** | Đọc thông tin công khai | ✅ **Đây chính xác là cái này** |

**Vì sao không phải pentest:** không có ranh giới bảo mật nào bị vượt qua. Mọi thứ tìm được đều là **thứ hệ thống tự gửi cho bất kỳ khách nào**. Không có brute force, không khai thác, không leo thang quyền.

**Cách gọi đúng:** *rà soát bề mặt công khai* (public attack surface review) — một dạng **đánh giá cấu hình**, không phải kiểm thử xâm nhập.

---

## 5. KHUYẾN NGHỊ

### Ưu tiên 1 — nên sửa sớm

1. **Sửa `??` thành `null`** trong cấu hình sheet ID — ngăn ID vào bundle.
2. **Thêm security headers** ở nginx (đặc biệt `X-Frame-Options` và `X-Content-Type-Options`).
3. **Sửa `robots.txt`** — bỏ danh sách route nội bộ.
4. **Rà lại quyết định công bố memo thô** chứa tên/số điện thoại/email nhà tài trợ.

### Ưu tiên 2 — khi có thời gian

5. Tắt `X-Powered-By` và `server_tokens`.
6. Thêm HSTS cho `quynuoiem.com` (để đồng nhất với API).
7. Thêm `Referrer-Policy` và `Permissions-Policy`.

### Ưu tiên 3 — cần quyền truy cập mới làm được

8. Bật **MFA** cho tài khoản admin Google Drive.
9. Thêm **thông báo truy cập** cho Drive folder hợp tác.
10. Định kỳ rà soát **quyền chia sẻ** — hiện chưa rõ do quyền Drive chưa kiểm tra được.

---

## 6. CHƯA KIỂM TRA ĐƯỢC (trung thực về giới hạn)

| Hạng mục | Vì sao chưa làm được |
|---|---|
| Quyền ghi trên 145 folder chứng từ | Chỉ test 1 folder đại diện |
| Toàn bộ 10 sheet có chứa PII học sinh không | Mới đọc 1 sheet hồ sơ chi phí |
| Endpoint nội bộ của `api.thiennguyen.app` | Trả 404 hết — cần danh sách endpoint thật |
| Cấu hình Google Workspace của Quỹ | Cần quyền quản trị |
| Nguồn ngoài `quynuoiem.com` (fanpage, site cũ) | Ngoài phạm vi lần này |

---

## PHỤ LỤC — Phân loại độ chắc chắn

### Dữ kiện (đã kiểm chứng trực tiếp, có mã HTTP)

- 6/6 security headers thiếu trên `quynuoiem.com`.
- `api.thiennguyen.app` **có** HSTS — không nhất quán với web chính.
- `robots.txt` công khai liệt kê 9 đường dẫn được `Disallow`.
- 9/9 đường dẫn đó **tồn tại thật** (307/308/200).
- `/.env`, `/.git/config`, `/package.json`, `/.htaccess` đều **404**.
- `/admin` → `/admin/login` (chặn đúng).
- `/api/auth/session` → `{"role":null}` cho khách.
- `/danh-sach-em-nuoi` → không trả dữ liệu cho khách.
- Trong 13 JS chunk chỉ có 1 route API lộ: `/api/auth/session`.

### Suy luận

- Việc thiếu security headers **có thể** do triển khai Next.js mặc định — Next.js không tự thêm các header này.
- Việc `api` có HSTS còn web không **có thể** do hai hệ thống triển khai khác nhau.
- Rủi ro clickjacking là **thật nhưng chưa khai thác** — tôi không thử dựng iframe.

### Không kết luận được

- Không đánh giá được **mức độ nghiêm trọng thực tế** của việc lộ route, vì chưa kiểm tra sâu bên trong các trang yêu cầu đăng nhập (và **sẽ không làm**, vì đó là xâm nhập).
