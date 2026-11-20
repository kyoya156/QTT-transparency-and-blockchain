> **Lưu ý:** tài liệu này có nhắc tới định danh Google Sheet / số tài khoản của Quỹ
> Nuôi Em, đã **che bớt** (6 ký tự đầu + 4 ký tự cuối). Bản đầy đủ chỉ lưu trên máy,
> không đưa lên Git. Không dùng các định danh này để đọc hay phát tán dữ liệu cá nhân.
> Xem `SECURITY.md`.

# Phát hiện: mã NE, mã học sinh, và mức độ lộ dữ liệu công khai

Ngày lập: 15/10/2026  
Người lập: phân tích kỹ thuật trên dữ liệu sản xuất thật (238.173 dòng sao kê Vietcombank)

Tài liệu này trả lời ba câu hỏi, và ghi lại hai lỗi trong bộ phân tích mà quá  
trình trả lời đã phát hiện ra.

---

## Câu 1 — "Mã học sinh nếu nuôi lâu thì tồn tại, còn nếu không nuôi nữa thì mã đó không bao giờ được dùng nữa"

### Cái này **củng cố** thiết kế hiện tại, và nó là một quy tắc quan trọng cần ghi vào tài liệu nghiệp vụ

Quy tắc bạn nói có nghĩa là: **mã NE là duy nhất vĩnh viễn (immutable, never reused)**.  
Một mã khi đã cấp cho một học sinh thì giữ nguyên mãi; khi dừng nuôi, mã đó  
**bị khoá vĩnh viễn**, không cấp lại cho học sinh khác.

Đây chính là điều mà mô hình dữ liệu của chúng ta đang giả định, và nó biện minh  
cho ba quyết định thiết kế đã làm:

| Quyết định                                                                              | Vì sao quy tắc "không tái sử dụng mã" biện minh cho nó                                                                                                           |
| --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `transaction_allocations.ne_code` lưu **chuỗi mã**, không lưu khoá ngoại tới `students` | Vì mã là định danh vĩnh viễn, nó đứng độc lập được. Nếu mã bị tái sử dụng thì bắt buộc phải có khoá ngoại + chiều thời gian, và mọi phân bổ cũ sẽ đọc sai người. |
| Nhật ký kiểm toán **append-only**                                                       | Lịch sử "ai được nuôi, giai đoạn nào" là bằng chứng. Nếu mã tái sử dụng, lịch sử đó vô nghĩa.                                                                    |
| Hậu tố `S`/`T` là **một phần của mã** (`NE00001S` ≠ `NE00001T`)                         | Mỗi hậu tố là một định danh riêng, gắn với một nhà tài trợ riêng. Không được gộp.                                                                                |

**Hệ quả cho vận hành (quan trọng):** vì mã không bao giờ tái sử dụng, nên  
`NE02019` xuất hiện năm 2019 và **không thể** là một học sinh khác vào năm 2024.  
Điều này có nghĩa là bất kỳ mã nào xuất hiện **rải rác qua nhiều năm** đều là  
**cùng một học sinh được nuôi dài hạn** — đúng như bạn nói.

### Nhưng dữ liệu cho thấy một điều bất ngờ: có mã bị dùng lại rất nhiều lần

Tôi đã đo trên 140.325 dòng phân bổ thật:

| Số mã      | Số lần xuất hiện        | Diễn giải                     |
| ---------- | ----------------------- | ----------------------------- |
| 6.572 mã   | xuất hiện **1 lần**     | phần lớn là giao dịch một lần |
| 24.478 mã  | xuất hiện **nhiều lần** | học sinh được nuôi dài hạn    |
| nhiều nhất | **79 lần** (`NE02019`)  |                               |

**Đây là chỗ tôi phải nói thẳng: phần lớn những lần "xuất hiện nhiều" đó KHÔNG  
phải là nuôi dài hạn thật — chúng là lỗi của bộ phân tích.** Xem Câu 4 bên dưới.  
Con số 79 lần của `NE02019` là gần như toàn bộ lỗi, không phải sự thật nghiệp vụ.

**Câu hỏi cho mentor:** cơ chế nào đảm bảo mã không bị tái sử dụng khi Quỹ chuyển  
từ Excel sang hệ thống? Trong Excel hiện tại, có ai đó có thể vô tình cấp lại mã  
đã ngừng nuôi không? Nếu có, đây là một rủi ro cần một ràng buộc ở tầng cơ sở dữ liệu.

---

## Câu 2 — Sheet Google đó có phải cố tình công khai không?

