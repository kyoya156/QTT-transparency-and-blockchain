# Hướng dẫn dùng trang quản trị

Dành cho người dùng hằng ngày: cán sự quỹ, kế toán, người chuẩn bị hồ sơ giải ngân.
Không cần biết SQL, không cần biết Python.

---

## 0. Trang này để làm gì

Hai trang, hai câu hỏi khác nhau. Đừng nhầm.

| Trang | Đường dẫn | Trả lời câu hỏi | Dành cho |
|---|---|---|---|
| Công khai | `/` | "Quỹ đã nhận và chi bao nhiêu?" | nhà tài trợ, công chúng |
| Quản trị | `/admin` | "**Hôm nay tôi phải làm gì?**" | cán sự quỹ, kế toán |

Trang công khai đặt số tổng lên trước. Trang quản trị đặt **việc cần làm** lên trước,
vì 125.713 dòng chưa đối soát không phải thứ đọc được bằng biểu đồ tròn — nó phải
được gom thành vài quyết định, mỗi quyết định kèm số tiền đang bị ảnh hưởng.

Nguyên tắc chung của cả hai trang: **con số nào cũng bấm vào được để xem dòng phía sau
nó.** Không có số tổng nào đứng một mình.

---

## 1. Mở trang

```powershell
.\run.ps1                 # tự mở trình duyệt
```

hoặc:

```powershell
python app.py --open      # mặc định cổng 8765
python app.py --port 9000 --open
```

Rồi mở `http://127.0.0.1:8765/admin`.

**Điều kiện:** phải có database `data\nuoi_em_mvp.sqlite`. Nếu chưa có, chương trình
báo lỗi và chỉ cách tạo:

```powershell
python build_database.py data\real_vcb.csv
```

**Chưa có đăng nhập.** Trang này không hỏi mật khẩu, vì nó được thiết kế để chạy trên
máy nội bộ của người dùng. Đừng mở cổng ra Internet khi chưa làm phần đăng nhập —
xem mục 7.

---

## 2. Ba màn hình

| Màn | Trả lời | Mở khi nào |
|---|---|---|
| **Tổng quan** | "Bức tranh đang thế nào, chỗ nào tệ nhất?" | đầu ngày, hoặc khi cần báo cáo |
| **Hàng đợi** | "Việc gì đang chờ, dòng nào cụ thể?" | khi bắt tay vào xử lý |
| **Tra cứu** | "Mã này là gì, đã nhận bao nhiêu?" | khi có người hỏi về một mã |

Chuyển màn bằng menu bên trái. Trên điện thoại, menu thu thành hàng tab ngang ở đầu
trang.

---

## 3. Màn Tổng quan

### 3.1 Bốn thẻ số

Đây là bốn con số phải hiểu trước khi đọc bất cứ thứ gì khác.

| Thẻ | Con số hiện tại | Nghĩa là gì | Lấy từ đâu |
|---|---:|---|---|
| **Dòng vào chưa gán mã** | 125.713 dòng · 373,6 tỷ | Tiền vào mà nội dung chuyển khoản không chứa mã NE nào. Hệ thống không biết tiền này của em nào. | `processing_status = 'needs_review'` |
| **Mã có tiền, chưa có hồ sơ** | 31.051 mã · 180,4 tỷ | Mã đã nhận tiền nhưng chưa gắn với học sinh hay trường nào. | mã NE không có trong `student_supports` |
| **Độ phủ tiền vào** | 32,52% | Tỉ lệ tiền vào nằm trong giao dịch có nhận diện được ít nhất một mã. | 179,99 tỷ / 553,55 tỷ |
| **Phần chia khớp tổng** | Khớp | Tổng các phần chia **bằng đúng** tổng tiền của các giao dịch đã chia. | 180.389.417.047 = 180.389.417.047 |

Đọc theo thứ tự này:

1. **Khớp hay Lệch?** Nếu Lệch, dừng lại. Mọi số khác đều không đáng tin cho tới khi
   xử lý. Đây là bất biến kế toán: các phần phải bằng tổng.
