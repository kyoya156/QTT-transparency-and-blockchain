# Kịch bản demo — 5 phút

Dùng cho buổi demo 20:00 ngày 17/10/2026.

---

## 0. Trước khi vào (làm lúc 19:50)

1. **Mở link trước 5 phút.** Sandbox ngủ khi không có truy cập; lần gọi đầu sau khi
   ngủ mất **hơn 25 giây**. Mở sẵn một tab, để đó.
2. **Đừng F5 liên tục** — mỗi lần tải lại là một lần chờ.
3. **Mở sẵn 3 thứ trong tab khác**: repo GitHub, `docs/DANH_GIA_HOAN_THIEN.md`,
   và ảnh chụp màn hình phòng khi link chết.

Link: `https://58572998c95f47f58fe38aefe20864dc.sg2.agentos-app.run`

---

## 1. Năm con số phải thuộc

| | Số | Nói gì |
|---|---:|---|
| Tiền vào | **236.030** GD / **553.550.809.401 đ** | khớp số Quỹ công bố, lệch 0 |
| Tiền ra | **2.143** GD / **553.541.302.920 đ** | khớp số Quỹ công bố, lệch 0 |
| Tổng dòng | **238.173** | 02/2018 → 25/02/2026 |
| Độ phủ | **32,52%** | 179,99 tỷ / 553,55 tỷ |
| Chưa gắn mã | **125.713** GD | gộp thành 1 mục ngoại lệ |

Hai số phụ nếu bị hỏi sâu: **31.051 mã NE**, **140.325 dòng phân bổ**.

---

## 2. Kịch bản 5 phút — theo đúng thứ tự khối trên trang

### ① Mở đầu (20 giây) — khối "Tiền vào có truy được về từng em không?"

> "Đây không phải dashboard làm cho đẹp. Câu hỏi của nó là: mỗi đồng vào có truy được
> về một em cụ thể không. Câu trả lời hiện tại là **chưa hoàn toàn** — và trang này
> hiện đúng chỗ chưa được, thay vì giấu."

Điểm mạnh: mở đầu bằng giới hạn, không bằng thành tích. Người chấm nghe nhiều lời
khoe rồi.

### ② Đối soát (60 giây) — khối "Đối soát: các phần phải bằng tổng"

> "Một giao dịch có thể nhắc tới 20 mã NE. Nếu nhân số tiền cho số mã thì tổng phồng
> lên gấp nhiều lần. Nên tiền lưu **một lần** ở bảng giao dịch, phần chia lưu ở bảng
> nối. Bất biến 'các phần phải bằng tổng' được kiểm ở mọi lần chạy — hiện lệch **0
> đồng** trên cả 110.317 giao dịch có mã."

### ③ Độ phủ (60 giây) — khối "Độ phủ"

> "32,52% tiền vào gắn được ít nhất một mã. 67,48% còn lại thì không.
> Con số này tính **theo giao dịch**, không chia tổng tiền cho số mã — vì một mã có
> thể là 1 tháng hoặc 100 tháng."

Nếu bị hỏi "sao thấp thế": xem mục 3, câu 1.

### ④ Tra cứu (90 giây) — khối "Tra cứu"

Gõ **`NE00298`**. Kết quả: 9 dòng phân bổ, tổng 159.250.000 đ.

> "Một mã, chín lần nhận tiền, tổng 159 triệu. Đây là chỗ thấy rõ mã NE là vĩnh viễn —
> một em, nhiều lần ủng hộ, nhiều năm."

### ⑤ Ngoại lệ (40 giây) — khối "Hàng đợi ngoại lệ"

> "125.713 giao dịch chưa gắn mã. Nếu hiện thành 125.713 dòng thì không ai đọc hết, và
> kiểm soát coi như không tồn tại. Nên gộp thành **một** mục, kèm số lượng và số tiền
> đang gặp rủi ro."

### ⑥ Kiểm toán (40 giây) — khối "Nhật ký kiểm toán"