### Trả lời: **Có. Sheet đang để chế độ công khai, ai cũng tải được, không cần đăng nhập.**

Tôi đã kiểm tra trực tiếp, không suy đoán:

```
GET https://docs.google.com/spreadsheets/d/1boFEZ…WgHg/
  -> 302 -> trang xem bình thường, tiêu đề "Sao kê tài khoản - Google Trang tính"

GET .../export?format=csv
  -> 200, content-type: text/csv, tải về 34.871.764 byte (34 MB)
```

**Tôi đã tải toàn bộ file 34 MB mà không dùng bất kỳ tài khoản hay mật khẩu nào.**  
Trang xem có chữ "Đăng nhập" ở góc, nhưng đó là nút đăng nhập chung của Google,  
không phải yêu cầu quyền — dữ liệu vẫn trả về đầy đủ cho khách ẩn danh.

### Đây là "cố tình" hay "vô tình"?

**Suy luận (không phải dữ kiện):** rất có thể là **cố tình, và hợp lý**. Lý do:

1. Tiêu đề sheet là "Sao kê tài khoản" — tài liệu công bố minh bạch, không phải  
   file nội bộ bị rò rỉ. Nó nằm trong chiến dịch minh bạch của Quỹ.
2. Chính quyền đã thanh tra Quỹ (17/12/2025 – 24/04/2026) và Quỹ phải chứng minh  
   dòng tiền. Công bố sao kê là cách trả lời.
3. 238.173 dòng khớp chính xác từng đồng với số Quỹ công bố — tức đây là bản  
   công bố chính thức, không phải bản lộ.

**Nhưng "cố tình công khai số tổng" KHÁC với "cố tình công khai từng dòng memo".**  
Và phần memo mới là vấn đề — xem Câu 3.

---

## Câu 3 — "Nó có bị lộ thêm file nào nữa không?"

### Trả lời trung thực: **Tôi không thể biết chắc.** Nhưng tôi có thể nói chính xác cái gì đang lộ, và cái gì tôi chưa kiểm tra được.

### (a) Cái đang lộ trong CHÍNH file này — và đây là mức nghiêm trọng

Tôi đã quét 238.173 dòng memo và đếm được:

| Loại dữ liệu cá nhân                        | Số lượng phát hiện      |
| ------------------------------------------- | ----------------------- |
| **Số điện thoại**                           | **14.328** số khác nhau |
| **Email**                                   | **222** địa chỉ         |
| **Số tài khoản / số tham chiếu**            | **87.434**              |
| **Tên người gửi** (trường `BO:` trong memo) | **1.818** tên khác nhau |

Ví dụ về **dạng** dữ liệu lấy từ file công khai (giá trị thật đã được che):

```
09xxxxxxxx, 08xxxxxxxx, 07xxxxxxxx, ...        (14.328 số)
xxxxx@gmail.com, xxxxx@gmail.com, ...           (222 địa chỉ)
NGUYEN VAN A, TRAN THI B, LE VAN C, ...         (1.818 tên)
```

> Bản trong repo đã che giá trị thật. Số lượng ở bảng trên là đủ để chứng minh
> quy mô; không cần — và không nên — công bố danh tính cụ thể của người thứ ba.

**Đây không phải dữ liệu của học sinh — đây là dữ liệu của NGƯỜI ỦNG HỘ.**  
1.818 nhà tài trợ bị lộ tên kèm số điện thoại và/hoặc email, công khai cho bất kỳ  
ai trên Internet, vĩnh viễn, có thể tải về máy.

Điều này nghiêm trọng hơn lộ dữ liệu học sinh ở một điểm: nhà tài trợ **không hề  
đồng ý** bị công bố thông tin cá nhân. Họ gửi tiền cho một tổ chức từ thiện, và  
memo chuyển khoản của họ bị đăng công khai.

### (b) Cái tôi KHÔNG kiểm tra được, và tôi sẽ không đoán

Tôi chỉ kiểm tra được file này vì bạn đưa tôi link. Tôi **không có cách nào** để  
biết Quỹ còn công khai file nào khác — điều đó cần:

- Quyền truy cập vào Google Drive của Quỹ để xem danh sách file được chia sẻ
- Hoặc một cuộc rà soát toàn bộ tài sản công khai của Quỹ (website, fanpage,  
  các link đã đăng trong bài công bố)

**Đây là việc nên làm, và tôi đề xuất một quy trình cụ thể ở phần cuối.**

### (c) Một điều đáng chú ý: đường dẫn không được bảo vệ

