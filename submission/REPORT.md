# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Phạm Thị Ngọc Anh
- **MSSV:** 2A202602831
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/ngocanhpham-hust/K4-L3-DAY13-PhamThiNgocAnh-2A202602831-Monitoring-LLMOps
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602831`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Không thiếu required fields/enrichment; correlation ID hợp lệ; không phát hiện PII thô. |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Contract có đủ latency, traffic, errors, cost, tokens và quality. |
| `pytest` | 22 passed | 26 passed | Bổ sung test PII và child observations cho Langfuse. |
| Số traces hợp lệ | Chưa đo | 28 | 28 root traces trong giờ kiểm tra, mỗi trace có child `retrieval` và `generation`; xác minh bằng Observations API v2. |
| Số PII leak | 0 | 0 | Validator độc lập không phát hiện email, điện thoại VN, CCCD hoặc thẻ thô. |
| Latency P95 / TTFT P95 | Chưa đo | 2664.3 ms / 55 ms | Cửa sổ CP3 gồm 10 baseline và 5 challenge requests; incident P95 riêng là 2664.8 ms. |
| Retrieval success rate | Chưa đo | 100% | Tính trên mọi event có field `tool_success`; retrieval chậm nhưng vẫn thành công. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware gọi `clear_contextvars()`, nhận `x-request-id` hoặc sinh `req-<8-hex>`, bind vào structlog, lưu trong `request.state`, truyền vào agent/trace và trả lại trong response header.
- **Các metadata được ghi vào structured log:** `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`, latency, TTFT, token, cost, quality và trạng thái retrieval.
- **Cách bảo đảm PII được scrub trước khi ghi:** User ID được hash; `scrub_event` chạy trước file writer/JSON renderer để che email, số điện thoại VN, CCCD và số thẻ.
- **Cách kiểm chứng kết quả:** Unit test cho bốn loại PII, request PII giả và validator độc lập; kết quả hiện tại là 100/100 và 0 PII leak.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Chạy workload bằng key của project `day13-k4-l3b-2A202602831`, lọc trace name `day13-agent-request`, environment `dev` và đối chiếu `correlation_id` với log; có 28 root traces hợp lệ trong giờ kiểm tra.
- **Cấu trúc root/retrieval/generation observations:** `day13-agent-request` → `lab-agent-run` → `retrieval` và `generation`; generation ghi model, usage, cost và managed prompt nhưng không capture raw input/output.
- **Cách nối trace với log:** Dùng cùng `correlation_id` trong log và trace metadata.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** v1 với labels `baseline`, `production` sau rollback.
- **Version/label candidate:** v2 với labels `candidate`, `latest` sau rollback.
- **Trace ID của mỗi version:** baseline v1 `9369bcfe7c693b84931a7db33a3deac9`; candidate v2 `f73c233a98885641126d982a0f037a41`; production-v2 khi promote `01cc4eb817c71a9493e1584836a81c52`; production-v1 sau rollback `124dfa1bc5ffd51822ac4255c663e60b`.
- **Cách promote và rollback `production`:** Dời `production` từ v1 sang v2, restart và tạo trace xác nhận v2; sau đó dời `production` về v1, giữ `candidate` trên v2, restart và tạo trace xác nhận v1. Trạng thái cuối: v1=`baseline, production`, v2=`candidate, latest`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard local đọc `data/logs.jsonl`, cửa sổ 60 phút, refresh 30 giây; gồm Latency/TTFT, Traffic, Errors/Retrieval success, Cost, Tokens và Quality, có threshold theo `config/dashboard.yaml`.
- **SLO và lý do chọn:** 99.5% request phải thành công và hoàn tất trong 2000 ms trong cửa sổ 28 ngày; baseline thấp hơn ngưỡng này còn challenge `rag_slow` vượt 2000 ms.
- **Cách tính error budget:** Error budget là `100% - 99.5% = 0.5%`; với 10,000 request, tối đa `10,000 × 0.005 = 50` request được phép lỗi hoặc chậm hơn 2000 ms.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (>2000 ms/5m), `HighRequestErrorRate` (>2%/3m) và `LowRetrievalSuccessRate` (<90%/5m), gửi Slack `#k4-l3b-alerts`; runbook tại `docs/alerts.md` đi theo Metrics → Logs → Traces rồi mitigation.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (`rag_slow`).
- **Khoảng thời gian điều tra:** `2026-10-01 00:09:26–00:09:39 ICT` (`2026-09-30 17:09:26–17:09:39 UTC`).
- **Triệu chứng từ metrics:** Baseline latency P95 khoảng 630.7 ms; 5 challenge requests có P95 2664.8 ms và toàn cửa sổ tăng lên 2664.3 ms, vượt threshold 2000 ms. TTFT vẫn khoảng 51–55 ms, error rate 0% và retrieval success 100%, nên triệu chứng là tail latency chứ không phải lỗi hoặc generation chậm.
- **Log line và correlation ID liên quan:** `response_sent` lúc `2026-09-30T17:09:39.704343Z`, `correlation_id=req-d46b7402`, `feature=monitoring`, `latency_ms=2665`, `ttft_ms=55`, `tool_success=true`.
- **Trace ID và span gây ảnh hưởng:** Trace `65025ca934d9c2d98375bf214fab5d51`; root `lab-agent-run` 2.667s, `retrieval` 2.506s, `generation` 0.158s. Trace dùng `day13-chat` production v1 và cùng `correlation_id=req-d46b7402`.
- **Root cause:** Incident `rag_slow` thêm độ trễ khoảng 2.5 giây vào bước retrieval; generation vẫn bình thường nên retrieval là span gây tail latency.
- **Fix action:** Tắt `rag_slow` bằng `python scripts/inject_incident.py --scenario rag_slow --disable`; `/health` sau xử lý xác nhận `rag_slow`, `tool_fail`, `cost_spike` đều `false`.
- **Preventive measure:** Alert `HighLatencyP95` khi P95 > 2000 ms trong 5 phút; runbook bắt buộc chọn log có correlation ID rồi so sánh span retrieval/generation; duy trì baseline và test incident để phát hiện regression trước production.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Không capture raw prompt/output trong trace; chỉ lưu preview đã scrub và metadata cần điều tra để giảm nguy cơ lộ PII.
- **Một lỗi/blocker đã gặp:** Langfuse trả `401 Invalid credentials` dù public/secret key đã được cấu hình.
- **Cách tìm nguyên nhân và xử lý:** Thử xác thực ở hai region mà không in secret, xác định key thuộc US region, đổi `LANGFUSE_BASE_URL` sang `https://us.cloud.langfuse.com`, restart API rồi xác minh trace/prompt bằng Observations API v2.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics xác định triệu chứng và thời gian; log cung cấp request cụ thể qua `correlation_id`; trace cùng ID cho thấy span retrieval/generation gây chậm hoặc lỗi.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version giúp đối chiếu regression và rollback không cần sửa code; token/cost phát hiện tiêu thụ bất thường; SLO/error budget lượng hóa mức rủi ro chấp nhận được.
- **Điều quan trọng nhất đã học:** Evidence vận hành chỉ đáng tin khi metric, log và trace cùng chỉ về một request/khoảng sự cố.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Cần chụp đúng 5 ảnh runtime và bổ sung Repository URL/Commit SHA sau khi commit cuối; ảnh phải do chính tôi chụp từ VS Code, Langfuse và dashboard, không hiển thị key/secret.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
