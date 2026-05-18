# Hướng Dẫn Nộp Bài - Lab #28: Full Platform Integration Sprint

## Yêu Cầu Nộp Bài

**Full AI infrastructure platform demo** - từ data ingestion đến model serving với full observability.

## Các Artifacts Cần Nộp

### 1. Source Code
- Folder `lab28/` hoàn chỉnh với tất cả files
- Tất cả integration scripts hoạt động
- Prefect flows đã deploy và schedule

### 2. Screenshots Demo
Chụp màn hình các bước:
- Prefect UI: http://localhost:4200 (flow đang chạy)
- API Gateway call: `curl http://localhost:8000/health`
- Grafana dashboard: http://localhost:3000

### 3. Kết Quả Smoke Tests
Chạy và chụp màn hình kết quả:
```bash
cd lab28
pytest smoke-tests/ -v
```
Kỳ vọng: 5/5 tests passing

### 4. Production Readiness Score
```bash
python scripts/production_readiness_check.py
```
Kỳ vọng: Score >80%

### 5. Documentation
- `README.md` giải thích cách:
  - Start platform: `docker compose up -d`
  - Deploy Prefect flows
  - Run smoke tests
  - Access dashboards (Grafana:3000, Prometheus:9090, Prefect:4200)

## Định Dạng Nộp Bài

Tạo Repo GitHub chứa:
```
lab28_submission_[student_id]
├── lab28/                    # Source code hoàn chỉnh
│   ├── docker-compose.yml
│   ├── prefect/flows/
│   ├── scripts/
│   ├── api-gateway/
│   └── monitoring/
├── screenshots/              # Screenshots demo
│   ├── prefect_ui.png
│   ├── api_gateway.png
│   └── grafana_dashboard.png
├── smoke_tests_results.png   # Screenshot kết quả pytest
├── production_readiness.png  # Screenshot readiness score
└── README.md                # Hướng dẫn setup
```

## Địa Điểm Nộp
Nộp link repo GitHub qua LMS

## Tiêu Chí Chấm Điểm

| Tiêu Chí | Trọng Số | Mô Tả |
|----------|----------|-------|
| Integration Completeness | 40% | Tất cả 10 integration points hoạt động, data flow end-to-end |
| Observability | 25% | Logs, metrics, traces hiển thị; alerts configured |
| Performance | 20% | Latency trong SLO; load tested; không có memory leaks |
| Architecture Quality | 15% | Clean separation, GitOps config, documented decisions |

## Các Vấn Đề Cần Tránh

- Config drift giữa các environments
- Thiếu error handling tại integration points
- Monitoring coverage không hoàn chỉnh
- Không có rollback strategy
- Demo không test trước khi nộp

---

## 5 Câu Hỏi Cần Trả Lời Khi Nộp

### 1. Phân tích các trade-offs trong thiết kế kiến trúc AI platform của bạn. Bạn đã cân bằng giữa performance, reliability, và maintainability như thế nào?

**Trade-offs chính:**

- **Performance vs Cost**: Dùng Kaggle GPU T4 (miễn phí) để chạy vLLM inference thay vì local GPU. Đánh đổi: latency tăng thêm ~5-7s do round-trip qua ngrok (local → internet → Kaggle → internet → local). Bù lại: tiết kiệm chi phí GPU, không cần máy local mạnh. Với batch inference hoặc async request pattern, latency này chấp nhận được.

- **Reliability vs Simplicity**: Dùng Kafka làm message broker trung gian thay vì gọi trực tiếp HTTP giữa các service. Đánh đổi: thêm 1 tầng infrastructure cần maintain (Zookeeper + Kafka broker). Bù lại: decouple hoàn toàn producer và consumer, có khả năng replay message, chịu được consumer crash mà không mất dữ liệu.

- **Maintainability vs Vendor Lock-in**: Tự build API Gateway bằng FastAPI thay vì dùng managed service (AWS API Gateway, Kong). Đánh đổi: phải tự maintain code, scale, monitoring. Bù lại: linh hoạt custom logic (circuit breaker, fallback), portable giữa các môi trường, không phụ thuộc cloud vendor.

- **Vector Search consistency**: Dùng Qdrant (local Docker) thay vì managed vector DB. Đánh đổi: tự quản lý backup, scaling. Bù lại: latency cực thấp cho vector search (<100ms), không tốn API cost.

