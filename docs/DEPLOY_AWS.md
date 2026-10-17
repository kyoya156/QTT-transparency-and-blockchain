# Deploy lên AWS — cần gì, tốn bao nhiêu, đổi những gì

Ngày: 17/10/2026
Trạng thái hiện tại: chạy trên sandbox tạm, không phải hạ tầng của bạn.

---

## 1. Tin tốt trước

App này **dễ deploy hơn hầu hết ứng dụng web** vì ba lý do:

- **0 thư viện bên thứ ba.** Chỉ cần Python 3.11+ là chạy. Không `pip install`, không
  build step, không node_modules.
- **Không có ghi.** Database mở `mode=ro`, mọi POST/PUT/DELETE trả 405. Nghĩa là
  không có transaction, không có lock, không có nguy cơ hỏng dữ liệu do người dùng.
- **Đã tự set security header.** CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.

Điểm thứ ba đáng nói: app này **có** header bảo mật, trong khi web thật của Quỹ thì
không. Đó là chi tiết nhỏ nhưng đáng nhắc khi bảo vệ.

---

## 2. Ba việc phải làm trước khi mở ra Internet

### 2.1 TLS — app không tự làm được

`ThreadingHTTPServer` chỉ nói HTTP. Không nên (và không cần) nhét TLS vào Python.
Cách chuẩn: **để một reverse proxy đứng trước** lo TLS rồi chuyển tiếp vào app.

Nếu dùng EC2/Lightsail thì nginx + Let's Encrypt. Nếu dùng ALB thì gắn ACM cert.

Sau khi có TLS mới thêm được header này (thêm ở proxy, không phải trong code):

```
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

Lý do phải thêm: HSTS chỉ có nghĩa khi đã có HTTPS, nên app không tự set.

### 2.2 Rate limit — hiện tại là 0

Đây là lỗ hổng thật khi mở công khai. App không giới hạn gì: một script gọi
`/api/transactions?limit=...` liên tục sẽ kéo sập một instance nhỏ, hoặc ít nhất làm
chậm cho người khác.

Hai lớp, làm cả hai:

```nginx
# nginx: 30 request/phút mỗi IP cho API
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;

location /api/ {
    limit_req zone=api burst=10 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8765;
}
```

Và một giới hạn cứng trong code: `limit` tối đa cho mỗi truy vấn (đã có sẵn cơ chế
giới hạn số bản ghi — cần rà lại trần).

### 2.3 Không đưa memo thô lên

Bản deploy hiện tại đã xoá `raw_description` (0 dòng còn PII). Giữ nguyên nguyên tắc
đó: **database đưa lên Internet là bản đã ẩn danh**, bản đầy đủ chỉ nằm trên máy.

Nếu sau này cần bản đầy đủ cho nội bộ Quỹ, nó phải là một deployment riêng, có đăng
nhập, không cùng host với bản công khai.

### 2.4 Lộ phiên bản Python trong header `Server`

`BaseHTTPRequestHandler` tự ghép header `Server: NuoiEmTopic4/2.0 Python/3.13.x`.
Tức là app khai chính xác phiên bản Python đang chạy — **đúng loại lỗi mà dự án này
đã chỉ trích ở web của Quỹ** (`Server: nginx/1.24.0`, `X-Powered-By: Next.js`).

Sửa ở proxy, không cần sửa code:

```nginx
proxy_hide_header Server;
add_header Server "nuoiem" always;
```

Hoặc sửa trong code, nếu muốn app tự đúng:

```python
class RequestHandler(BaseHTTPRequestHandler):
    def version_string(self) -> str:
        return "nuoiem"