2. **Độ phủ bao nhiêu?** Đây là giới hạn trên của "truy được về từng em". 32,52%
   nghĩa là gần 2/3 số tiền vào chưa gắn được với một mã nào.
3. **Hai hàng đợi còn bao nhiêu?** Đây là việc phải làm, không phải số liệu để báo cáo.

> **Lưu ý dễ nhầm:** vì danh mục học sinh còn trống, **mọi** mã đều "chưa có hồ sơ" —
> nên thẻ thứ hai (180,4 tỷ) hiện bằng đúng tổng tiền đã phân bổ. Đó không phải lỗi
> tính toán, mà là hệ quả của việc chưa nhập danh mục. Khi nhập danh mục vào, số này
> sẽ tụt xuống.

### 3.2 Khối "Cần xử lý"

Ba nút, sắp theo **số dòng giảm dần** — thứ tự người ta thực sự làm việc, không phải
thứ tự theo số tiền.

Mỗi nút hiện: tên nguyên nhân, số tiền đang bị ảnh hưởng, số dòng, và **việc phải làm**.
Bấm vào là mở màn Hàng đợi đã lọc sẵn theo nguyên nhân đó.

| Nguyên nhân | Việc phải làm (ghi trên nút) |
|---|---|
| Dòng vào không tìm thấy mã NE | Gán mã hoặc chuyển quỹ ẩn danh |
| Mã có tiền nhưng chưa có hồ sơ | Gắn hồ sơ học sinh |
| Dòng ra chưa phân loại kế toán | Nối với đề nghị thanh toán |

Số tiền trên mỗi nút **không phải tiền đã mất**. Nó là số tiền đang nằm trong nhóm
chưa xử lý. Cách nói đúng khi báo cáo: *"373,6 tỷ chưa gắn được mã"*, không phải
*"373,6 tỷ bị thất thoát"*.

### 3.3 Khối "Tình trạng hệ thống"

Năm dòng, trả lời "dữ liệu này có đáng tin không":

| Dòng | Ý nghĩa | Khi nào cần lo |
|---|---|---|
| Lần import gần nhất | tên file đã nạp | khác file bạn vừa nạp → nạp chưa thành công |
| Thời điểm nạp | ngày nạp file đó | cũ hơn dữ liệu bạn có → cần nạp lại |
| Đã nạp | số giao dịch · số dòng phân bổ | ít hơn lần trước → nghi ngờ |
| Khoảng dữ liệu | ngày đầu → ngày cuối | thiếu tháng gần nhất → file chưa đủ |
| Chuỗi audit | **toàn vẹn** hoặc **đứt tại #…** | đứt = có người sửa/xoá lịch sử |

Chuỗi audit là dãy băm nối tiếp nhau. Nếu một dòng lịch sử bị sửa hoặc xoá, chuỗi sẽ
đứt và trang báo đúng vị trí đứt. Đây là **phát hiện được**, không phải **không sửa
được** — đừng nói mạnh hơn thực tế.

### 3.4 Biểu đồ "Tiền vào chưa gắn mã, theo năm"

Số dòng chưa gắn mã chia theo năm. Dùng để trả lời "chuyện này mới xảy ra hay lâu rồi?"
— hiện tại nặng nhất là 2023 (44.874 dòng), tức là vấn đề tích luỹ nhiều năm, không
phải sự cố một tháng.

---

## 4. Màn Hàng đợi

Đầu trang luôn ghi hai thứ: **nguyên nhân** đang mở, và **việc phải làm** với nguyên
nhân đó. Ví dụ: *"Mã đã nhận tiền nhưng chưa gắn với học sinh hoặc trường · Việc phải
làm: Gắn hồ sơ học sinh."* — để không phải nhớ mình vào đây làm gì.

### 4.1 Bộ lọc