**Cân bằng đạt được:** Kiến trúc hybrid phân tách rõ 2 tầng — tầng local xử lý các thành phần latency-sensitive (Qdrant search, Redis feature store, monitoring), tầng cloud (Kaggle) xử lý GPU-intensive tasks (LLM inference, embedding generation). Kết quả: 100% Production Readiness Score, 8/8 smoke tests pass.

---

### 2. Trong kiến trúc hybrid (Local + Kaggle), bạn xử lý ngắt kết nối giữa local và Kaggle như thế nào? Có cơ chế fallback không?

**Các cơ chế xử lý đã implement:**

1. **Graceful Degradation tại API Gateway**: Khi gọi vLLM hoặc embedding service thất bại (timeout, connection refused, HTTP error), API Gateway catch exception và trả về fallback response thay vì crash:
   ```python
   try:
       # gọi vLLM...
   except Exception:
       answer = "LLM service unavailable"
       model = "fallback"
   ```
   Service vẫn healthy, client nhận được response có ý nghĩa thay vì 500 error.

2. **Vector Search fallback**: Nếu Qdrant không available, context trả về empty list `[]` — LLM vẫn có thể trả lời dựa trên knowledge có sẵn trong model (zero-shot), dù chất lượng giảm.

3. **Kafka persistence**: Data được ingest vào Kafka topic trước khi xử lý. Nếu Kaggle ngắt kết nối, pipeline local (Kafka → Delta Lake → Feast) vẫn hoạt động bình thường. Khi Kaggle reconnect, có thể chạy batch job embed các records chưa được xử lý.

4. **Ngrok auto-reconnect**: Khi Kaggle kernel restart, ngrok tự động tạo tunnel mới. Chỉ cần cập nhật URL mới vào `.env` và restart API Gateway container để nhận biến môi trường mới.

**Hướng cải thiện nếu có thêm thời gian:**
- Circuit breaker pattern (dùng `tenacity` hoặc `pybreaker`) để tránh gọi liên tục vào service đã chết
- Cached LLM responses trong Redis cho các query phổ biến, dùng làm fallback khi mất kết nối
- Health check endpoint riêng cho Kaggle connection để Grafana alert sớm

---

### 3. Giải thích cách event-driven architecture với Kafka giúp decouple các components trong AI platform của bạn.

**Luồng event-driven trong platform:**

```
Producer (scripts/01) → Kafka Topic "data.raw" → Consumer (Prefect flow) → Delta Lake → Feast (Redis)
```

**Decoupling cụ thể:**

1. **Producer-Consumer tách biệt thời gian**: Script `01_ingest_to_kafka.py` gửi data vào Kafka và kết thúc ngay, không cần đợi pipeline xử lý xong. Prefect flow (consumer) chạy theo schedule 5 phút/lần, đọc batch records từ Kafka. Nếu consumer chậm hoặc crash, message vẫn được lưu an toàn trong Kafka (retention 7 ngày).

2. **Multiple consumers độc lập**: Cùng một topic `data.raw` có thể được consume bởi nhiều service khác nhau mà không ảnh hưởng lẫn nhau. Ví dụ: Prefect flow consume để lưu Delta Lake; một consumer khác có thể consume để real-time analytics; một consumer thứ ba để gửi alert.

3. **Schema linh hoạt**: Kafka message format là JSON — dễ dàng thêm field mới mà không break consumer cũ (forward compatibility). Consumer chỉ đọc những field nó cần.

4. **Replay capability**: Nếu cần rebuild toàn bộ data pipeline (ví dụ: thay đổi logic xử lý), chỉ cần reset consumer offset về 0 và chạy lại — tất cả data vẫn còn trong Kafka.

5. **Đo lường độc lập**: Có thể monitor consumer lag (số message chưa được xử lý) qua Kafka metrics → Grafana, phát hiện sớm bottleneck.

**Flow cụ thể trong bài lab:**
- Integration 1: Producer gửi 2 records → Kafka (mất <1ms/record)
- Integration 2: Prefect flow mỗi 5 phút consume batch → Delta Lake (xử lý hàng loạt, hiệu quả)
- Integration 3+4: Script đọc từ Delta Lake → Feast/Redis (pull-based, chủ động)

---

### 4. Bạn đã implement observability như thế nào? Logs, metrics, và traces được thu thập và visualized ra sao?

**3 pillars of observability đã implement:**

