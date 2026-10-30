# Nuôi Em · Topic 4 — Bảng điều khiển minh bạch tài chính

Đọc sao kê ngân hàng của Quỹ Nuôi Em, đối soát từng khoản tiền vào với mã NE. Chỉ
đọc — không có chức năng sửa, thêm hay xoá gì.

Ban đầu mình định làm trên file mẫu của mentor. Nhưng file đó có 10 em và 9 giao
dịch: đủ để hiểu quan hệ ACN → NE → học sinh, không đủ để nói gì về một quỹ 238
nghìn giao dịch. Nên mình chuyển sang dùng sao kê Vietcombank mà Quỹ công bố trên
trang tài chính của mình — 238.173 dòng, từ 02/2018 đến 25/02/2026.

Phạm vi cần nói rõ trước khi ai đó trích dẫn số ở đây: đây là **một nguồn
Vietcombank, dừng ở 25/02/2026**. Không phải toàn bộ dữ liệu tài chính của Quỹ, và
chưa có VPBank hay MB.

> Đọc `SECURITY.md` trước khi dùng repo này. Dữ liệu gốc (sao kê 34 MB và database
> 176 MB) không có trong repo. Định danh của Quỹ trong `docs/` đã được che bớt.

## Chạy ứng dụng

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

hoặc:

```powershell
python app.py --open          # mở tại http://127.0.0.1:8765
python app.py --port 8792     # đổi cổng
```

Ứng dụng chỉ lắng nghe trên `127.0.0.1` và không được xuất bản lên Internet.
Mọi endpoint ghi (POST/PUT/PATCH/DELETE) trả về 405.

## Hai bề mặt, hai câu hỏi khác nhau

| Đường dẫn | Trả lời câu hỏi | Đối tượng |
|---|---|---|
| `/` | "Quỹ đã nhận và chi bao nhiêu?" | công chúng, nhà tài trợ |
| `/admin` | "Hôm nay phải làm gì?" | cán sự quỹ, kế toán, kiểm toán |

Người dùng hằng ngày đọc `docs/HUONG_DAN_QUAN_TRI.md` — hướng dẫn từng màn hình, ba
hàng đợi và việc phải làm với mỗi cái, những gì trang **chưa** làm được.

Trang công khai đặt số tổng lên trước. Trang quản trị đặt **hàng đợi việc** lên
trước, vì 125.713 dòng chưa đối soát không phải thứ đọc được bằng biểu đồ tròn —
nó phải được gom thành vài quyết định, mỗi quyết định kèm số tiền đang bị ảnh
hưởng.

Bốn endpoint mới phục vụ trang này:

| Endpoint | Trả về |
|---|---|
| `/api/admin/queue` | hàng đợi gom theo nguyên nhân, kèm số dòng và số tiền |
| `/api/admin/rows?bucket=&year=&cursor=` | các dòng trong một nguyên nhân, phân trang bằng keyset |
| `/api/admin/search?q=` | tự nhận dạng loại mã (NE / ACN / số tham chiếu) |
| `/api/ne?ne=` | hồ sơ một mã: dòng tiền, biến thể S/T, trạng thái hồ sơ |

Ô tra cứu nhận **một** loại đầu vào, không bắt người dùng chọn dropdown, vì cán
sự nhận mã từ tin nhắn Facebook, cuộc gọi hoặc ảnh chụp sao kê — không ai gõ
đúng định dạng. Deep link `/admin#/lookup?q=NE01156` mở thẳng kết quả, để gửi cho
người khác thay vì hướng dẫn họ tìm.

Số điện thoại **không** tra cứu được: nó chỉ tồn tại trong nội dung sao kê thô,
và cho tìm theo số điện thoại là biến ô tra cứu thành công cụ dò dữ liệu cá
nhân. Endpoint trả `kind: "blocked"` chứ không trả "không tìm thấy".

## Xây lại database

Nguồn là **CSV sao kê**, không phải Excel. Cột được định vị theo **tiêu đề**,
không theo toạ độ ô, nên thứ tự cột thay đổi vẫn nhập đúng.

```powershell
python build_database.py data\real_vcb.csv
```

Database tạo tại `data\nuoi_em_mvp.sqlite` (~179 MB). Tuỳ máy, rebuild toàn bộ
238.173 dòng thường mất khoảng 1–2 phút.

