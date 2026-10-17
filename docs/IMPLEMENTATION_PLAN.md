# Kế hoạch tiếp theo cho Topic 4

## 1. Kết luận từ dữ liệu mẫu

File mẫu chứa ba khối dữ liệu trên cùng một worksheet:

1. Hồ sơ học sinh và quan hệ với ACN, trường, điểm trường.
2. Giao dịch chuyển khoản sau khi xử lý và ghép mã.
3. Sao kê trước xử lý cùng kết quả phân loại.

Dữ liệu đủ để làm MVP đối soát tiền vào. Dữ liệu chưa đủ để làm luồng tiền ra, phê duyệt đề nghị chi, chứng từ trường và đóng kỳ tài chính.

## 2. Mô hình dữ liệu dùng cho MVP

```text
BankTransaction ──< TransactionAllocation >── Donor/ACN
                                              │
                                              │
StudentSupport >── Student ──> School
```

`TransactionAllocation` là bảng trung gian bắt buộc vì một giao dịch có thể xuất hiện nhiều dòng để gắn nhiều mã NE. Số tiền chỉ được lưu một lần ở `BankTransaction`, tránh cộng trùng khi tổng hợp.

Trong bộ mẫu, các mã ACN của giao dịch không trùng với các mã ACN của hồ sơ học sinh. Vì vậy chưa thể nối chắc chắn `BankTransaction → ACN → Student → School` bằng một trường hợp thực tế hoàn chỉnh.

## 3. MVP đã xây

- Database SQLite đã chuẩn hóa và có khóa ngoại.
- Import ba khối dữ liệu từ Excel.
- Loại bỏ tên, email, số điện thoại, phụ huynh, giáo viên và liên kết ảnh khỏi database MVP.
- Dashboard tổng quan.
- Tìm kiếm giao dịch theo mã giao dịch, ACN và NE.
- Danh sách quan hệ ACN, học sinh và trường.
- Màn hình truy vết quan hệ.
- Danh sách vấn đề chất lượng dữ liệu.
- Chống cộng trùng số tiền do một giao dịch lặp trên nhiều dòng NE.
- API chỉ đọc, truy vấn có tham số và giới hạn số bản ghi.

## 4. Việc cần xác nhận với mentor

1. Cột `Mã học sinh chính` có phải là định danh học sinh bền vững qua nhiều năm không?
2. `Mã NE trên ảnh` là mã học sinh hay mã suất tài trợ?
3. Một giao dịch tài trợ nhiều mã NE thì số tiền phân bổ cho từng mã được lưu ở đâu?
4. Một mã ACN có thể thanh toán bằng nhiều giao dịch không?
5. Khi một mã ACN được phân bổ lại cho học sinh khác, hệ thống có giữ lịch sử không?
6. Ngày trong file dùng `dd/mm`, `mm/dd` hay ký hiệu tháng/năm học?
7. Đơn giá `170` có nghĩa là 170 đồng hay 170.000 đồng?
8. Cần thêm một mẫu có cùng mã ACN ở bảng giao dịch và bảng học sinh để kiểm chứng quan hệ end-to-end.

## 5. Roadmap đề xuất

### Giai đoạn A — Xác nhận dữ liệu và nghiệp vụ

- Chốt data dictionary và ý nghĩa từng mã.
- Chốt cardinality ACN, giao dịch, NE, học sinh và trường.
- Nhận một trường hợp hoàn chỉnh từ tiền vào đến học sinh.
- Chốt quy tắc phân loại giao dịch và xử lý ngoại lệ.

### Giai đoạn B — Hoàn thiện tiền vào

- Nhận webhook Casso vào bảng raw bất biến.
- Xác minh chữ ký webhook và chống replay.
- Parser mã ACN/NE có version.
- Hàng đợi ngoại lệ và maker-checker khi chỉnh kết quả ghép.
- Đối chiếu định kỳ với sao kê ngân hàng chính thức.

### Giai đoạn C — Bổ sung tiền ra

- Payment Request từ trường.
- Quy trình phê duyệt hai bước.
- Gắn giao dịch tiền ra với đề nghị thanh toán.
- Quản lý chứng từ và phiên bản chứng từ.
- Theo dõi thiếu, từ chối và nộp lại chứng từ.

### Giai đoạn D — Báo cáo và hiệu năng

- Đóng kỳ và report snapshot có version.
- Public read model đã loại dữ liệu cá nhân.
- Sinh một triệu giao dịch giả để kiểm thử.
- Index, phân trang theo khóa và kiểm thử SLO tìm kiếm.

### Giai đoạn E — Đánh giá bảo mật

- RBAC và phạm vi dữ liệu theo vai trò.
- Maker-checker cho thao tác tài chính.
- Audit log bất biến ở mức ứng dụng.
- Kiểm thử IDOR, injection, upload chứng từ và lộ PII.
- Backup, restore drill và kiểm tra tính toàn vẹn báo cáo.

## 6. Tiêu chí hoàn thành phiên bản tiếp theo

- Một giao dịch được nhập lặp không làm tăng tổng tiền.
- Có thể truy vết một giao dịch đến ACN và kết quả phân bổ.
- Không có API công khai trả tên hoặc thông tin liên lạc của trẻ em.
- Mọi chỉnh sửa kết quả ghép đều có người thực hiện, người duyệt và lý do.
- Tổng tiền vào trên hệ thống khớp sao kê theo kỳ đã chọn.
- Tìm kiếm một triệu giao dịch đạt SLO được mentor thống nhất.