| Pillar | Công cụ | Chi tiết |
|--------|---------|----------|
| **Metrics** | Prometheus + Grafana | `prometheus-fastapi-instrumentator` tự động expose `/metrics` endpoint với các metric: `http_requests_total`, `http_request_duration_seconds_bucket`, `http_requests_in_progress`. Prometheus scrape mỗi 15s. Grafana dashboard visualize request rate, latency percentiles, error rate. |
| **Logs** | Docker logs + container stdout | Tất cả services log ra stdout → `docker compose logs` hoặc Docker Desktop. Prefect UI hiển thị log chi tiết của từng flow run và task run (consume_and_process, save_to_delta). |
| **Traces** | LangSmith (cấu hình sẵn) | API Gateway được setup với `LANGCHAIN_API_KEY` và `LANGCHAIN_PROJECT`. Khi gọi LLM inference, trace tự động được gửi lên LangSmith để phân tích latency breakdown, token usage, error tracing. |

**Cấu hình cụ thể:**

- **Prometheus config** (`monitoring/prometheus.yml`): scrape 3 job — api-gateway, kafka, prefect-orion, interval 15s
- **Grafana**: tự động connect đến Prometheus data source, dashboard accessible tại `localhost:3000` (admin/admin)
- **Prefect UI**: hiển thị real-time flow runs, task runs, logs, deployment schedules tại `localhost:4200`
- **Health check endpoints**: API Gateway `/health`, Prometheus `/-/healthy`, Grafana `/api/health`, Qdrant `/healthz`

**Verified qua smoke test:**
- `test_prometheus_scrapes_api_gateway` — Prometheus scrape thành công API Gateway metrics
- `test_grafana_dashboard_accessible` — Grafana API health check pass
- Production readiness check xác nhận tất cả monitoring endpoints hoạt động

---

### 5. Nếu một service trong stack (ví dụ: Qdrant hoặc Kafka) bị crash, hệ thống của bạn sẽ xử lý như thế nào? Có graceful degradation không?

**Kịch bản và cơ chế xử lý cho từng service:**

**Qdrant crash:**
- API Gateway bọc Qdrant search trong try-except → trả về empty context `[]` thay vì crash
- LLM vẫn trả lời dựa trên pretrained knowledge (zero-shot), dù thiếu context retrieval
- Health check `/health` vẫn trả về `{"status": "ok"}`
- **Recovery**: `docker compose restart qdrant` — collection được lưu trong named volume nên data không mất

**Kafka crash:**
- Prefect flow consumer không connect được → flow run vẫn completed (với 0 records), không crash worker
- Producer script từ host sẽ fail với lỗi connection — cần retry hoặc báo lỗi rõ ràng
- Các service khác (API Gateway, Qdrant, Feast/Redis) không bị ảnh hưởng
- **Recovery**: `docker compose restart kafka` — topic và message mất (trong bài lab này), nhưng có thể re-ingest data

**Redis (Feast) crash:**
- Script `03_delta_to_feast.py` sẽ fail khi push features
- Smoke test `test_feast_redis_has_features` sẽ phát hiện
- API Gateway không phụ thuộc trực tiếp vào Redis (chỉ dùng Qdrant và vLLM)
- **Recovery**: `docker compose restart redis` — data mất, chạy lại script để re-populate

**vLLM / Kaggle mất kết nối:**
- API Gateway trả về `"LLM service unavailable"` với `model: "fallback"` — không crash
- Response vẫn có `latency_ms` measurement hữu ích để debug
- Smoke test `test_full_inference_returns_200` sẽ FAIL → làm tín hiệu cảnh báo

**Prefect crash:**
- Worker auto-restart nhờ `restart: unless-stopped` trong docker-compose
- Scheduled flow runs được lưu trong SQLite database của Prefect server
- Flow deployments không mất (lưu trong Prefect database)

**Tổng kết khả năng phục hồi:**

| Service | Impact nếu crash | Graceful degradation? | Recovery |
|---------|-----------------|----------------------|----------|
| Qdrant | Mất vector search | Có — empty context | `restart` + volume persist |
| Kafka | Mất data pipeline | Có — flow trả 0 records | `restart` + re-ingest |
| Redis | Mất feature store | Có — không ảnh hưởng API | `restart` + re-run script |
| vLLM/Kaggle | Mất LLM inference | Có — fallback message | Cập nhật ngrok URL |
| Prefect | Mất orchestration | Có — auto-restart | `restart: unless-stopped` |
| API Gateway | Mất toàn bộ | Không — single point | Cần load balancer (chưa implement) |

---

## Kết quả thực tế

```
Smoke Tests:        8/8 PASSED
Production Readiness: 100% (10/10)
Services:           9/9 Running
Integration Points: 10/10 Connected
```

## Câu Hỏi Thêm?
Liên hệ giảng viên qua LMS hoặc office hours.