- **Nguyên nhân** — chọn một trong ba hàng đợi ở trên.
- **Năm** — chỉ hiện với hàng đợi dòng tiền. Với hàng đợi "mã chưa có hồ sơ", ô này
  **bị ẩn có chủ đích**: một mã trải qua nhiều năm, nên lọc theo năm sẽ đổi câu hỏi
  thành "mã nào có phát sinh trong năm đó" — một câu hỏi khác, dễ gây hiểu sai.

### 4.2 Bảng

Hai hàng đợi dòng tiền có bốn cột:

| Cột | Nghĩa |
|---|---|
| Ngày | ngày giao dịch trên sao kê |
| Số tiền | số tiền của cả giao dịch, đơn vị đồng |
| Mã giao dịch | số tham chiếu của ngân hàng — dùng để tra lại trên sao kê gốc |
| Trạng thái | trạng thái xử lý nội bộ |

Hàng đợi mã chưa có hồ sơ có bốn cột khác:

| Cột | Nghĩa |
|---|---|
| Mã NE | mã hỗ trợ, giữ nguyên hậu tố S/T nếu có |
| Số dòng | số lần mã này được chia tiền |
| Tổng đã nhận | tổng tiền mã này đã nhận |
| xem → | mở hồ sơ mã |

### 4.3 Cái gì bấm được, cái gì không

- **Dòng trong hàng đợi mã** → bấm được, mở sang màn Tra cứu.
- **Dòng tiền** → **không** bấm được, và đây là chủ đích. Hệ thống chưa có chức năng
  ghi (chưa có bảng cấp mã, chưa có API ghi), nên bấm vào cũng chỉ đọc được câu
  "không làm gì được". Một nút bấm không dẫn tới đâu thì tệ hơn là không có nút.
- **Xem thêm** → tải 25 dòng tiếp theo. Chỉ hiện khi còn dòng phía sau.

### 4.4 Vì sao chưa có nút "Gán mã"

Vì chưa có chỗ để ghi. Gán một mã cho một giao dịch cần: (1) bảng cấp mã để biết mã
nào còn trống, (2) API ghi có kiểm soát người làm – người duyệt, (3) nhật ký ghi lại
ai đổi gì. Cả ba chưa xây. Trang này hiện là **bề mặt đọc**: nó cho biết phải làm gì,
việc gán mã hiện vẫn làm ngoài hệ thống.

---

## 5. Màn Tra cứu

### 5.1 Một ô, nhiều loại đầu vào

Cán sự nhận mã từ tin nhắn Facebook, từ cuộc gọi, hoặc từ ảnh chụp sao kê — không ai
gõ đúng một định dạng. Nên ô này tự nhận dạng, người dùng không phải chọn dropdown.

| Bạn nhập | Hệ thống hiểu | Kết quả |
|---|---|---|
| `NE1156`, `ne 1156`, `1156`, `1156s` | mã NE, tự đệm thành 5 chữ số | mở hồ sơ mã `NE01156` |
| `ACN02497` | mã nhà tài trợ | báo **chưa dùng được** (xem 5.4) |
| số có **9–11** chữ số | bị coi là số điện thoại | **từ chối tra** (xem 5.5) |
| dãy số khác | số tham chiếu ngân hàng | chỉ sang bảng công khai để tra |
| chữ (tên trường, tên tỉnh) | không nhận dạng | báo chưa hỗ trợ |

### 5.2 Kết quả tra một mã gồm bốn khối

| Khối | Cho biết |
|---|---|
| **Mã và tình trạng** | mã, suất ăn (bữa trưa / bữa tối / cả S và T), số dòng phân bổ, tổng đã nhận, các biến thể S/T |
| **Trường và hồ sơ** | trường, tỉnh, lớp — hoặc thông báo "chưa có hồ sơ" |
| **Dòng tiền nhận được** | tối đa 8 dòng gần nhất: ngày, số tiền, cách chia, trạng thái |
| **Nhà tài trợ** | mã ACN — hiện luôn là "chưa gắn mã ACN" |

### 5.3 Gửi kết quả cho người khác

Mỗi lần tra cứu là một đường dẫn riêng. Ví dụ:

```
http://127.0.0.1:8765/admin#/lookup?q=NE01156
```

