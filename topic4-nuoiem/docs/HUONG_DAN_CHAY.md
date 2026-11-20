# Hướng dẫn chạy — dành cho người vừa clone repo

Viết cho thành viên nhóm lấy mã nguồn từ GitHub về và chưa từng chạy dự án Python.
Làm đúng thứ tự dưới đây là được, không cần đọc phần nào khác.

Thời gian: khoảng 10 phút, phần lớn là chờ tải dữ liệu.

---

## 0. Cần có trước

| Thứ | Kiểm tra bằng | Ghi chú |
|---|---|---|
| Python 3.11 trở lên | `py --version` hoặc `python --version` | Nếu chưa có: tải ở python.org, **tick ô "Add python.exe to PATH"** khi cài |
| Git | `git --version` | Nếu chưa có: git-scm.com |
| File dữ liệu | — | **Không có trên GitHub.** Xem bước 3 |

**Không cần `pip install` gì cả.** Ứng dụng chỉ dùng thư viện chuẩn của Python.
Chỉ cài thêm nếu sau này cần nhập file Excel `.xlsx`.

---

## 1. Clone repo

Mở PowerShell, chọn một thư mục bất kỳ (ví dụ `D:\doan`), rồi:

```powershell
git clone https://github.com/tuankhongbietcode/nuoiem-topic4-minh-bach-tai-chinh.git
cd nuoiem-topic4-minh-bach-tai-chinh
```

---

## 2. Tạo thư mục dữ liệu

Git **không giữ thư mục rỗng**, nên sau khi clone sẽ không có thư mục `data`.
Phải tự tạo:

```powershell
mkdir data
```

---

## 3. Lấy dữ liệu — bước quan trọng nhất

File dữ liệu **cố ý không nằm trên Git**. Sao kê ngân hàng chứa tên, số điện
thoại và email của nhà tài trợ; đưa lên GitHub công khai là vi phạm quyền riêng
tư, và repo này công khai.

Nên người phụ trách nhóm phải gửi riêng cho bạn **một trong hai** file sau.

### Cách A — nhận sẵn database (nhanh nhất, nên dùng)

Nhận file `nuoi_em_mvp.sqlite` (~180 MB) qua Google Drive / USB, đặt vào:

```
nuoiem-topic4-minh-bach-tai-chinh/data/nuoi_em_mvp.sqlite
```

Xong. Không cần dựng lại gì. Sang bước 4.

### Cách B — nhận sao kê gốc rồi tự dựng (chậm hơn, nhưng tự kiểm chứng được)

Nhận file `real_vcb.csv` (~34 MB), đặt vào `data/real_vcb.csv`, rồi:

```powershell
python build_database.py data/real_vcb.csv
```

Quá trình này đọc 238.173 dòng, mất vài phút. Chạy xong sẽ có
`data/nuoi_em_mvp.sqlite`.

Cách này tốt hơn về mặt kiểm chứng: bạn tự dựng từ nguồn gốc, không phải tin
file có sẵn. Nhưng nếu chỉ cần xem giao diện thì dùng cách A.

---

## 4. Chạy

```powershell
python app.py --open
```

`--open` tự mở trình duyệt. Nếu không muốn tự mở:

```powershell
python app.py
```

Hoặc dùng script có sẵn (tự tìm Python, đổi cổng được):

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
powershell -ExecutionPolicy Bypass -File .\run.ps1 -Port 8792
```

Khi chạy đúng, terminal in ra **ba dòng** như thế này:

```
Database: ...\data\nuoi_em_mvp.sqlite
  238,173 giao dịch · 2018-02-08 00:00:00 → 2026-02-25 00:00:00