> "Nhật ký là **tamper-evident**, không phải bất biến tuyệt đối. Em không nói quá:
> trigger chặn UPDATE/DELETE thông thường, chuỗi hash phát hiện sửa đổi. Nhưng người
> có toàn quyền database vẫn gỡ được trigger — nên production cần neo hash ra ngoài."

### ⑦ Kết (20 giây)

> "Toàn bộ API là **9 route GET**, mọi lệnh ghi trả 405, database mở read-only. Nên
> đưa link công khai cũng không ai sửa được dữ liệu."

---

## 3. Năm câu hỏi khó — trả lời sẵn

**1. "Vì sao chỉ 32,52%? Hệ thống dở à?"**

> "Không phải lỗi code. Hệ thống biết tiền vào mã NE nào, nhưng **không biết mã đó là
> em nào, trường nào** — vì Quỹ chưa công bố danh mục học sinh. Không có danh mục thì
> không thể nối. Và phần chưa nối được có giá trị trung bình **cao hơn** phần nối
> được (2,97 triệu so với 1,63 triệu mỗi giao dịch), nên đây không phải tiền lẻ."

**2. "Deploy lên AWS mà dùng SQLite à?"**

> "Nguồn sự thật của hệ thống là **file sao kê**, database chỉ là bản dẫn xuất — dựng
> lại từ đầu được bằng một lệnh. Bản dẫn xuất chỉ đọc thì không cần database server.
> Postgres sẽ vào khi Quỹ bắt đầu **ghi** — đề nghị chi, phê duyệt, chứng từ."

**3. "Sao không lấy dữ liệu học sinh?"**

> "Không có để lấy. Đó là dữ liệu Quỹ giữ, không công bố. Đây là việc **xin dữ liệu**,
> không phải việc viết thêm code."

**4. "Đây có phải là hack không?"**

> "Không. Toàn bộ dữ liệu là thứ Quỹ tự công bố công khai trên trang tài chính của
> mình, đọc được bởi bất kỳ ai, không cần đăng nhập. Em chỉ dùng GET, không thử vượt
> quyền, không dò quét. Và em đã báo Quỹ về những gì tìm thấy."

**5. "Số này có tin được không?"**

> "Đây là chỗ em tin nhất: hệ thống so với **số Quỹ tự công bố**, không so với số do
> chính code sinh ra. Lệch **0 đồng** ở cả hai chiều. Có script kiểm tra riêng
> (`verify_real_data.py`), không có ngưỡng dung sai — lệch 1 đồng là fail."

---

## 4. Ba phương án dự phòng

| Tình huống | Làm gì |
|---|---|
| Link chết hoặc chậm | Mở ảnh chụp màn hình đã lưu; nói "em có bản chạy local, để em mở" |
| Mạng yếu | Chạy `python app.py --open` trên máy, mở `127.0.0.1:8765` |
| Quên số | Mở `docs/DANH_GIA_HOAN_THIEN.md` — có đủ bảng số |

---

## 5. Ba điều không nên nói

1. **"Hệ thống đã hoàn thiện."** Nó chưa. Nói "phần tiền vào xong, phần tiền ra mới có
   schema" thì đáng tin hơn nhiều.
2. **"Em đã hack được quỹ."** Sai về bản chất và làm mất thiện cảm. Nói "em tìm thấy
   dữ liệu công khai bị lộ".
3. **"32,52% là do thiếu dữ liệu nên em để vậy."** Nghe như bào chữa. Nói kèm con số
   2,97 triệu — nó cho thấy bạn hiểu vấn đề, không phải bỏ qua.

---

## 6. Nếu thầy hỏi "dữ liệu thật đâu, sao tên bị che?"

> "Bản công khai em đã bỏ nội dung chuyển khoản thô, vì trong đó có tên, số điện thoại
> và email của khoảng 1.818 nhà tài trợ. Dự án của em đang chỉ ra đúng việc đó, nên
> đưa nguyên danh tính thật lên một host mới thì tự mâu thuẫn. Mọi con số tiền, mã NE
> và đối soát vẫn là số thật, không đổi."

Đây là câu trả lời **tốt**, không phải câu xin lỗi — nó cho thấy bạn hiểu nguyên tắc
dữ liệu cá nhân.
