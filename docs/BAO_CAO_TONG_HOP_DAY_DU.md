> **Lưu ý:** tài liệu này có nhắc tới định danh Google Sheet / số tài khoản của Quỹ
> Nuôi Em, đã **che bớt** (6 ký tự đầu + 4 ký tự cuối). Bản đầy đủ chỉ lưu trên máy,
> không đưa lên Git. Không dùng các định danh này để đọc hay phát tán dữ liệu cá nhân.
> Xem `SECURITY.md`.

# BÁO CÁO DỰ ÁN — TOPIC 4: MINH BẠCH TÀI CHÍNH QUỸ NUÔI EM

**Môn:** Swinburne University — Project A/B  
**Ngày lập:** 15/10/2026  
**Phạm vi báo cáo:** Topic 4 (Topic 2 để sau)  
**Trạng thái:** MVP chạy được trên **dữ liệu sản xuất thật** — 238.173 dòng sao kê

---

## MỤC LỤC

1. [Website có gì](#1-website-có-gì)
2. [File mẫu anh mentor cung cấp](#2-file-mẫu-anh-mentor-cung-cấp)
3. [Đề bài là gì](#3-đề-bài-là-gì)
4. [Hướng giải quyết](#4-hướng-giải-quyết)
5. [Đã làm như thế nào](#5-đã-làm-như-thế-nào)
6. [Kết quả ra sao](#6-kết-quả-ra-sao)
7. [Phát hiện bảo mật ngoài phạm vi bài làm](#7-phát-hiện-bảo-mật-ngoài-phạm-vi-bài-làm)
8. [Quyết định bảo mật trong hệ thống](#8-quyết-định-bảo-mật-trong-hệ-thống)
9. [Hướng vận hành](#9-hướng-vận-hành)
10. [Chưa có gì / giới hạn](#10-chưa-có-gì--giới-hạn)
11. [Phụ lục: dữ kiện / suy luận / câu hỏi](#11-phụ-lục-dữ-kiện--suy-luận--câu-hỏi)

---

# 1. WEBSITE CÓ GÌ

## 1.1 Cách chạy

```powershell
cd "C:\Users\Tuna\WorkBuddy AI\2026-10-15-13-47-28\topic4-nuoiem"
.\run.ps1
```

Script tự tìm Python, tự mở trình duyệt tại **<http://127.0.0.1:8765>**

**Đặc điểm kỹ thuật:**

| Mục              | Giá trị                                                   |
| ---------------- | --------------------------------------------------------- |
| Ngôn ngữ backend | Python 3.13, **không framework**, chỉ `http.server` chuẩn |
| Frontend         | HTML + CSS + JS thuần (ES2020), **không build step**      |
| Tổng dòng code   | **4.608 dòng**                                            |
| Cơ sở dữ liệu    | SQLite **chỉ đọc** (`mode=ro`, `PRAGMA query_only`)       |
| Kiểm thử         | **77 bài, OK**                                            |
| Phụ thuộc ngoài  | **0** — không pip install gì                              |

**Vì sao chọn "không framework"?** Đề bài yêu cầu một hệ thống Quỹ **thật sự chạy được**. Một hệ thống 0 phụ thuộc có nghĩa: không cần cài đặt, không lo phiên bản, chạy được trên máy bất kỳ. Nhóm tình nguyện viên của Quỹ có thể tự chạy.

## 1.2 Cấu trúc file

```
topic4-nuoiem/
├── run.ps1                    # script khởi động
├── app.py                 621 # HTTP server + 9 API route
├── parsers.py             543 # ★ bộ phân tích mã ACN/NE
├── reconciliation.py      359 # đối soát + nhật ký kiểm toán
├── schema.py              306 # định nghĩa 15 bảng
├── build_database.py      707 # nạp dữ liệu từ CSV
├── verify_real_data.py    210 # kiểm chứng với số công bố của Quỹ
├── static/
│   ├── index.html         194 # giao diện
│   ├── app.js             469 # logic hiển thị
│   ├── styles.css         394 # mobile-first
│   └── assets/                # logo + ảnh hero
├── tests/test_app.py      805 # 77 bài kiểm thử
└── docs/                       # 7 tài liệu
```

## 1.3 Giao diện có gì — 10 khối

Giao diện đọc theo **một mạch duy nhất**, từ trên xuống:

### ① Banner trung thực (đầu trang)

Nói thẳng phạm vi ngay từ đầu:

> *"Dữ liệu từ một nguồn ngân hàng duy nhất, giai đoạn 2018–2026. Các khoản chưa gắn mã được hiển thị công khai, không che."*

**Vì sao có khối này:** người xem cần biết mình đang xem gì **trước khi** đọc số, không phải sau.

### ② Hero

Tiêu đề + thời điểm cập nhật dữ liệu.

### ③ Bốn ô KPI

| Ô            | Nội dung            | Giá trị thật                         |
| ------------ | ------------------- | ------------------------------------ |
| Tiền vào     | Số dòng + tổng tiền | **236.030 dòng / 553.550.809.401 đ** |
| Tiền ra      | Số dòng + tổng tiền | **2.143 dòng / 553.541.302.920 đ**   |
| Mã NE        | Số mã phân biệt     | **31.051 mã**                        |
| Cần soát lại | Số dòng chưa gắn mã | **125.713 dòng**                     |

### ④ Thẻ bất biến đối soát

Đây là **kiểm soát quan trọng nhất** trên màn hình. Nó chứng minh:

```
Tổng các dòng phân bổ  =  Tổng giao dịch đã liên kết
      180.389.417.047 đ  =  180.389.417.047 đ     ✅ KHỚP
```

Nếu hai vế lệch nhau, nghĩa là tiền bị ghi trùng hoặc thất lạc. **Hiện khớp tuyệt đối.**

### ⑤ Thanh tỷ lệ phủ

```
32,52% tiền vào đã gắn được ít nhất một mã NE
```

**Đây là quyết định thiết kế có chủ ý:** tỷ lệ thấp nhưng được **hiển thị to, không giấu**. Lý do nằm ở quy định của Quỹ — các khoản không gắn được mã **không hoàn lại** và chuyển vào quỹ vô danh. Nên người xem **phải thấy** con số này.

### ⑥ Ô tìm kiếm theo mã

Nhập `NE00001` hoặc `ACN02497` → tra cứu ngược ra giao dịch.

### ⑦ Bộ lọc

Theo chiều tiền (vào/ra), theo trạng thái (đã gắn/chưa gắn mã).

### ⑧ Ngăn kéo truy vết (lineage drawer)

Bấm một giao dịch → mở ra xem:

- Các mã NE được tách ra từ memo này
- Mỗi mã nhận bao nhiêu tiền
- **Chính sách phân bổ** đã dùng

Đây là phần trả lời câu hỏi khó nhất của minh bạch: *"con số này ở đâu ra?"*

### ⑨ Hàng đợi ngoại lệ

Hiển thị **1 dòng** hành động được (gộp từ 125.713 vấn đề).

### ⑩ Nhật ký kiểm toán

Bảng append-only, mỗi dòng chứa hash của dòng trước. Phát hiện được sửa đổi.

## 1.4 Chín API route

| Route                    | Chức năng                         |
| ------------------------ | --------------------------------- |
| `/api/health`            | Kiểm tra sống                     |
| `/api/summary`           | Số liệu tổng (KPI)                |
| `/api/transactions`      | Danh sách giao dịch có phân trang |
| `/api/transactions/<id>` | Chi tiết + truy vết               |
| `/api/allocation`        | Phân bổ theo mã                   |
| `/api/ne`                | Tra cứu mã NE                     |
| `/api/exceptions`        | Hàng đợi ngoại lệ                 |
| `/api/approvals`         | Hàng đợi phê duyệt                |
| `/api/metadata`          | Nguồn dữ liệu + phạm vi           |

**Chỉ có `GET`.** Mọi `POST`/`PUT`/`PATCH`/`DELETE` trả **405** — đã có test.

---

# 2. FILE MẪU ANH MENTOR CUNG CẤP

## 2.1 Nó là gì

`mock data.xlsx` — file Excel mẫu.

## 2.2 Bên trong có gì

| Thực thể          | Số lượng |
| ----------------- | -------- |
| Học sinh          | **10**   |
| Nhà tài trợ (ACN) | **14**   |
| Trường            | **1**    |
| Giao dịch thô     | **9**    |

## 2.3 Giá trị THẬT của file này

File mẫu **không đủ để chạy** — nhưng nó có **hai giá trị thật** mà tôi phải ghi nhận:

### Giá trị 1 — Chứng minh chuỗi quan hệ có thật

```
ACN (mã nhà tài trợ)  →  NE (mã em nuôi)  →  học sinh  →  trường
```

Mô hình dữ liệu của tôi dựa hoàn toàn vào chuỗi này. File mẫu chứng minh nó tồn tại trong thực tế, không phải tôi tự nghĩ ra.

### Giá trị 2 — Cho thấy quy ước hậu tố S/T

Đây là phát hiện tôi suýt bỏ sót:

```
NE00001S  = bữa trưa (Sáng)
NE00001T  = bữa tối (Tối)
```

**Hai mã khác nhau, hai nhà tài trợ khác nhau, một học sinh nội trú ăn hai bữa.**

Nếu gộp `S` và `T` lại, tôi sẽ **đếm sai số nhà tài trợ** và **gộp hai người khác nhau thành một**. Đây là lý do `parsers.py` giữ hậu tố như **một phần của mã**, không tách ra.

## 2.4 File mẫu KHÔNG có gì — và đây là lý do phải tìm dữ liệu thật

| Thiếu                           | Hệ quả                               |
| ------------------------------- | ------------------------------------ |
| Đề nghị thanh toán của trường   | Không dựng được luồng tiền ra        |
| Tiền ra liên kết chứng từ       | Không chứng minh được giải ngân      |
| Chứng từ + trạng thái phê duyệt | Không có luồng maker-checker         |
| **ACN trùng giữa hai khối**     | **Không chứng minh được end-to-end** |

**Điểm thứ 4 là điểm chí mạng.** Không có một ACN nào xuất hiện ở **cả** khối giao dịch **và** khối học sinh. Nghĩa là file mẫu **tự nó không chứng minh được** chuỗi quan hệ hoàn chỉnh — nó chỉ có hai nửa rời nhau.

## 2.5 Kết luận về file mẫu

> File mẫu là **bản thiết kế**, không phải **dữ liệu chạy**.  
> Nó cho biết *hình dạng đúng* của dữ liệu; nó không cho biết *dữ liệu có đúng không*.

Nên tôi quyết định: **giữ mô hình dữ liệu học từ file mẫu, nhưng chạy trên dữ liệu thật.**

---

# 3. ĐỀ BÀI LÀ GÌ

## 3.1 Bối cảnh — đây không phải bài tập lý thuyết

**Ngày 05/06/2026, Quỹ Nuôi Em công bố kết quả làm việc với cơ quan chức năng.**

Diễn biến:

| Thời gian  | Sự kiện                                    |
| ---------- | ------------------------------------------ |
| 17/12/2025 | Cơ quan chức năng bắt đầu làm việc với Quỹ |
| 24/04/2026 | Kết thúc quá trình làm việc                |
| 05/06/2026 | Quỹ công bố kết quả                        |

**Kết luận của cơ quan chức năng:**

- ✅ **Không có vi phạm hình sự**
- ✅ **Không có thất thoát tiền**

**Nhưng Quỹ tự nhận ba vấn đề:**

1. **Chạy dự án lớn qua tài khoản ngân hàng cá nhân** → dòng tiền lẫn lộn giữa tiền dự án và tiền cá nhân
2. **Quản lý bằng Excel** → không có ràng buộc dữ liệu
3. **Hệ quả: sai mã, trùng mã, lỗi dữ liệu** → không truy vết được

## 3.2 Vì sao bối cảnh này quan trọng với bài làm

Điểm 3 chính là **định nghĩa của topic 4**. Nghĩa là:

> Topic 4 **không phải** "vẽ một dashboard cho đẹp".  
> Topic 4 là **trả lời một thất bại quản trị đã được ghi nhận**.

Cụ thể, ba lỗi Quỹ nhận có tương ứng kỹ thuật rõ ràng:

| Lỗi Quỹ nhận                     | Giải pháp kỹ thuật trong bài                     |
| -------------------------------- | ------------------------------------------------ |
| Tài khoản cá nhân, dòng tiền lẫn | Đối soát bất biến: tổng phân bổ = tổng giao dịch |
| Quản lý bằng Excel               | Cơ sở dữ liệu có ràng buộc + nhật ký kiểm toán   |
| Sai/trùng mã, không truy vết     | `parsers.py` + bảng phân bổ + truy vết ngược     |

## 3.3 Yêu cầu của đề bài

Theo đề bài (Notion link):

| Yêu cầu                     | Cách đáp ứng                        |
| --------------------------- | ----------------------------------- |
| **Mobile-first** (bắt buộc) | 1 cột ở 360px, thêm cột ở 560/860px |
| Dữ liệu Excel-compatible    | Đọc CSV trực tiếp                   |
| Hệ thống chạy được thật     | 0 phụ thuộc, chạy bằng 1 script     |
| Minh bạch tiền vào–ra       | 4 KPI + thẻ bất biến                |
| Truy vết mã → người         | Tra cứu NE/ACN + ngăn kéo truy vết  |

**Về mobile-first:** đề bài nêu rõ hành trình người dùng **đi từ fanpage/Facebook sang website**. Nghĩa là đa số truy cập bằng **điện thoại**, sau khi bấm link trong bài đăng Facebook. Nên mobile-first không phải yêu cầu hình thức — nó phản ánh **cách người thật dùng hệ thống**.

---

# 4. HƯỚNG GIẢI QUYẾT

## 4.1 Quyết định lớn nhất: bỏ file mẫu, dùng dữ liệu thật

Đây là bước ngoặt.

**Vấn đề với file mẫu:** nó không có số tổng do Quỹ công bố. Nghĩa là tôi **không có cách nào biết tính toán của mình đúng hay sai** — tôi chỉ có thể so với chính mình.

**Giải pháp:** tìm dữ liệu thật của Quỹ. Sau đó mọi con số **kiểm chứng được với một con số bên ngoài**.

**Cách tìm** (chi tiết ở `BAO_CAO_CACH_PHAT_HIEN_DU_LIEU.md`):

Báo cáo tài chính của Quỹ **không phải API** — nó là **Google Sheet nhúng**. ID sheet nằm trong file JavaScript của trang `/tai-chinh`.

→ Lấy được: **238.173 dòng sao kê Vietcombank thật, 2018–2026**, do chính Quỹ công bố.

## 4.2 Ba trụ thiết kế

### Trụ 1 — Nguồn sự thật là sao kê ngân hàng

Không lấy Excel làm nguồn. Sao kê ngân hàng là **dữ liệu do ngân hàng sinh ra**, không ai sửa được. Đây là điểm tựa pháp lý.

### Trụ 2 — Tiền lưu MỘT lần

Một giao dịch ngân hàng có thể chứa **tới 20 mã NE**. Nếu lưu tiền vào từng mã, số tiền bị nhân bản.

**Giải pháp:** tiền lưu **một lần** trên giao dịch; bảng `transaction_allocations` giữ **phần chia**.

```
bank_transactions          transaction_allocations
─────────────────          ───────────────────────
id: 123                    tx_id: 123, ne: NE05517, 20.000.000
amount: 80.000.000    ──▶  tx_id: 123, ne: NE05518, 20.000.000
                           tx_id: 123, ne: NE05519, 20.000.000
                           tx_id: 123, ne: NE05520, 20.000.000
                           ─────────────────────────────────────
                           Tổng phân bổ = 80.000.000 ✅ khớp
```


### Trụ 3 — Bất biến đối soát

Định kỳ kiểm tra: **tổng các dòng phân bổ phải bằng đúng tổng giao dịch đã liên kết**. Lệch một đồng là báo lỗi.

Đây là kiểm soát chống lại chính lỗi Quỹ đã mắc — tiền ghi trùng hoặc thất lạc.

## 4.3 Nguyên tắc đối phó thực tế

**Không thử làm sạch dữ liệu hoàn hảo.** Dữ liệu ngân hàng 8 năm không bao giờ sạch. Thay vào đó:

| Thay vì | Làm |
|---|---|
| Cố gắn mã cho mọi giao dịch | Gắn được thì gắn, không được thì **hiển thị công khai** |
| Giấu tỷ lệ phủ thấp | Hiện **32,52%** to, kèm giải thích quy định Quỹ |
| Giả vờ mọi số đều chắc chắn | Mọi số suy ra đều mang nhãn **"suy ra"** |

---

# 5. ĐÃ LÀM NHƯ THẾ NÀO

## 5.1 Nạp dữ liệu — theo header, không theo ô cứng

CSV của ngân hàng có **2 dòng tiêu đề** trước dữ liệu. Cách nạp theo **toạ độ ô** (A3, B3…) rất dễ vỡ nếu Quỹ đổi định dạng.

**Giải pháp:** tìm cột **theo tên tiêu đề**, không theo vị trí.

```
STT | Ngày/TNX Date/ Số CT/Doc No | Chi | Thu | Số dư/Balance |
Nội dung chi tiết/Transactions in detail | Năm | Tháng
```

Ngoài ra phát hiện: ô ngày gói **ngày + số dư** cách nhau bằng xuống dòng. Một vòng round-trip biến xuống dòng thành khoảng trắng, khiến **65.654/238.173 dòng (27,6%)** có `tx_time` là rác:

```
'31/12/2020 9774.0008477811'   ← ngày + số dư dính nhau
```

**Đã sửa** bằng cách tách theo xuống dòng rồi theo khoảng trắng. **Tiền không bị ảnh hưởng** (số dư là cột riêng, tổng khớp công bố tuyệt đối). Kết quả: khoảng dữ liệu hiển thị đúng **2018-02-08 → 2026-02-25**. Thêm 7 test hồi quy.

## 5.2 Bộ phân tích mã — phần khó nhất

Đây là nơi tập trung nhiều lỗi nhất, và là phần đóng góp kỹ thuật chính.

### Vấn đề: memo ngân hàng không phải dữ liệu sạch

Nó là **metadata ngân hàng dán liền với văn bản người viết**:

```
904214.271219.145325.SON HA LE DU AN NUOI EM NE3851-271219-14:53:24
└─trace─┘└─date─┘└time─┘└──── văn bản người viết ────┘
```

Một bộ phân tích ngây thơ đọc ra **ba mã**: `NE00014`, `NE03851`, `NE271219`.
**Chỉ `NE03851` là thật.** Hai cái kia là số trace và ngày.

### Bốn lỗi đã tìm và sửa

#### Lỗi 1 — Mã ma từ ngày/trace (6 chữ số)

Danh mục NE rộng **5 chữ số**. Số `271219` là ngày 27/12/19.

**Hậu quả cụ thể:** có giao dịch mà bộ phân tích chia **145.000.000 đ thành ba phần**, khiến mã thật `NE00298` chỉ nhận **48.333.333 đ** thay vì 145.000.000 đ.

**Cách sửa:** giới hạn phần số ở **5 chữ số** + thêm guard `(?![\d:])` + `strip_bank_metadata()`.

**Chi tiết đáng nhớ:** ban đầu tôi giả thuyết *"mã thật luôn nằm trong dãy liên tiếp"*. **Dữ liệu bác bỏ giả thuyết đó** — `NE110323` là ngày 11/03/23 đứng cạnh mã thật `NE10578`; `NE140819` là 14/08/19 đứng cạnh `NE3851`. Tôi **sửa giả thuyết theo bằng chứng**, không bảo vệ nó.

Kết quả: **342 dòng sai → 2** (và cả 2 là mã 6 số thật trong hai dãy viết tắt).

#### Lỗi 2 — Mã bị ngắt dòng đọc thành `NE00001`

Sao kê tự ngắt dòng ở cột cố định. Mã vắt qua chỗ ngắt đến dưới dạng `NE1` + xuống dòng + `156`. Sau khi chuẩn hoá, bộ phân tích đọc `NE1` → **NE00001** — đúng mã học sinh đầu tiên của Quỹ.

```
"...TRUONG THI MINH CHAU NE1 156"   → phải là NE01156
```

Đo trên dữ liệu thật: **44 memo** có dạng này, **23 memo bị đọc sai** → tiền của ít nhất 23 học sinh khác dồn vào NE00001.

**Đã sửa:** thêm `repair_line_wrap()` ghép lại mã **trước mọi bước khác**.

#### Lỗi 3 — Năm học đọc thành mã học sinh

Nhà tài trợ viết năm ngay cạnh mã:

```
"NE413 + NE414, 2019+2020"
"NE2019, NE2020"
"NE20192020"
"NE4708 - 2019/20"
```

Vì danh mục rộng 5 chữ số, `2019` **hợp lệ về cú pháp** — giới hạn độ rộng **không bắt được**.

Đo được: **371 dòng** được tạo cho `NE02018`…`NE02026`, riêng `NE02019` "nhận" **79 dòng**.

**Cái bẫy phải xử lý:** `NE02019` **vừa là năm, vừa là mã thật**. Có memo ghi nguyên văn:

```
"ck 1 ma NE02019 Quyen Mice"   ← giao dịch thật!
```

Nếu chặn cứng mọi số 2018–2026 thì **xoá mất một nhà tài trợ thật**.

**Giải pháp — phân biệt theo NGỮ CẢNH, không theo con số:**

| Chuỗi | Kết luận |
|---|---|
| `NE2019, NE2020` | **Năm** → loại |
| `NE20192020` | **Năm** → loại |
| `2019+2020` / `2019/20` | **Năm** → loại |
| `ck 1 ma NE02019` đứng một mình | **Mã thật** → giữ |

**Nguyên tắc khi phải đánh đổi:**
> Một mã ma làm sai lệch **một** học sinh.
> Một mã thật bị xoá thì **mất luôn một nhà tài trợ**.
> → Khi không đủ ngữ cảnh, **giữ lại an toàn hơn**.

Kết quả: **371 → 37 dòng** (37 còn lại là năm đứng một mình, ngữ cảnh không phân biệt được).

#### Lỗi 4 — Dãy số viết tắt bị mất

Sửa lỗi 1 ban đầu **làm hỏng** trường hợp `NE140370, 140371, 140372` (6 chữ số). Nhưng memo chứng minh dãy 6 số **có thật**.

**Đã sửa:** thêm `_RE_NE_BARE_CONTINUATION` + `expand_continuation()`, ghép chữ số đầu vào đuôi ngắn:

```
NE121215,16,17  →  NE121215, NE121216, NE121217
```

Nếu không sửa, tôi ghi **1 mã thay vì 3** — sai lệch phân bổ.

## 5.3 Idempotency — không nạp trùng

**Vấn đề:** nếu nạp lại cùng file, số tiền sẽ bị nhân đôi.

**Giải pháp ban đầu:** khoá SHA-256 theo `(số chứng từ + thời gian + số tiền)`.

**Lỗi tìm được:** có **7 giao dịch thật** trùng cả ba trường đó nhưng **khác memo** → bị khoá trùng loại bỏ. Đây chính là **-6.274.000 đ chênh lệch** so với số công bố.

**Đã sửa:** dùng **định danh dòng ổn định** thay vì tổ hợp ba trường.

**Kiểm chứng chéo:** số dòng tăng **236.023 → 236.030** (đúng +7). Tôi kiểm điều này để chắc rằng **không phải tôi chỉnh hằng số cho khớp** — mà là sửa dữ liệu.

## 5.4 Hiệu năng — SQLite cần ANALYZE

**Phát hiện:** truy vấn mất **4.188 ms**. Nguyên nhân: SQLite **không có thống kê** nên chọn kế hoạch thực thi sai.

**Giải pháp:** chạy `ANALYZE` (điền bảng `sqlite_stat1`) + thêm composite index.

**Kết quả:** **4.188 ms → 1,6 ms** (nhanh hơn ~2.600 lần).

## 5.5 Nhật ký kiểm toán — chống sửa

**Thiết kế:** bảng append-only, mỗi dòng lưu **hash của dòng trước**.

```
event 1: hash=A
event 2: prev=A, hash=B
event 3: prev=B, hash=C
```

Sửa bất kỳ dòng nào → hash chuỗi gãy → phát hiện được.

**Thêm:** trigger cơ sở dữ liệu **chặn** `UPDATE`/`DELETE` thường.

**Đã kiểm chứng:** sửa một dòng trên bản sao → **phát hiện tại event 1** ✅

**Tôi phải nói chính xác về giới hạn:** đây là **tamper-evident** (phát hiện được sửa), **KHÔNG phải immutable** (không sửa được). Người có quyền truy cập file DB **vẫn sửa được** — chỉ là sẽ bị phát hiện. **Đừng nói quá thành "không thể sửa".**

## 5.6 Maker-checker — tách nhiệm vụ

Một người không được vừa tạo vừa duyệt một đề nghị. Vi phạm → raise `PermissionError`.

## 5.7 Bảo vệ dữ liệu cá nhân

**Danh sách `FORBIDDEN_FIELDS`** kiểm tra trên **mọi** phản hồi API. Nếu trường cấm lọt ra, hệ thống **raise lỗi** thay vì trả về.

**Quyết định đã sửa:** ban đầu API trả `raw_description` (memo thô) và có tìm kiếm toàn văn. **Đây là lỗ hổng thật.**

Lý do: memo ngân hàng chứa **tên, số tài khoản, số điện thoại** người gửi. Tìm kiếm toàn văn biến API thành **công cụ tra cứu dữ liệu cá nhân**.

**Đã sửa:**
- Trả `description_masked` (đã che), **không bao giờ** trả memo thô
- **Tắt** tìm kiếm toàn văn

**Phát hiện bảo mật ở phần 7 đã chứng minh quyết định này là đúng** — không còn là phòng ngừa lý thuyết.

## 5.8 Gộp ngoại lệ — kiểm soát phải dùng được

**Vấn đề:** 125.713 dòng cần soát. Một hàng đợi như vậy là **kiểm soát không hoạt động** — không ai đọc hết.

**Giải pháp:** gộp theo **loại**, kèm **số lượng** và **giá trị đang gặp rủi ro**.

```
[medium] INBOUND_WITHOUT_CODE
  125.713 giao dịch tiền vào không gắn được mã ACN/NE,
  tổng 373.554.936.804 đ
```

**Kết quả:** 125.713 vấn đề → **1 dòng hành động được**.

## 5.9 Frontend an toàn CSP

Không dùng inline handler, không `style=`, chỉ **một** thẻ `<script>` ngoài → chạy được với `script-src 'self'; style-src 'self'`.

Đã kiểm: **0 inline handler, 0 style attribute**.

---

# 6. KẾT QUẢ RA SAO

## 6.1 Số liệu trên dữ liệu sản xuất thật

| Chỉ số | Giá trị |
|---|---|
| **Tổng dòng** | **238.173** — khớp CSV, không mất dòng |
| **Tiền vào** | 236.030 dòng / **553.550.809.401 đ** |
| **Tiền ra** | 2.143 dòng / **553.541.302.920 đ** |
| **Chênh lệch với số công bố** | **+0 đ cả hai chiều** |
| Bất biến đối soát | **KHỚP** — 180.389.417.047 = 180.389.417.047 |
| Dòng phân bổ | **140.325** |
| Mã NE phân biệt | **31.051** |
| Cần soát lại | 125.713 dòng |
| Tỷ lệ phủ | **32,52%** |
| Khoảng dữ liệu | 08/02/2018 → 25/02/2026 |

## 6.2 Điểm quan trọng nhất về con số

> **Tổng thu và tổng chi khớp số Quỹ công bố CHÍNH XÁC TỪNG ĐỒNG.**

Đây là điều kiện để mọi thứ khác đáng tin. Nếu tổng lệch, mọi con số chi tiết đều vô nghĩa.

Và tôi đã **kiểm chứng chéo** rằng mình không tự lừa: đọc trực tiếp header file CSV (`Tổng thu, 553.550.809.401`) và xác nhận số dòng tăng **236.023 → 236.030** — chứng minh +7 dòng là **sửa dữ liệu thật**, không phải chỉnh hằng số.

## 6.3 Kiểm thử

| Bộ kiểm thử | Kết quả |
|---|---|
| `tests/test_app.py` | **77 bài — OK** (~4 giây) |
| `verify_real_data.py` | **ALL CHECKS PASSED** |

**Bảy nhóm kiểm chứng trong `verify_real_data.py`:**

1. Tổng các phần = tổng thể (lệch 0)
2. Tiền vào/ra khớp số công bố (lệch 0)
3. Không còn mã vượt độ rộng ngoài hai dãy viết tắt thật
4. Nhật ký kiểm toán nguyên vẹn
5. **Phát hiện sửa đổi** (trên bản sao dùng-một-lần)
6. Hàng đợi ngoại lệ đã gộp
7. Phân bổ khớp đơn giá công bố

## 6.4 Bảng vector đã kiểm chứng

| Vector | Kết quả |
|---|---|
| SQL injection | ✅ Chặn |
| Path traversal | ✅ Chặn |
| Method không hợp lệ | ✅ 405 |
| Tìm memo thô | ✅ Chặn |
| Tìm số điện thoại / số tiền | ✅ Chặn |
| PII guard | ✅ Có test cho chính bộ kiểm tra |
| Sửa nhật ký kiểm toán | ✅ Phát hiện |
| Maker-checker | ✅ Chặn |
| Idempotency | ✅ Chặn nạp trùng |

**Chưa kiểm thử:** IDOR, rate limiting, upload file.

---

# 7. PHÁT HIỆN BẢO MẬT NGOÀI PHẠM VI BÀI LÀM

> Phần này **không thuộc yêu cầu đề bài**. Nó phát sinh khi tôi đi tìm dữ liệu thật.
> Tôi đưa vào vì nó **liên quan trực tiếp đến chủ đề minh bạch**.

## 7.1 Cách tìm ra

Báo cáo tài chính của Quỹ là **Google Sheet nhúng trong trang**, không phải API. Nên ID sheet phải nằm trong **file JavaScript** mà trình duyệt tải về.

**Nguyên lý:** frontend không thể giấu nguồn dữ liệu của chính nó, vì trình duyệt phải biết để tải.

Chi tiết phương pháp: xem `BAO_CAO_CACH_PHAT_HIEN_DU_LIEU.md`.

## 7.2 Phát hiện 1 — 10 sheet + 1 Drive folder công khai

File JS `page-e73e03b76ce68f16.js` (37.710 byte, công khai) chứa **14 mục cấu hình**, gồm **10 ID Google Sheet + 1 Drive folder**, tất cả là **giá trị thật**.


| Loại | Số lượng | Kiểm chứng |
|---|---|---|
| Sheet sao kê (2 tab) | 1 sheet | **200 · 34,8 MB** |
| Sheet hồ sơ chi phí theo tháng | 9 sheet | **200** (cả 9) |
| Drive folder chứng từ | 1 folder | **200** |

**Tổng cộng 12/12 đều tải được, không cần đăng nhập.** Chi tiết đường dẫn: `DUONG_DAN_DAY_DU_14_MUC.md`.

## 7.3 Nguyên nhân gốc — một dòng code

```javascript
sheetId: process.env.VCB_STATEMENTS_SHEET_ID ?? "1boFEZ…WgHg"
```

**Quỹ đã làm đúng một nửa:** dùng `process.env` → tức **biết** ID không nên viết cứng. Đây là thực hành tốt.

**Nhưng `??` phá hỏng tất cả:** nó nghĩa là *"nếu không có biến môi trường thì dùng giá trị bên phải"*, và giá trị bên phải là **ID thật**. Nên khi build, ID bị nhúng thẳng vào file công khai.

**Sửa một dòng:**
```diff
- process.env.X ?? "<ID thật>"
+ process.env.X
```

## 7.4 Dữ liệu cá nhân bị phơi — phần nghiêm trọng nhất

Trong sheet sao kê công khai, cột memo chứa:

| Loại | Số lượng |
|---|---|
| Số điện thoại | **14.328** |
| Email | **222** |
| Tên người gửi | **1.818** |
| Số tài khoản / tham chiếu | **87.434** |

**Đây là dữ liệu của NGƯỜI ỦNG HỘ, không phải của học sinh.**

Điểm quan trọng: **họ không hề đồng ý bị công bố thông tin cá nhân.** Họ gửi tiền cho một tổ chức từ thiện — và thông tin của họ bị công khai vĩnh viễn, ai cũng tải được 34 MB.

Và link dạng *"ai có link thì xem"* **không thể thu hồi**.

## 7.5 Phát hiện 2 — `robots.txt` làm lộ bản đồ

`robots.txt` là file **công khai**, liệt kê 9 route nhạy cảm:

```
/admin  /auth/  /children  /donors  /portal
/schools  /login-activity  /danh-sach-em-nuoi  /cong-thong-tin-nha-tai-tro
```

`robots.txt` **không chặn** ai — nó chỉ xin bot thân thiện đừng index. Nên file dùng để **ẩn** trở thành **bản đồ chỉ đường**.

**Kiểm chứng:** 9/9 route đều tồn tại thật.

**Nhưng phải nói công bằng:** `/admin` → `/admin/login`, `/api/auth/session` → `{"role":null}`, `/danh-sach-em-nuoi` không trả dữ liệu cho khách. **Xác thực chặn đúng** → đây là **rủi ro thông tin**, không phải rủi ro truy cập.

## 7.6 Phát hiện 3 — Thiếu 6/6 security headers

`quynuoiem.com` thiếu: `Content-Security-Policy`, `X-Frame-Options`, `HSTS`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`.

Đáng chú ý: `api.thiennguyen.app` **CÓ** HSTS, web chính **KHÔNG** → không nhất quán.

## 7.7 Những gì Quỹ làm ĐÚNG

Ghi nhận công bằng:

| Kiểm tra | Kết quả |
|---|---|
| `/.env`, `/.git/config`, `/package.json` | **404** — không lộ |
| `/admin` | **307 → `/admin/login`** |
| `/api/auth/session` cho khách | **`{"role":null}`** |
| `/danh-sach-em-nuoi` cho khách | **Không trả dữ liệu** |
| HSTS trên API | **Có** |

→ **Xác thực làm tốt. Dữ liệu học sinh được bảo vệ tốt.** Vấn đề nằm ở **lớp ngoài**.

## 7.8 Cách phân loại phát hiện này

| | Cần gì | Đây là? |
|---|---|---|
| **CVE** | Lỗi phần mềm, có bản vá | ❌ Không có lỗi phần mềm nào |
| **Pentest / red team** | Uỷ quyền, tấn công, vượt kiểm soát | ❌ Không tấn công, không vượt kiểm soát |
| **OSINT / rà soát công khai** | Đọc thông tin công khai | ✅ **Chính xác là cái này** |

**Khuyến nghị:** không dùng chữ "CVE", "pentest", "hack", "xâm nhập" trong báo cáo nộp. Không phải vì sai kỹ thuật, mà vì **nó làm nhỏ đi phát hiện thật**:

> Vấn đề **không phải** "Quỹ bị hack".
> Vấn đề **là** "Quỹ đang công bố dữ liệu cá nhân của 1.818 nhà tài trợ mà không nhận ra".

Cách gọi thứ hai vừa chính xác hơn, vừa chỉ đúng vào việc cần sửa.

---

# 8. QUYẾT ĐỊNH BẢO MẬT TRONG HỆ THỐNG

Tóm tắt các quyết định bảo mật của chính hệ thống bài làm (khác với phát hiện ở phần 7):

| Quyết định | Vì sao |
|---|---|
| SQLite **chỉ đọc** (`mode=ro`) | Web không thể sửa dữ liệu, kể cả khi có lỗi |
| **Chỉ có GET** | Không có bề mặt ghi để tấn công |
| Tìm cột **theo header** | Đổi định dạng file không phá hệ thống |
| `FORBIDDEN_FIELDS` trên mọi response | Phòng ngừa lộ PII ngay từ đầu ra |
| Trả `description_masked`, **không bao giờ** memo thô | Memo chứa tên/SĐT/email người gửi |
| **Tắt** tìm kiếm toàn văn | Tránh biến API thành công cụ tra cứu cá nhân |
| Nhật ký **append-only** + trigger chặn | Chống sửa, có phát hiện |
| Maker-checker | Tách nhiệm vụ tạo/duyệt |
| CSP-safe frontend | Không inline handler |
| 0 phụ thuộc ngoài | Không bề mặt supply-chain |

---

# 9. HƯỚNG VẪN HÀNH

## 9.1 Cho người dùng cuối

```
1. Mở link  →  thấy 4 KPI
2. Đọc thẻ bất biến  →  xác nhận tiền khớp
3. Xem thanh tỷ lệ phủ  →  biết bao nhiêu phần chưa gắn mã
4. Tra mã NE  →  tìm một học sinh cụ thể
5. Bấm giao dịch  →  xem tiền được chia thế nào
6. Xem ngoại lệ  →  biết vấn đề nào cần xử lý
7. Xem nhật ký  →  kiểm tra tính toàn vẹn
```

## 9.2 Cho vận hành viên

**Cập nhật dữ liệu:**
```bash
python build_database.py data/real_vcb.csv \
  --database data/nuoi_em_mvp.sqlite --mode statement
```

**Kiểm chứng sau khi nạp:**
```bash
python verify_real_data.py     # phải ra ALL CHECKS PASSED
python -m unittest discover -s tests
```

## 9.3 Nguyên tắc hiển thị số liệu

| Nguyên tắc | Thực hiện |
|---|---|
| Không trình bày số suy ra như số chắc chắn | Mọi số theo mã mang nhãn **"suy ra"** |
| Không ngụ ý đầy đủ | Nếu kết quả bị giới hạn, nói rõ |
| Không giấu tỷ lệ phủ thấp | Hiện **32,52%** to, kèm giải thích quy định Quỹ |
| Nêu rõ phạm vi | Banner đầu trang nói rõ nguồn + giai đoạn |

## 9.4 Giám sát định kỳ

| Việc | Tần suất |
|---|---|
| Chạy `verify_real_data.py` | Mỗi lần nạp dữ liệu |
| Kiểm tra hash chuỗi kiểm toán | Hàng ngày |
| Xem hàng đợi ngoại lệ | Hàng tuần |
| Sao lưu cơ sở dữ liệu | Hàng ngày |

---

# 10. CHƯA CÓ GÌ / GIỚI HẠN

## 10.1 Chưa làm — trung thực

| Hạng mục | Trạng thái |
|---|---|
| **RBAC** (phân quyền theo vai) | Có bảng seed, **chưa thực thi** |
| Luồng đề nghị thanh toán của trường | Chỉ có schema, **chưa có endpoint** |
| Ánh xạ NE → trường | **Chưa làm** — xem 10.3 |
| Topic 2 | **Chưa bắt đầu** |

## 10.2 Chưa kiểm thử bảo mật

- IDOR
- Rate limiting
- Upload file (chưa có endpoint nên chưa có bề mặt)

## 10.3 Điều quan trọng — tôi phải sửa một kết luận cũ

Trước đây tôi báo cáo:

> *"Tỷ lệ phủ 32,52% là **trần cứng** vì thiếu danh mục học sinh để ánh xạ NE → trường."*

**Điều này KHÔNG còn đúng.** Khi rà soát bảo mật, tôi tìm thấy **sheet hồ sơ chi phí** — chính là phần tôi nói là thiếu:

| Tôi từng thiếu | Sheet hồ sơ có |
|---|---|
| Tiền ra theo từng trường | ✅ `Trường` + `Số tiền giải ngân` |
| Số học sinh mỗi trường | ✅ `Số học sinh được hỗ trợ` |
| Chứng từ | ✅ `Link drive chứng từ` |

→ **32,52% KHÔNG phải trần cứng.** Có đường nâng tỷ lệ phủ.

**Giới hạn của chính nguồn đó:** đây là dữ liệu **tiền ra theo trường**, không phải **danh mục học sinh ↔ mã NE**. Nên nó mở **một** đường, không mở **tất cả**. Vẫn cần danh mục học sinh để ánh xạ NE → trường chính xác.

## 10.4 Giới hạn phạm vi

- **Một nguồn ngân hàng** (Vietcombank), chưa dùng tab VPBank
- **Một khoảng thời gian** (2018–2026)
- Không bao gồm dữ liệu **tiền ra liên kết chứng từ**
- Chưa rà nguồn ngoài `quynuoiem.com` (fanpage, site cũ)

---

# 11. PHỤ LỤC: DỮ KIỆN / SUY LUẬN / CÂU HỎI

## Dữ kiện (đã kiểm chứng trực tiếp)

**Về dữ liệu:**
- 238.173 dòng nạp, khớp CSV, không mất dòng
- Tiền vào/ra khớp số Quỹ công bố, **lệch 0 đồng** cả hai chiều
- Bất biến đối soát: 180.389.417.047 = 180.389.417.047
- 140.325 dòng phân bổ · 31.051 mã NE · phủ 32,52%
- Số dòng tăng 236.023 → 236.030 sau khi sửa lỗi khoá trùng

**Về lỗi đã sửa:**
- Mã ngắt dòng: 44 memo có dạng, **23 bị đọc sai**
- Năm thành mã: **371 dòng** → 37 sau khi sửa
- Mã ma 6 số: **342 dòng** → 2
- Ngày lẫn số dư: **65.654 dòng (27,6%)**
- Idempotency: 7 giao dịch bị loại oan

**Về kiểm thử:**
- 77 bài OK · `verify_real_data.py` ALL CHECKS PASSED
- Phát hiện sửa nhật ký tại event 1
- 4.188 ms → 1,6 ms sau ANALYZE

**Về phát hiện bảo mật:**
- 10 sheet + 1 Drive folder trong JS công khai, **12/12 HTTP 200**
- 14.328 SĐT · 222 email · 1.818 tên · 87.434 số TK trong sao kê
- `robots.txt` liệt kê 9 route, **9/9 tồn tại thật**
- 6/6 security headers thiếu trên web; API **có** HSTS
- `.env`, `.git/config` đều 404; `/admin` chặn đúng

## Suy luận (có bằng chứng, chưa xác nhận)

- Công bố **số tổng** là **cố ý** (minh bạch sau thanh tra)
- Phơi **dữ liệu cá nhân nhà tài trợ** nhiều khả năng **không cố ý**
- Quỹ dùng `process.env` → **có ý thức** cấu hình, không ngờ `??` phá hỏng
- Mỗi tháng một sheet → dấu hiệu **quy trình thủ công**, khớp vấn đề Excel
- Thiếu security headers có thể do **Next.js mặc định**

## Câu hỏi cho mentor / Quỹ

1. **Nhóm có được phép phân tích file công khai này không?** Và có nên nêu phát hiện dữ liệu cá nhân trong bài nộp?
2. **Quy tắc "mã NE không bao giờ tái sử dụng" được thực thi bằng gì** khi chuyển khỏi Excel?
3. **Quỹ có biết** memo công khai chứa tên/SĐT/email của 1.818 nhà tài trợ chưa?
4. **Quỹ còn công khai file nào khác** (Drive, website, fanpage) ngoài những cái đã tìm?
5. **Có danh mục học sinh** để ánh xạ NE → trường không? (để nâng tỷ lệ phủ)
6. **Có đồng ý cho rà soát sâu hơn** không (cần uỷ quyền bằng văn bản)?

## Khuyến nghị ưu tiên

| # | Việc | Ai làm | Khó |
|---|---|---|---|
| 1 | Sửa `??` thành `null` trong config | Kỹ thuật Quỹ | 1 dòng |
| 2 | Thu hồi chia sẻ công khai các sheet | Quản trị Quỹ | Cài đặt Google |
| 3 | Sửa `robots.txt` | Kỹ thuật Quỹ | Sửa file |
| 4 | Thêm security headers ở nginx | Kỹ thuật Quỹ | Không sửa code |
| 5 | **Không dán ID vào báo cáo nộp** | Nhóm | — |

---

# TÀI LIỆU LIÊN QUAN TRONG `docs/`

| File | Nội dung |
|---|---|
| `BAO_CAO_DU_AN.md` | Báo cáo dự án (bản trước) |
| `BAO_CAO_CACH_PHAT_HIEN_DU_LIEU.md` | Phương pháp phát hiện dữ liệu (4 bước) |
| `GIAI_THICH_BA_PHAT_HIEN.md` | Giải thích robots.txt / file JS / 10 sheet |
| `DUONG_DAN_DAY_DU_14_MUC.md` | Đường dẫn đầy đủ 14 mục (⚠️ nội bộ) |
| `PHAT_HIEN_BAO_MAT_VA_MA_NE.md` | Phát hiện bảo mật + lỗi mã NE |
| `BAO_CAO_RECON_NHE.md` | Kết quả recon nhẹ |
| `IMPLEMENTATION_PLAN.md` | Kế hoạch triển khai |

> ⚠️ **Lưu ý về `DUONG_DAN_DAY_DU_14_MUC.md`:** file này chứa ID thật, chỉ dùng nội bộ.
> Không kèm vào bài nộp. Trong báo cáo nộp chỉ nêu **số lượng** để chứng minh nguồn.
