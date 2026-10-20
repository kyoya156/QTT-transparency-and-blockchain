# ERD & Luồng lỗi — Nuôi Em (Topic 4)

Tài liệu nội bộ. Nguồn: `PRAGMA foreign_key_list` trên `data/nuoi_em_mvp.sqlite`  
và code `build_database.py` / `reconciliation.py` / `parsers.py`.

## 1. ERD — quan hệ bảng

![Sơ đồ ERD — 12 thực thể, 11 khóa ngoại](assets/erd.png)

### Khóa ngoại thật (11)

| Bảng con                | Cột                | → Bảng cha              | Cột |
| ----------------------- | ------------------ | ----------------------- | --- |
| students                | school_id          | schools                 | id  |
| student_supports        | student_id         | students                | id  |
| student_supports        | donor_id           | donors                  | id  |
| transaction_allocations | transaction_id     | bank_transactions       | id  |
| transaction_allocations | donor_id           | donors                  | id  |
| transaction_allocations | student_id         | students                | id  |
| transaction_allocations | school_id          | schools                 | id  |
| school_payment_requests | school_id          | schools                 | id  |
| disbursements           | payment_request_id | school_payment_requests | id  |
| disbursements           | transaction_id     | bank_transactions       | id  |
| evidence_documents      | payment_request_id | school_payment_requests | id  |

### Bảng độc lập (không khóa ngoại)

`approval_tasks`, `audit_events`, `exception_queue`, `import_runs`,  
`report_periods`, `roles`, `data_quality_issues`.

## 2. Luồng lỗi — mỗi gate hỏng rẽ nhánh nào

![Luồng lỗi — một giao dịch đi qua 5 gate](assets/luong_loi.png)

| Gate | Điều kiện đạt                       | Khi hỏng → trạng thái / ngoại lệ                                        | Mức      |
| ---- | ----------------------------------- | ----------------------------------------------------------------------- | -------- |
| 1    | Có mã NE/ACN trong memo             | `needs_review` (inbound có memo, không mã) / `unclassified` (memo rỗng) | —        |
| 2    | `sum(allocated) == amount`          | `ALLOCATION_SUM_MISMATCH`                                               | **high** |
| 3    | Mã NE có trong danh mục học sinh    | `NE_CODE_NOT_IN_REGISTRY` + `match_status=ambiguous`                    | **high** |
| 4    | Không lặp mã NE trên cùng giao dịch | `DUPLICATE_NE_ON_TRANSACTION` (tiền đã gộp, không cộng trùng)           | low      |
| 5    | Inbound có mã                       | `INBOUND_WITHOUT_CODE` (chuyển quỹ vô danh, cần hạch toán riêng)        | medium   |

Ngoài ra: `UNCLASSIFIED_INBOUND` (medium) khi memo rỗng hoàn toàn.

### Nguyên tắc

- Ngoại lệ được **gom 1 dòng/loại** kèm count + tổng giá trị rủi ro — không phải 1 dòng/lỗi.
- Gate 2 và 3 là **chặn công bố** (high): không được báo cáo khi còn lỗi này.
- Gate 4 và 5 là **nhắc chuẩn hoá** (low/medium): tiền vẫn đúng, chỉ cần người xử lý.

## 3. Ghi chú

- `transaction_allocations.ne_code` là **chuỗi**, không FK tới `students`, vì mã NE    
  là vĩnh viễn và không tái sử dụng — FK sẽ âm thầm trỏ lại sai nếu mã bị cấp lại.
- `audit_events` append-only (trigger chặn UPDATE/DELETE) + chuỗi hash    
  `sha256(prev_hash|event|entity|actor|body)`.
- `approval_tasks` là maker-checker: `maker != checker`, nếu trùng → `PermissionError`.

## Phụ lục — mã mermaid (import vào draw.io)

```mermaid
erDiagram
  schools {
    int id PK
    text school_code UK
    text name
    text province
  }
  students {
    int id PK
    text student_code UK
    int school_id FK
    text class_name
  }
  donors {
    int id PK
    text acn_code UK
  }
  student_supports {
    int id PK
    int student_id FK
    int donor_id FK
    text ne_code
    text academic_year
    int total_amount
  }
  bank_transactions {
    int id PK
    text provider_tx_id UK
    text idempotency_key UK
    text tx_time
    text direction
    int amount
    text processing_status
  }
  transaction_allocations {
    int id PK
    int transaction_id FK
    text ne_code
    int donor_id FK
    int student_id FK
    int school_id FK
    int allocated_amount_computed
    text match_status
  }
  school_payment_requests {
    int id PK
    text request_code UK
    int school_id FK
    int requested_amount
    text status
  }
  disbursements {
    int id PK
    int payment_request_id FK
    int transaction_id FK
    int amount
  }
  evidence_documents {
    int id PK
    int payment_request_id FK
    text document_type
    text external_url
  }
  approval_tasks {
    int id PK
    text entity_type
    text action
    text maker
    text checker
    text status
  }
  audit_events {
    int id PK
    text event_type
    text actor
    text prev_hash
    text event_hash
  }
  exception_queue {
    int id PK
    text exception_code
    text severity
    text status
  }
  schools ||--o{ students : "1-n"
  schools ||--o{ transaction_allocations : "1-n"
  schools ||--o{ school_payment_requests : "1-n"
  students ||--o{ student_supports : "1-n"
  students ||--o{ transaction_allocations : "1-n"
  donors ||--o{ student_supports : "1-n"
  donors ||--o{ transaction_allocations : "1-n"
  bank_transactions ||--o{ transaction_allocations : "1-n"
  bank_transactions ||--o{ disbursements : "1-n"
  school_payment_requests ||--o{ disbursements : "1-n"
  school_payment_requests ||--o{ evidence_documents : "1-n"
```