Topic 4 MVP running at http://127.0.0.1:8765
```

Nếu dòng đầu báo `Không tìm thấy database` thì quay lại bước 3.

Dừng server: bấm `Ctrl+C` trong cửa sổ PowerShell.

---

## 5. Mở trên trình duyệt

| Địa chỉ | Là gì |
|---|---|
| http://127.0.0.1:8765/ | Trang công khai — "quỹ đã nhận và chi bao nhiêu" |
| http://127.0.0.1:8765/admin | Trang quản trị — "hôm nay phải làm gì" |

Hướng dẫn dùng trang quản trị: `docs/HUONG_DAN_QUAN_TRI.md`.

---

## 6. Kiểm tra đã chạy đúng dữ liệu

Đừng chỉ nhìn giao diện. Ba con số này phải khớp, nếu lệch là dữ liệu khác:

| Chỗ xem | Phải thấy |
|---|---|
| Dòng thứ hai ở terminal | `238,173 giao dịch` |
| Trang `/`, tổng tiền vào | `553.550.809.401 đ` |
| Trang `/admin`, độ phủ | `32,52%` |

Muốn kiểm tra sâu hơn (khoảng 30 giây):

```powershell
python verify_real_data.py
```

Dòng cuối phải là `RESULT: ALL CHECKS PASSED`.

---

## 7. Chạy bộ kiểm thử (tuỳ chọn)

```powershell
python -m unittest discover -s tests
```

Phải ra `OK` với 90 bài. Bộ test dựng database mẫu riêng trong bộ nhớ, **không**
đụng vào `data/`, nên chạy được cả khi chưa có dữ liệu thật.

---

## 8. Lỗi hay gặp

| Hiện tượng | Nguyên nhân | Cách sửa |
|---|---|---|
| Gõ `python` thì **Microsoft Store mở ra** | Windows chỉ có "App execution alias", không có Python thật | Cài Python từ python.org, tick "Add python.exe to PATH". Tạm thời dùng `py app.py` |
| `Không tìm thấy database` | Chưa có file trong `data/` | Bước 3 |
| Trang mở được nhưng số trống, API trả `database_error` | Bản app cũ chưa có kiểm tra đầu vào, hoặc trỏ sai file | Chạy lại, đọc dòng `Database:` ở terminal |
| `run.ps1 cannot be loaded because running scripts is disabled` | Chính sách PowerShell | Dùng đúng lệnh: `powershell -ExecutionPolicy Bypass -File .\run.ps1` |
| `OSError: [WinError 10048]` | Cổng 8765 đang bị chiếm | `python app.py --port 8792` |
| Chữ Việt trong terminal thành ô vuông | Codepage console | `chcp 65001` rồi chạy lại |
| `ModuleNotFoundError: openpyxl` | Chỉ xảy ra khi nhập file `.xlsx` | `pip install -r requirements.txt` |
| `git: command not found` | Chưa cài Git | git-scm.com, cài xong mở lại PowerShell |

---

## 9. macOS / Linux

Không cần đổi gì trong code, chỉ đổi tên lệnh:

```bash
git clone https://github.com/tuankhongbietcode/nuoiem-topic4-minh-bach-tai-chinh.git
cd nuoiem-topic4-minh-bach-tai-chinh
mkdir data
# chép nuoi_em_mvp.sqlite vào data/
python3 app.py --open
```

Không dùng được `run.ps1` (là script PowerShell). Dùng thẳng `python3 app.py`.

---

## 10. Ba điều không được làm

**Không commit thư mục `data/`.** `.gitignore` đã chặn `*.sqlite` và `*.csv`,
nhưng đừng dùng `git add -f` để lách. Đẩy sao kê lên GitHub công khai là sự cố
dữ liệu cá nhân, không phải lỗi kỹ thuật nhỏ.

**Không đổi `--host` thành `0.0.0.0`.** Ứng dụng chỉ lắng nghe trên
`127.0.0.1` — tức chỉ máy bạn truy cập được. Mở ra mạng LAN hay Internet nghĩa
là ai trong quán cà phê cũng đọc được dữ liệu nhà tài trợ.

**Không gửi link cho người ngoài nhóm.** Không có đăng nhập. Ai mở được link là
đọc được toàn bộ.

---

## Tóm tắt một khối, copy là chạy

```powershell
git clone https://github.com/tuankhongbietcode/nuoiem-topic4-minh-bach-tai-chinh.git
cd nuoiem-topic4-minh-bach-tai-chinh
mkdir data
# >>> chép nuoi_em_mvp.sqlite vào data\ <<<
python app.py --open
```

Rồi mở http://127.0.0.1:8765/admin