Copy nguyên đường dẫn này gửi đi, người nhận mở là ra đúng kết quả — không phải
hướng dẫn họ bấm vào đâu.

### 5.4 Vì sao mã ACN chưa tra được

Mã ACN đến từ chatbot Facebook. Nó **không xuất hiện** trong sao kê ngân hàng, và
bảng nhà tài trợ trong hệ thống đang trống. Nên chưa có đường nối ACN → NE. Trang báo
đúng như vậy thay vì trả "không tìm thấy" — hai chuyện khác nhau.

### 5.5 Vì sao số điện thoại bị chặn

Số điện thoại nhà tài trợ chỉ tồn tại trong **nội dung sao kê thô**. Nếu cho tra theo
số điện thoại thì ô tra cứu biến thành công cụ dò dữ liệu cá nhân. Nên hệ thống từ
chối thẳng (`kind: "blocked"`), chứ không trả "không tìm thấy" — để người dùng hiểu
là *không được phép*, không phải *không có*.

---

## 6. Ba hàng đợi — làm gì với từng cái

Đây là phần quan trọng nhất của tài liệu này.

### 6.1 Dòng vào không tìm thấy mã NE — 125.713 dòng

**Câu hỏi thật:** khoản tiền này của ai?

Có ba khả năng, và phải phân biệt được:

| Khả năng | Dấu hiệu | Xử lý |
|---|---|---|
| Nhà tài trợ ghi mã sai / viết tắt | nội dung có chữ "nuoi em", có số giống mã | tìm mã đúng, gán lại |
| Nhà tài trợ không ghi mã | nội dung chỉ có tên người chuyển | liên hệ nếu có thông tin, hoặc chuyển quỹ ẩn danh |
| Tiền không phải của dự án | nội dung khác hẳn | loại khỏi dự án |

**Hệ quả nếu bỏ qua:** theo quy định của Quỹ, tiền không gắn được mã là **không hoàn
lại** và chuyển vào quỹ ẩn danh. Đây là lý do độ phủ được hiển thị chứ không bị giấu.

### 6.2 Mã có tiền nhưng chưa có hồ sơ — 31.051 mã

**Câu hỏi thật:** mã này là em nào?

Việc cần làm là **nhập danh mục học sinh** — một việc làm một lần, không phải 31.051
lần. Sau khi nhập, phần lớn 31.051 mã này sẽ tự khớp và hàng đợi biến mất.

**Hệ quả nếu bỏ qua:** hệ thống biết *có người gửi tiền cho mã NE08784*, nhưng không
biết *em nào*. Mọi câu hỏi kiểu "em X đã nhận đủ chưa" đều không trả lời được.

### 6.3 Dòng ra chưa phân loại kế toán — 2.109 dòng

**Câu hỏi thật:** khoản chi này ứng với đề nghị thanh toán nào của trường nào?

2.109 dòng / 553,1 tỷ — gần như **toàn bộ** tiền ra chưa nối được với chứng từ.

**Hệ quả nếu bỏ qua:** tiền vào truy được một chiều, tiền ra không. Một báo cáo chỉ
truy được một chiều thì chưa chứng minh được gì về việc tiền có tới trường hay không.

---

## 7. Những gì trang này **chưa** làm được

Ghi rõ để không ai tưởng nhầm là đã có:

- **Không ghi, không sửa, không xoá.** Mọi yêu cầu ghi đều bị từ chối với mã 405.
  Đây là lựa chọn có chủ đích: một công cụ chỉ đọc thì không thể làm hỏng dữ liệu.
- **Không có đăng nhập, không phân quyền.** Chạy nội bộ.
- **Không có danh mục học sinh / trường.** Bảng `students`, `schools`, `donors`,
  `student_supports` đang trống.
- **Không gán mã được.** Xem 4.4.
- **Không nối mã ACN với mã NE.** Xem 5.4.
- **Không tra theo tên trường, tên tỉnh, tên người.** Cần danh mục trường trước.
- **Không xuất Excel/CSV.** Muốn gửi danh sách cho người khác thì gửi đường dẫn
  (xem 5.3) hoặc chụp màn hình.

