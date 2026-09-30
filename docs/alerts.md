# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: P95 của `response_sent.latency_ms`; SLO request thành công trong 2000 ms.
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 2000ms` liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời đến chậm, làm tiêu hao error budget latency.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency, xác nhận P95/P99, TTFT và khoảng thời gian tăng.
  2. Lọc `response_sent` có `latency_ms > 2000`, lấy một `correlation_id` đại diện.
  3. Mở trace cùng `correlation_id`, so sánh duration của `retrieval` và `generation` để xác định span chậm.
- Mitigation tạm thời: tắt incident practice nếu đang bật; nếu regression đến từ prompt thì rollback `production`; giảm concurrency khi hệ thống quá tải.
- Owner: `student-2A202602831`

## Alert 2

- Tên: `HighRequestErrorRate`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ `request_failed / request_received`; guardrail error rate tối đa 2%.
- Điều kiện và thời gian duy trì: error rate lớn hơn 2% liên tục 3 phút.
- Ảnh hưởng tới người dùng: request trả lỗi và không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors, xác nhận error rate và nhóm `error_type` tăng.
  2. Lọc `request_failed` trong cùng khoảng thời gian và lấy `correlation_id`, `error_type`, `tool_name`.
  3. Mở trace cùng `correlation_id`, kiểm tra trạng thái `retrieval` và `generation` để định vị lỗi.
- Mitigation tạm thời: tắt scenario gây lỗi, khôi phục dependency retrieval hoặc rollback thay đổi gần nhất; trả fallback an toàn nếu cần.
- Owner: `student-2A202602831`

## Alert 3

- Tên: `LowRetrievalSuccessRate`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ thành công của mọi event có `tool_success`; guardrail tối thiểu 90%.
- Điều kiện và thời gian duy trì: retrieval success thấp hơn 90% liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời thiếu context hoặc request thất bại vì không lấy được tài liệu.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors/Retrieval, xác nhận tỷ lệ thành công và thời điểm giảm.
  2. Lọc event có `tool_success=false`, lấy `correlation_id` và `error_type`.
  3. Mở trace cùng `correlation_id`, kiểm tra span `retrieval` và các span phía sau.
- Mitigation tạm thời: chuyển sang context fallback, giảm tải hoặc khôi phục vector store; tắt scenario practice nếu còn bật.
- Owner: `student-2A202602831`