Nạp lại cùng một file là **idempotent**: khoá bất biến SHA-256 theo từng giao
dịch, nên nhập lại không làm tăng tổng.

## Kiểm thử

```powershell
python -m unittest discover -s tests -v     # 87 bài
python verify_real_data.py                  # đối chiếu với số Quỹ công bố
```

`verify_real_data.py` là bài kiểm tra quan trọng nhất: nó so từng con số với
**số Quỹ tự công bố**, không so với một con số khác do chính code này sinh ra.
Không có ngưỡng dung sai: lệch 1 đồng cũng thất bại.

## Kết quả trên dữ liệu thật

| Kiểm tra | Kết quả |
|---|---|
| Tổng các dòng phân bổ = tổng giao dịch được liên kết | **PASS** (lệch 0 đồng) |
| Tiền ra so với số Quỹ công bố | **khớp tuyệt đối** — 553.541.302.920 đ, lệch 0 |
| Dòng tiền vào so với số Quỹ công bố | **khớp tuyệt đối** — 553.550.809.401 đ, lệch 0 |
| Bảo vệ nhật ký kiểm toán | **PASS** — UPDATE/DELETE thông thường bị chặn; bypass đặc quyền vẫn bị hash chain phát hiện |
| Mã NE vượt khổ danh mục | 6 dòng / 140.661, đều là lô mã thật |
| Ngoại lệ | 125.670 dòng vấn đề gộp thành **1** mục hành động được |

## Vì sao mình làm cái này

Ngày 05/06/2026 Quỹ công bố văn bản về đợt xác minh của cơ quan chức năng
(17/12/2025 – 24/04/2026). Kết luận là không có vi phạm hình sự, không chiếm đoạt.
Nhưng trong văn bản đó Quỹ tự nhận đã vận hành dự án lớn qua tài khoản cá nhân,
dòng tiền lẫn lộn, không theo chuẩn kế toán, và quản lý bằng Excel nên sinh ra sai
mã, trùng mã, lỗi dữ liệu.

Chỗ đáng chú ý là Quỹ tự nói ra điều đó. Nghĩa là vấn đề không phải ai giấu tiền —
vấn đề là cách ghi chép không đủ chặt để tự chứng minh mình đúng.

Nên Topic 4 với mình không phải bài làm dashboard cho đẹp. Mục tiêu hẹp hơn: làm
cho một mã sai không thể lọt qua trong im lặng.

## Ba chỗ mình phải quyết, và vì sao quyết như vậy

**1. Tiền lưu một lần, phân bổ lưu ở bảng nối.**
Một giao dịch ngân hàng có thể viện dẫn tới 20 mã NE. Nếu nhân số tiền cho số
mã thì tổng tiền vào phồng lên gấp nhiều lần. `transaction_allocations` giữ phần
chia, và bất biến "các phần phải bằng tổng" được kiểm tra ở mọi lần chạy.

**2. Chỉ số tổng hợp + `ANALYZE`, không phải `OFFSET`.**
Trên 1 triệu dòng, truy vấn nóng mất **4.188 ms** khi thiếu thống kê và chỉ số;
sau khi thêm `idx_tx_direction_time` và chạy `ANALYZE` còn **1,6 ms**. Ghi chú
kèm theo: `OFFSET 500000` chỉ mất 34 ms, tức `OFFSET` **không** phải nút cổ chai
— ghi lại để không ai tối ưu sai chỗ.

**3. Ngoại lệ gộp theo nhóm, không mỗi dòng một cảnh báo.**
125.670 dòng tiền vào không gắn được mã. Một hàng đợi 125.670 dòng là một kiểm
soát không hoạt động được, vì không ai đọc hết. Hệ thống gộp thành **một** mục
kèm số lượng và giá trị đang gặp rủi ro.

## Lỗi đã tìm ra và sửa trong quá trình làm

**Mã NE giả sinh từ ngày và số trace.** Đây là lỗi nghiêm trọng nhất. Bộ tách mã
đọc mọi chuỗi `NE<số>`, kể cả khi `<số>` là metadata ngân hàng:

```
483019.171024.133756.BCG FOUNDATION NUOI 50 BE - NE00298-171024-13:36:06
```

