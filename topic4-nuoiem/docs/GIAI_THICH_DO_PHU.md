# Giải thích tỷ lệ phủ 32,52% — tiền vào được tính như thế nào?

> Tài liệu nội bộ. Trả lời câu hỏi: *"Tiền vào khá lớn nếu chỉ so cho 1 mã. Vậy đang tính như thế nào? Có phải lấy tổng tiền vào chia đều cho các mã NE không?"*
>
> Trả lời ngắn: **Không.** Không có phép chia nào giữa tổng tiền và số mã.

---

## 1. Câu trả lời ngắn

Tỷ lệ phủ được tính **theo từng giao dịch**, không theo mã NE.

```
Với mỗi giao dịch tiền vào:
    memo có ít nhất 1 mã NE?
        CÓ   → cộng TOÀN BỘ số tiền giao dịch đó vào "đã gắn mã"
        KHÔNG → cộng toàn bộ số tiền vào "chưa gắn mã"

tỷ lệ phủ = tổng tiền của nhóm "CÓ" / tổng tiền toàn bộ tiền vào
```

Không chia cho 31.051. Không chia cho số tháng. Không chia cho số học sinh.
Một giao dịch được đếm **đúng một lần**, với **nguyên số tiền** ghi trên sao kê.

---

## 2. Số thật (Vietcombank, 08/02/2018 → 25/02/2026)

| Nhóm | Số giao dịch | Tổng tiền | Tỷ trọng |
|---|---:|---:|---:|
| Có ít nhất 1 mã NE | 110.317 | 179.995.872.597 đ | **32,52%** |
| Không có mã nào | 125.713 | 373.554.936.804 đ | **67,48%** |
| **Tổng tiền vào** | **236.030** | **553.550.809.401 đ** | 100% |

Phép tính: `179.995.872.597 / 553.550.809.401 = 32,52%`

Kiểm chứng bất biến: tổng các dòng phân bổ của nhóm "có mã" =
**179.995.872.597 đ**, chênh lệch **0 đ** so với tổng tiền giao dịch của nhóm đó.
Tức là tiền không bị mất hay bị nhân đôi khi tách thành nhiều mã.

---

## 3. Ba thứ rất dễ lẫn nhau

Đây là nguồn gốc của sự khó hiểu. Hệ thống có **ba con số khác nhau**, phục vụ ba mục đích khác nhau:

| Con số | Đơn vị đếm | Dùng để làm gì | Có chia đều không? |
|---|---|---|---|
| **Tỷ lệ phủ 32,52%** | giao dịch | đo mức độ minh bạch của dòng tiền | **Không** |
| **140.325 dòng phân bổ** | (giao dịch × mã) | biết từng đồng thuộc em nào | **Có**, khi 1 giao dịch có nhiều mã |
| **31.051 mã NE** | mã | đếm số em được nhận tiền | Không liên quan |

Chỉ có **dòng phân bổ** mới chia tiền. Và nó chia **bên trong một giao dịch**, không chia toàn bộ tổng tiền vào.

Ví dụ thật — giao dịch ngày 05/01/2024, 47.500.000 đ, memo có 10 mã:

```
47.500.000 đ
   ├─ NE... 4.750.000 đ
   ├─ NE... 4.750.000 đ
   ├─ ...             (10 dòng, mỗi dòng bằng nhau)
   └─ NE... 4.750.000 đ
   ─────────────────────
   tổng = 47.500.000 đ   ← luôn khớp lại đúng số tiền gốc
```

Chính sách ghi trong DB: `equal_split`. Nếu chia có dư, phần dư dồn vào mã đầu
(`equal_split_with_remainder`) để **tổng không bao giờ lệch**.

---

## 4. Vì sao "1 mã" có thể là số tiền rất lớn — bạn nhận xét đúng

Vì **mã NE xác định em nào, không xác định bao nhiêu tháng**.