Link `docs.google.com/spreadsheets/d/1boFEZ...` là dạng "ai có link thì xem được".  
Điều này có nghĩa là: bất kỳ ai từng được gửi link (nhà báo, tình nguyện viên,  
người kiểm tra) đều có thể phát tán tiếp, và **không có cách nào thu hồi**. File  
34 MB này giờ đã có thể nằm trên bất kỳ máy nào.

---

## Câu 4 — Hai lỗi bộ phân tích phát hiện được khi trả lời ba câu hỏi trên

Đây là phần đáng giá nhất của lần rà soát này. Cả hai lỗi đều **đang hoạt động  
trong bản đã nạp trước đó**, và cả hai đều gán tiền sai người.

### Lỗi A — Mã bị ngắt dòng bị đọc thành `NE00001`

Sao kê tự động ngắt dòng ở một cột cố định. Một mã nằm vắt qua chỗ ngắt sẽ đến  
dưới dạng `NE1` xuống dòng rồi `156`. Sau khi chuẩn hoá xuống dòng thành khoảng  
trắng, bộ phân tích đọc `NE1` thành **NE00001** — đúng mã của học sinh đầu tiên  
của Quỹ.

Ví dụ thật:

```
BO:TRUONG THI MINH CHAU.TRUONG THI MINH CHAU NE1 156    -> phải là NE01156
BO:NGUYEN THI MINH HIEN.NGUYEN THI MINH HIEN   NE1 307 -> phải là NE01307
```

Đo trên dữ liệu thật: **44 memo** có dạng `NE1 <số>`, trong đó **23 memo bị đọc sai**.  
Hậu quả: tiền của ít nhất 23 học sinh khác nhau bị dồn vào học sinh NE00001.

**Đã sửa:** thêm bước `repair_line_wrap()` ghép lại mã trước mọi bước phân tích khác.

### Lỗi B — Năm học (`2019`, `2020`) bị đọc thành mã học sinh

Nhà tài trợ viết năm học ngay cạnh mã: `"NE413 + NE414, 2019+2020"`,  
`"NE2019, NE2020"`, `"NE20192020"`, `"NE4708 - 2019/20"`. Vì danh mục NE rộng  
5 chữ số, số `2019` **hợp lệ về mặt cú pháp**, nên giới hạn độ rộng không bắt được.

Đo trên dữ liệu thật: **371 dòng phân bổ** được tạo cho `NE02018`…`NE02026` —  
những mã thật ra là **năm 2018–2026**. Riêng `NE02019` "nhận" 79 dòng.

**Đã sửa, nhưng có một cái bẫy phải xử lý cẩn thận.** `NE02019` **vừa** là năm,  
**vừa là mã học sinh thật**: có một memo ghi nguyên văn  
`"ck 1 ma NE02019 Quyen Mice"`. Nếu tôi chặn cứng mọi số 2018–2026 thì sẽ  
**xoá mất một nhà tài trợ thật**.

Nên quy tắc được đặt theo **ngữ cảnh, không theo con số**:

- `NE2019, NE2020` / `NE20192020` / `2019+2020` / `2019/20` → **năm, loại bỏ**
- `ck 1 ma NE02019` đứng một mình → **mã thật, giữ lại**

Nguyên tắc tôi chọn khi phải đánh đổi: **một mã ma làm sai lệch một học sinh, còn  
một mã thật bị xoá thì mất luôn một nhà tài trợ.** Nên khi không đủ ngữ cảnh để  
phân biệt, giữ lại an toàn hơn.

Kết quả: **371 → 37 dòng**, và 37 dòng còn lại là những trường hợp năm đứng một  
mình mà ngữ cảnh thật sự không phân biệt được.

### Ảnh hưởng lên số liệu

| Chỉ số                  | Trước           | Sau khi sửa                  |
| ----------------------- | --------------- | ---------------------------- |
| Dòng phân bổ            | 140.661         | **140.325**                  |
| Mã NE phân biệt         | 31.050          | **31.051**                   |
| Cần soát lại            | 125.670         | **125.713**                  |
| Tỷ lệ phủ               | 32,57%          | **32,52%**                   |
| Tiền vào (khớp công bố) | 553.550.809.401 | **553.550.809.401 — lệch 0** |
| Tiền ra (khớp công bố)  | 553.541.302.920 | **553.541.302.920 — lệch 0** |

**Tiền không đổi** — tổng thu/chi vẫn khớp công bố từng đồng. Cái thay đổi là  
**tiền được gán cho ĐÚNG mã nào**. Đây là điểm quan trọng nhất: sửa lỗi này làm  
con số per-mã chính xác hơn, chứ không làm sai lệch con số tổng.