Câu này từng cho ra **ba** mã: `NE00013`, `NE00298`, `NE171024`. Chỉ `NE00298`
là thật. Hệ quả: 145.000.000 đ bị chia ba, nên mã thật chỉ được ghi 48.333.333 đ.

Cách sửa không phải "siết regex thành `NE\d{5}`" — làm vậy mất khoảng 150 nghìn
tham chiếu viết bằng văn xuôi như `NE77, NE78, NE79`. Cách sửa đúng là: cắt tiền
tố metadata ngân hàng, xoá giờ `HH:MM:SS`, chặn số hạng ở 5 chữ số, và chỉ cho
số 6 chữ số đi qua khi nó nằm trong một **lô liệt kê tường minh** như
`NE140370, 140371, 140372` (và dạng viết tắt `NE121215,16,17`).

Kết quả: 342 dòng có mã giả → **2** (đúng hai lô mã thật). 9/9 ca kiểm thử.

**Bảy giao dịch thật bị xem nhầm là trùng.** Sao kê có bảy nhóm cùng số chứng
từ, thời gian và số tiền nhưng nội dung khác nhau. Khoá idempotency cũ làm mất
7 dòng và đúng 6.274.000 đ tiền vào. Khoá mới dùng định danh dòng ổn định,
giữ đủ 238.173 dòng nhưng nạp lại cùng file vẫn không nhân đôi dữ liệu.

**Hai bản cài đặt cho một kiểm soát an ninh.** `app.py` từng tự tính lại hash
chuỗi kiểm toán thay vì gọi `reconciliation.AuditChain.verify()`. Hai bản cài
đặt của cùng một kiểm soát nghĩa là chỉ cần sửa một bên là chúng âm thầm bất
đồng. Đã gom về một chỗ.

**Script kiểm tra đọc nhầm database cũ.** `verify_real_data.py` trỏ vào
`real_test.sqlite` (rác còn lại từ lần profiling) và tự "khôi phục" dữ liệu sau
khi giả lập sửa, nên lần chạy thứ hai không còn gì để phát hiện và báo sai là
"không phát hiện sửa đổi". Đã sửa: trỏ đúng database đang phục vụ, và giả lập
sửa trên **bản sao dùng một lần**.

## Chỉ số suy ra — đọc kỹ trước khi trích dẫn

Quỹ **không** công bố số tiền theo từng mã NE. Số tiền mỗi mã ở đây do hệ thống
**chia ra** từ giao dịch, nên là **suy ra**, không phải số Quỹ đã xác nhận. Mỗi
con số đều mang nhãn `allocation_policy` và giao diện ghi rõ chữ "suy ra".

## Bảo vệ dữ liệu và giới hạn của audit

Sao kê gốc có thể chứa tên hoặc định danh trong phần nội dung. Hệ thống cần phần
thô đó để tách mã, nhưng API mặc định **không trả và không cho tìm kiếm** nội
dung sao kê thô hoặc số tài khoản. Giao diện chỉ hiện mô tả tổng hợp từ mã NE/ACN
đã tách. `data/real_vcb.csv` và database sinh ra phải ở máy cục bộ, không đưa lên
Git hoặc đóng gói nộp công khai. Production còn cần mã hoá, phân quyền và chính
sách lưu giữ/xoá dữ liệu.

Audit log là **tamper-evident**, không phải bất biến tuyệt đối. Trigger chặn
UPDATE/DELETE thông thường; hash chain phát hiện thay đổi không được băm lại.
Người sở hữu toàn quyền database vẫn có thể gỡ trigger và xây lại cả chuỗi, nên
production cần neo hash ra hệ thống độc lập hoặc kho WORM.

### Các vector đã kiểm chứng bằng kiểm thử tự động