---

## 8. Câu hỏi thường gặp

**"32,52% có phải là đã mất 67,48% số tiền?"**
Không. 32,52% là tỉ lệ tiền vào **truy được về ít nhất một mã**. Phần còn lại vẫn nằm
trong tài khoản, chỉ là chưa biết của em nào. Không có đồng nào biến mất trong phép
tính này — tiền vào và tiền ra đều khớp số Quỹ công bố, lệch 0.

**"Vì sao `NE00001` không có dòng nào mà `NE00001S` lại có?"**
Vì hậu tố S/T là **một phần của mã**, không phải trang trí. `NE00001S` là suất ăn trưa,
`NE00001T` là suất ăn tối, hai mã riêng biệt, hai nhà tài trợ riêng. Nếu gộp chúng lại
thì tổng tiền và số nhà tài trợ đều sai. Trang Tra cứu luôn liệt kê các biến thể ở
riêng một dòng "Biến thể S/T".

**"Bấm vào một dòng tiền mà không có gì xảy ra?"**
Đúng, và có chủ đích — xem 4.3.

**"Số trên trang khác số tôi tự cộng trong Excel?"**
Kiểm tra ba thứ: (1) bạn có đang lọc cùng khoảng thời gian không, (2) bạn có gộp mã
S/T vào mã gốc không, (3) bạn có tính cả giao dịch tiền ra không. Ba lỗi này giải
thích gần hết các trường hợp lệch.

**"Bao lâu phải nạp lại dữ liệu?"**
Mỗi khi Quỹ công bố sao kê mới. Sau khi nạp, xem lại khối "Tình trạng hệ thống" để
chắc là số dòng tăng lên và khoảng dữ liệu đã dài ra.

---

## 9. Khi số liệu trông lạ

Chạy kiểm tra tự động trước khi tin vào bất cứ kết luận nào:

```powershell
python verify_real_data.py
```

Lệnh này kiểm tra 7 nhóm: số dòng, tổng tiền vào/ra so với số Quỹ công bố, độ rộng mã,
chuỗi audit, khả năng phát hiện sửa đổi, hàng đợi ngoại lệ có được gộp không, và các
phần chia có khớp đơn giá công bố không. Kết quả cuối cùng phải là:

```
RESULT: ALL CHECKS PASSED
```

Nếu một mục FAIL, **đừng** dùng số liệu trên trang để báo cáo cho tới khi hiểu vì sao.

Ba dấu hiệu cần dừng lại ngay:

1. Thẻ "Phần chia khớp tổng" hiện **Lệch**.
2. Khối "Tình trạng hệ thống" báo chuỗi audit **đứt**.
3. Số dòng "Đã nạp" **giảm** so với lần trước.

---

## 10. Từ điển nhanh

| Thuật ngữ | Nghĩa |
|---|---|
| **Mã NE** | mã định danh một suất hỗ trợ, dạng `NE` + 5 chữ số, có thể có hậu tố `S`/`T` |
| **Hậu tố S / T** | hai suất ăn trong ngày của cùng một em nội trú. `S` = bữa trưa, `T` = bữa tối (theo cách ghi trong `BAO_CAO_TONG_HOP_DAY_DU.md`; chữ `S` nhiều khả năng viết tắt của "sáng"). Điều chắc chắn: **hai mã khác nhau, hai nhà tài trợ khác nhau** — không được gộp. |
| **Mã ACN** | mã nhà tài trợ, đến từ chatbot Facebook |
| **Phân bổ** | việc chia một giao dịch cho một hay nhiều mã NE |
| **Độ phủ** | tỉ lệ tiền vào gắn được với ít nhất một mã |
| **Ngoại lệ** | một dòng dữ liệu không khớp được với quy tắc nào |
| **Chuỗi audit** | dãy bản ghi nối bằng băm, dùng để phát hiện sửa đổi lịch sử |
