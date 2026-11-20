# Dữ liệu mẫu để test tra cứu

`sao_ke_mau.csv` là một bảng sao kê **giả lập**, dựng đúng theo cấu trúc file
sao kê thật mà Quỹ công bố (cột `STT | Ngày/ TNX Date/ Số CT/ Doc No | Chi |
Thu | Số dư/ Balance | Nội dung chi tiết/ Transactions in detail | Năm |
Tháng`, ô ngày đóng gói kèm số chứng từ trên dòng thứ hai). File này **không**
chứa dữ liệu thật — toàn bộ mã NE, số tiền, số chứng từ, nội dung chuyển
khoản trong đây đều tự đặt ra chỉ để test, an toàn để chạy thử, commit, hay
xoá bất cứ lúc nào.

## Cách nạp thử

Đừng ghi đè lên database thật. Nạp vào một file test riêng:

```bash
python build_database.py du_lieu_mau/sao_ke_mau.csv --database /tmp/test_tra_cuu.sqlite
cp /tmp/test_tra_cuu.sqlite data/nuoi_em_mvp.sqlite   # rồi mới chạy app.py để xem trên trình duyệt
python app.py --port 8765
```

Nạp xong, lệnh trên in ra một dòng JSON tóm tắt — với file mẫu này sẽ là
`20 bank_transactions`, `22 transaction_allocations`, `2 exception_queue`
(1 giao dịch vào không ghi nội dung + 1 giao dịch vào ghi nội dung nhưng
không có mã).

## Vì sao chọn đúng những dòng này

20 dòng trong file được chọn để mỗi dòng demo một kiểu nội dung chuyển khoản
thật hay gặp, và để các mã NE cố ý **trùng tiền tố chữ số** với nhau — đúng
cái cần để thấy gợi ý (autocomplete) hoạt động có ý nghĩa, chứ không chỉ gợi
ý đúng 1 kết quả:

| STT | Nội dung | Để test cái gì |
|---|---|---|
| 1–3 | `NE01156`, `NE01156S`, `NE01156T` | Mã gốc + 2 biến thể ăn trưa/tối (S/T) của cùng một em — ba mã, ba nhà tài trợ khác nhau |
| 4 | `NE 1157` (gõ cách, không có số 0) | Người gõ tay thường không nhớ đủ số 0, hệ thống vẫn phải nhận ra |
| 5 | `NE01162 va NE01163` | Hai mã trong cùng một nội dung chuyển khoản |
| 6 | `NE89-90-91-92` | Một donor mua một lúc 4 mã liền số (chuỗi mã) |
| 7 | `NE140370, 140371, 140372` | Danh sách số trần nối theo sau một mã NE đầy đủ |
| 8–11 | `NE01200`, `NE01201`, `NE12005`, `NE12006` | Cùng gõ `12` ở ô tìm kiếm sẽ gợi ý cả 4 mã này |
| 12 | `ACN00042` | Mã nhà tài trợ (ACN), không phải mã em |
| 13 | `ACN00042 - NE01156` | Một dòng vừa có ACN vừa có NE — donor tự ghi tên mã em được tài trợ |
| 14 | (để trống) | Tiền vào nhưng không ghi gì — rơi vào "chưa phân loại" |
| 15 | "Ủng hộ quỹ chung, không ghi rõ mã em" | Tiền vào có chữ nhưng không có mã — rơi vào "cần xử lý" |
| 16–17 | Giải ngân học bổng, phí ngân hàng | Hai dòng tiền ra (cột Chi), không phải tiền vào |
| 18–20 | `NE01156`, `NE01157` lặp lại ở tháng sau, và `NE01156 - NE01157` | Một mã nhận hỗ trợ nhiều lần; một dòng chia cho 2 mã cùng lúc |

## Vài câu tìm thử ở trang Tra cứu

Mở `#/lookup` sau khi nạp file mẫu và gõ:

- **`1156`** — gợi ý hiện cả 3: `NE01156`, `NE01156S`, `NE01156T`, kèm tổng
  tiền và số dòng của mỗi mã. Bấm Enter ra trang chi tiết đầy đủ của
  `NE01156`.
- **`12`** — gợi ý hiện 4 mã trùng tiền tố: `NE01200`, `NE01201`, `NE12005`,
  `NE12006`. Đây là ví dụ rõ nhất cho việc gợi ý khớp theo **số**, không
  phải khớp theo chuỗi ký tự có đệm số 0 — xem giải thích bên dưới.
- **`ACN00042`** — nhận dạng là mã nhà tài trợ.
- **`YG26.000106`** (có dấu chấm, giống hệt trên sao kê) hoặc gõ tắt
  **`26000106`** (bỏ dấu chấm, chỉ còn số) — cả hai đều nhận dạng là **số
  tham chiếu** (xem mục riêng bên dưới).

## "Số tham chiếu" là gì

Đây là **số chứng từ / mã giao dịch do ngân hàng cấp** cho một dòng sao kê —
ví dụ `YG26.000106` — khác hẳn với **mã NE** (`NE01156`) là mã do người
chuyển khoản tự gõ vào nội dung để chỉ định ủng hộ cho em nào.

Một giao dịch luôn có đúng một số tham chiếu (ngân hàng cấp), nhưng có thể
có 0, 1, hoặc nhiều mã NE/ACN nằm trong phần nội dung của giao dịch đó (dòng
STT 6 ở trên có 1 số tham chiếu nhưng chứa 4 mã NE). Số tham chiếu dùng khi
bạn có biên lai/ảnh chụp sao kê ngân hàng và muốn tìm đúng dòng giao dịch đó
trong hệ thống — kể cả khi dòng đó chưa ghi rõ, hoặc ghi sai, mã em nào.

Hai điểm cần biết khi gõ số tham chiếu ở ô tìm kiếm:

1. **Trang Tra cứu (`#/lookup`) của khu quản trị chỉ xác nhận đây là một số
   tham chiếu** rồi nhắc dùng **bảng công khai** (trang `/`) để xem chi
   tiết giao dịch — trang quản trị cố tình không hiện nội dung sao kê thô ở
   đây để không biến API thành công cụ tra dữ liệu cá nhân.
2. Gõ số tham chiếu **có hay không có dấu chấm đều được** — cả ô tìm kiếm
   trang công khai lẫn gợi ý ở trang quản trị đều tự bỏ dấu chấm trước khi
   so khớp (sửa trong phiên làm việc này, vì trước đó gõ thiếu dấu chấm sẽ
   không ra kết quả).

Nói cách khác: **mã NE/ACN hỏi "ủng hộ cho ai"**, còn **số tham chiếu hỏi
"đây là giao dịch ngân hàng nào"** — hai trục tra cứu độc lập với nhau,
cùng gặp nhau tại một giao dịch.