| Vector | Kết quả |
|---|---|
| `' OR 1=1--` và biến thể trong `q`, `tx`, `ne` | Vô hại — tham số hoá toàn bộ |
| Path traversal `/../app.py`, `/%2e%2e/app.py`, `..%2f` | Bị chặn (400/403/404) |
| POST/PUT/PATCH/DELETE trên mọi endpoint | 405 |
| Tìm kiếm nội dung sao kê thô (`q=xay truong`) | Trả 0 dòng — không phải bề mặt tìm kiếm |
| Số điện thoại / số tiền làm từ khoá tìm kiếm | Trả 0 dòng |
| Trường PII (`student_name`, `phone`, `date_of_birth`, …) trong phản hồi | Bộ kiểm tra chặn, và có test cho chính bộ kiểm tra |
| Sửa/xoá một dòng audit log | Chuỗi đứt, báo đúng `id` |
| Maker tự duyệt thay đổi của mình | `PermissionError` |
| Nạp lại cùng file sao kê | Idempotent, tổng không đổi |

Còn thiếu: IDOR/BOLA (chưa có nhiều vai trò để kiểm), rate limiting, và tải
chứng từ — chưa có endpoint ghi nên chưa có bề mặt để test.

Các KPI “dòng tiền vào/ra” là chuyển động ngân hàng gộp. Chúng không tự động là
doanh thu/chi phí kế toán cho tới khi có chứng từ và quy tắc phân loại.

## Chưa có gì

Chưa có dữ liệu VPBank/MB hoặc dữ liệu sau 25/02/2026; chưa có đăng nhập, phân
quyền (vai trò đã tạo trong CSDL nhưng chưa cưỡng chế),
thao tác ghi, webhook Casso thật, luồng chi có chứng từ và phê duyệt (mới có
schema), chứng từ số, hay danh mục học sinh để nối mã NE với trường.

## Về Topic 2

Topic 4 làm trước, Topic 2 (chatbot RAG) làm sau. Phần dùng chung đã sẵn: bảng
`students`, `schools`, `student_supports` và trường `ne_code` chính là thứ
chatbot cần để trả lời "mã NE của em này là gì" mà không phải đọc lại sao kê.
Chưa nên làm Topic 2 trước khi việc tách mã ở Topic 4 đủ tin cậy — chatbot trả
lời sai mã sẽ nhân sai sót lên, thay vì chỉ hiển thị sai một ô.

## Tài liệu trong `docs/`

| File | Nội dung |
|---|---|
| `BAO_CAO_TONG_HOP_DAY_DU.md` | Báo cáo tổng hợp 11 phần: website có gì, file mẫu mentor cho được gì, đề bài, hướng giải quyết, đã làm gì, kết quả, hướng vận hành |
| `BAO_CAO_DU_AN.md` | Báo cáo dự án (bản trước, giữ để đối chiếu) |
| `BAO_CAO_CACH_PHAT_HIEN_DU_LIEU.md` | Cách phát hiện dữ liệu công khai từ bundle JavaScript |
| `BAO_CAO_RECON_NHE.md` | Rà soát bề mặt công khai: header, TLS, robots.txt, route, API |
| `PHAT_HIEN_BAO_MAT_VA_MA_NE.md` | Phát hiện bảo mật và các lỗi tách mã NE |
| `GIAI_THICH_BA_PHAT_HIEN.md` | Giải thích chi tiết `robots.txt`, 10 sheet + 1 Drive, và file JS gốc |
| `GIAI_THICH_DO_PHU.md` | Vì sao 32,52% tính theo giao dịch, không chia cho số mã |
| `DUONG_DAN_DAY_DU_14_MUC.md` | Đường dẫn của 14 mục cấu hình tìm thấy trong bundle |
| `ERD_VA_LUONG_LOI.md` / `.pdf` | ERD 12 thực thể, 11 khoá ngoại, 5 cổng lỗi |
| `ERD_DRAWIO.drawio` | ERD dạng bảng, mở và sửa bằng diagrams.net |
| `KIEN_TRUC_DRAWIO.drawio` | Sơ đồ kiến trúc hệ thống |
| `IMPLEMENTATION_PLAN.md` | Kế hoạch triển khai |
| `Bao_cao_chi_tiet_he_thong_minh_bach_tai_chinh_Nuoi_Em.docx` | Bản Word của báo cáo |

## Giấy phép và phạm vi

Mã nguồn công bố để tham khảo học thuật. Báo cáo kết luận về **thiết kế hệ thống và
kiểm soát dữ liệu**, không phải về hành vi hay ý định của bất kỳ cá nhân nào, và không
phải kết luận pháp lý. Xem `SECURITY.md` để biết giới hạn sử dụng dữ liệu trích dẫn.