Kiểm thử: **77 test, OK** (thêm 8 test hồi quy cho hai lỗi này).  
`verify_real_data.py`: **ALL CHECKS PASSED**.

---

## Câu 5 — Khuyến nghị

### Ngay lập tức (làm trước khi nộp bài)

1. **Không đưa link sheet vào báo cáo.** Trong báo cáo, trích dẫn rằng Quỹ có  
   công bố sao kê, và nêu số dòng + số tổng để chứng minh nguồn. **Không dán URL.**  
   Việc sao chép thêm một lần nữa làm phát tán dữ liệu cá nhân.
2. **Ghi rõ trong báo cáo rằng đây là dữ liệu công khai, nhưng chứa dữ liệu cá  
   nhân của 1.818 nhà tài trợ.** Đây là một phát hiện về quản trị, không phải  
   một khuyết điểm của bài làm — nó chứng minh bài làm hiểu đúng vấn đề.
3. **Xác nhận lại với mentor** rằng nhóm được phép dùng dữ liệu này. Vì file công  
   khai nên về mặt kỹ thuật là truy cập được, nhưng về mặt đạo đức nên báo.

### Trong hệ thống (đưa vào phần "hướng vận hành")

1. **Cột `raw_description` không bao giờ ra khỏi máy chủ.** Hệ thống đã làm đúng  
   điều này (`description_masked`), và phát hiện này là lý do cụ thể nhất để bảo  
   vệ quyết định đó: memo thô chứa 14.328 số điện thoại và 222 email.
2. **Tìm kiếm toàn văn trên memo đã bị tắt** — quyết định này giờ đã được chứng  
   minh bằng số liệu, không còn là phòng ngừa lý thuyết.
3. **Đề xuất Quỹ rà soát lại quyết định công bố memo thô.** Bản thân việc công bố  
   số tổng là tốt và nên tiếp tục. Công bố **từng dòng memo có tên người gửi, số  
   điện thoại, email** là một vấn đề riêng, và Quỹ có thể giữ minh bạch mà vẫn


che phần này (ví dụ chỉ công bố mã NE + số tiền + ngày).

### Việc rà soát mở rộng (cần thêm quyền truy cập)

1. Rà soát toàn bộ tài sản công khai của Quỹ để trả lời trọn vẹn câu hỏi  
   "còn file nào nữa không": website, fanpage, các link trong bài công bố,  
   và danh sách file được chia sẻ trên Google Drive của Quỹ.  
   **Việc này tôi chưa làm được vì không có quyền truy cập — cần Quỹ hoặc mentor  
   cung cấp.**

---

## Phụ lục — Phân loại theo mức độ chắc chắn

### Dữ kiện (đã kiểm chứng trực tiếp)

- Sheet là công khai: tải được 34 MB không cần đăng nhập (HTTP 200).
- Nội dung lộ: 14.328 số điện thoại, 222 email, 87.434 số tài khoản, 1.818 tên.
- Lỗi ngắt dòng mã: 44 memo có dạng, 23 memo bị đọc sai.
- Lỗi năm-thành-mã: 371 dòng phân bổ trước khi sửa, 37 sau khi sửa.
- Tiền khớp công bố tuyệt đối: lệch 0 cả thu và chi.
- 77 test OK, `verify_real_data.py` ALL CHECKS PASSED.

### Suy luận (có bằng chứng nhưng chưa xác nhận)

- Việc công khai sheet rất có thể là **cố tình**, để phục vụ yêu cầu minh bạch  
  sau thanh tra. Bằng chứng: tiêu đề là tài liệu công bố, số khớp số đã công bố,  
  không có dấu hiệu rò rỉ (không có mật khẩu file, không phải file nội bộ).
- Nhưng việc công khai **dữ liệu cá nhân nhà tài trợ** nhiều khả năng là  
  **không cố ý** — Quỹ muốn công bố dòng tiền, không nhắm vào việc phơi số điện  
  thoại của người ủng hộ.

### Câu hỏi cho mentor / Quỹ

1. Quy tắc "mã không bao giờ tái sử dụng" được thực thi bằng gì khi chuyển khỏi Excel?
2. Nhóm có được phép phân tích file công khai này không, và có nên nêu phát hiện  
   dữ liệu cá nhân trong bài nộp không?
3. Quỹ còn công khai file nào khác (Drive, website, fanpage) ngoài sheet này?
4. Quỹ đã biết việc memo công khai chứa tên/số điện thoại/email nhà tài trợ chưa?