Nhà tài trợ có thể chuyển trước nhiều năm cho cùng một em, và memo chỉ ghi một mã.

| Giao dịch | Số tiền | Mã | Quy ra tháng (đơn giá 1.450.000 đ) |
|---|---:|---|---:|
| NE00298 | 1.450.000 đ | 1 mã | **1 tháng** |
| NE15294 | 145.000.000 đ | 1 mã | **100 tháng** |
| NE15693 | 163.850.000 đ | 1 mã | **113 tháng** |

Nên "1 giao dịch · 1 mã" **không** đồng nghĩa "1 em · 1 tháng". Nếu lấy
`553.550.809.401 / 31.051` sẽ ra **17.827.149 đ/mã** — con số này **không được
dùng ở bất kỳ đâu** trong hệ thống, vì nó giả định mọi em nhận tiền như nhau,
trong khi thực tế có em nhận 1 tháng và có em nhận trả trước 100 tháng.

### Phân bố thật của các giao dịch "chỉ 1 mã" (92.240 giao dịch)

| Số tiền | Số giao dịch | Ghi chú |
|---|---:|---|
| 1.450.000 đ | **40.003** | đúng 1 tháng — 43,4% |
| 150.000 đ | 4.673 | tiền ăn lẻ |
| 450.000 đ | 4.635 | |
| 500.000 đ | 4.606 | |
| 484.000 đ | 4.113 | |
| 2.900.000 đ | 4.095 | 2 tháng |
| 725.000 đ | 2.835 | nửa tháng |

→ Đa số là 1 tháng, nhưng **đuôi phân bố rất dài**: vẫn có giao dịch 145 triệu,
163 triệu cho đúng một mã. Đó là lý do không thể suy ra "mỗi mã bao nhiêu tiền".

---

## 5. Một phát hiện quan trọng đi kèm

Nhóm **không gắn được mã** có số tiền trung bình **lớn hơn** nhóm gắn được mã:

| Nhóm | Trung bình mỗi giao dịch |
|---|---:|
| Có mã | **1.631.624 đ** |
| Không mã | **2.971.490 đ** |

Nghĩa là phần chưa minh bạch **không phải tiền lẻ vụn** — nó là những khoản lớn.
Đây là lập luận mạnh cho việc cần danh mục học sinh: 67,48% tiền chưa gắn mã
đang nằm ở các giao dịch có giá trị cao hơn mức trung bình.

---

## 6. Nếu bị hỏi, trả lời trong ba câu

1. *"Tỷ lệ phủ tính theo giao dịch: giao dịch nào có ít nhất một mã NE thì toàn bộ số tiền của nó được tính là đã gắn mã."*
2. *"Không chia tổng tiền cho số mã, vì một mã có thể là 1 tháng hoặc 100 tháng — chia đều sẽ sai."*
3. *"Chỉ khi một giao dịch chứa nhiều mã thì mới chia tiền, và tổng sau khi chia luôn khớp lại đúng số tiền gốc — chênh lệch 0 đồng."*

---

## Phụ lục — phân loại

**Dữ kiện (đo từ DB):** mọi con số ở mục 2, 4, 5. Bất biến tổng phân bổ = tổng tiền giao dịch, lệch 0 đ trên toàn bộ 110.317 giao dịch có mã.

**Suy luận:** việc quy đổi "số tháng" dùng đơn giá 1.450.000 đ/tháng — đây là mức phổ biến nhất (43,4% giao dịch một mã), nhưng bảng giá Quỹ có nhiều mức (1.360.000 / 1.450.000 / 1.496.000 / 1.650.000 và tiền ăn 150.000 / 170.000). Số tháng nêu trên là **ước lượng để minh hoạ độ lớn**, không phải số tháng thực của từng em.

**Chưa kiểm chứng:** chưa đối chiếu được với danh mục học sinh (không có dữ liệu), nên chưa biết mỗi mã thực sự đã nhận bao nhiêu tháng.