```

Đây là chi tiết nhỏ, nhưng nếu báo cáo phê bình người khác lộ stack thì code của
mình cũng không nên lộ.

---

## 3. Chọn kiến trúc nào

> Phân tích riêng cho phần database — vì sao giữ SQLite dù chạy trên AWS, và khi nào
> mới chuyển Postgres — nằm ở `QUYET_DINH_DATABASE.md`. Đọc kèm mục này.

| Phương án | Hợp với | Ưu | Nhược | Chi phí ước tính |
|---|---|---|---|---|
| **A. Lightsail + nginx** | demo, nộp bài, chạy thật quy mô nhỏ | đơn giản nhất, giá cố định, có sẵn static IP, SSL dễ | 1 máy, không HA, tự vá OS | **~$5–7/tháng** |
| **B. EC2 t4g.nano + EBS + nginx** | muốn kiểm soát, dùng free tier | rẻ nhất, linh hoạt | phải tự dựng nhiều thứ hơn Lightsail | **~$3–6/tháng** |
| **C. ALB + EC2** | nhiều instance | cân bằng tải, health check | **ALB đắt hơn cả instance** | ~$20–28/tháng |
| **D. ECS Fargate + EFS** | cần scale ngang | không quản OS | SQLite trên EFS chậm, phức tạp vô ích ở quy mô này | ~$20–35/tháng |
| **E. RDS Postgres + App Runner** | Quỹ dùng thật, nhiều người ghi | đúng hướng dài hạn, backup tự động | **phải port toàn bộ SQL**, sửa schema, sửa test | ~$35–60/tháng |

Giá trên là **khoảng tham khảo**, không phải báo giá — AWS đổi giá và tùy region.
Cần kiểm tra lại ở trang pricing trước khi cam kết với ai.

### Khuyến nghị

**Bây giờ: phương án A.** Một máy, nginx, SQLite, chạy đúng như hiện tại. Không cần
đổi một dòng code nào.

**Khi Quỹ thật sự dùng: phương án E.** Lúc đó mới đáng đổi, vì có người ghi dữ liệu
(đề nghị chi, phê duyệt, chứng từ) thì SQLite hết phù hợp — nó chỉ cho một tiến trình
ghi tại một thời điểm.

Đừng nhảy sang C/D ở quy mô này. Đó là cách tiêu tiền để giải quyết vấn đề mình
không có.

---

## 4. SQLite trên AWS — giới hạn thật

| Câu hỏi | Trả lời |
|---|---|
| Nhiều instance đọc cùng lúc được không? | **Không** — mỗi máy cần bản sao riêng. Read-only nên chỉ là chuyện đồng bộ file, nhưng vẫn là vấn đề |
| Một tiến trình ghi được không? | Được, nhưng app hiện **không ghi** nên chưa gặp |
| Chạy trên Lambda được không? | Được về kỹ thuật (DB 176 MB < giới hạn 250 MB), nhưng mỗi cold start phải tải file → chậm và tốn. Không nên |
| Backup thế nào? | Snapshot EBS theo lịch, hoặc `VACUUM INTO` ra S3 mỗi đêm |
| 176 MB có tốn RAM không? | Không — SQLite đọc từ disk, page cache dùng RAM còn trống. 512 MB RAM là đủ |

---

## 5. Cấu hình mẫu (phương án A)

**systemd unit** — để app tự chạy lại khi reboot:

```ini
[Unit]
Description=Nuoi Em transparency dashboard
After=network.target

[Service]
Type=simple
User=nuoiem
WorkingDirectory=/opt/nuoiem
ExecStart=/usr/bin/python3 app.py --host 127.0.0.1 --port 8765
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadOnlyPaths=/opt/nuoiem

[Install]
WantedBy=multi-user.target
```

**nginx** — TLS + rate limit + chặn truy cập file ẩn:

```nginx
server {
    listen 443 ssl http2;
    server_name nuoiem.example.com;

    ssl_certificate     /etc/letsencrypt/live/nuoiem.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nuoiem.example.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    server_tokens off;
    proxy_hide_header Server;
    add_header Server "nuoiem" always;

    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;

    location /api/ {
        limit_req zone=api burst=10 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header X-Forwarded-For $remote_addr;
    }

    location / {
        proxy_pass http://127.0.0.1:8765;
    }
}

server {
    listen 80;
    server_name nuoiem.example.com;
    return 301 https://$host$request_uri;
}
```

Lưu ý: app bind `127.0.0.1` chứ không `0.0.0.0`. Chỉ nginx nói chuyện với Internet,
app không lộ trực tiếp. Đây là mặc định an toàn hơn.

---

## 6. Chi phí thực tế cho một học kỳ

| Khoản | /tháng | 4 tháng |
|---|---:|---:|
| Lightsail 1 GB | ~$6 | ~$24 |
| Domain `.com` (nếu mua) | ~$1 | ~$4 |
| Snapshot backup | ~$0,10 | ~$0,40 |
| **Tổng** | **~$7** | **~$28** |

Khoảng **700.000 đ cho cả học kỳ**. Nếu chỉ để demo thì sandbox hiện tại là đủ và
miễn phí — không cần trả tiền.

---

## 7. Việc này có làm tăng % hoàn thiện không?

**Không nhiều.** Deploy lên AWS là chuyện hạ tầng, không phải chức năng. Nó đổi
"chạy được trên máy mình" thành "chạy ổn định trên Internet", nhưng **không lấp được
chỗ trống danh mục học sinh** — mà đó mới là 10 điểm lớn nhất còn thiếu.

Ước lượng: +3 đến +5 điểm ở mục vận hành. Từ 77% lên khoảng 80–82%, không hơn.

Nếu chỉ có thời gian cho một việc, **xin danh mục học sinh** đem lại nhiều hơn là
dựng AWS.

---

## 8. Thứ tự làm, nếu vẫn muốn lên AWS

1. Mua/tạo Lightsail, cài Python 3.11+, copy code + DB đã ẩn danh.
2. Chạy thử bằng tay: `python3 app.py --host 127.0.0.1`.
3. Dựng systemd unit, bật `systemctl enable --now`.
4. Cài nginx, trỏ `proxy_pass` vào `127.0.0.1:8765`.
5. Trỏ domain, chạy `certbot --nginx`, kiểm tra HTTPS.
6. Thêm rate limit, thử bằng `curl` liên tục xem có trả 429 không.
7. Bật snapshot EBS hằng ngày.
8. Kiểm tra lại: `/health`, `/api/summary`, và một truy vấn nặng để đo thời gian.
9. Tắt port 8765 ra ngoài (chỉ mở 80/443).
