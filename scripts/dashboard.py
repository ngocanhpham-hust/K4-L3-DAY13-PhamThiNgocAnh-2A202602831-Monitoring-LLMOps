from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
WINDOW_MINUTES = 60
REFRESH_SECONDS = 30


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_records(path: Path = LOG_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamp = parse_timestamp(record.get("ts"))
        if timestamp is not None:
            record["_timestamp"] = timestamp
            records.append(record)

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)
    return [record for record in records if record["_timestamp"] >= cutoff]


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def minute_series(records: list[dict[str, Any]], value_key: str | None = None) -> list[float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for record in records:
        minute = record["_timestamp"].strftime("%H:%M")
        if value_key is None:
            grouped[minute].append(1.0)
        elif isinstance(record.get(value_key), (int, float)):
            grouped[minute].append(float(record[value_key]))
    if value_key is None:
        return [sum(values) for _, values in sorted(grouped.items())]
    return [mean(values) for _, values in sorted(grouped.items())]


def metric(label: str, value: str) -> str:
    return (
        '<div class="metric">'
        f'<span>{html.escape(label)}</span><strong>{html.escape(value)}</strong>'
        "</div>"
    )


def chart(values: list[float], threshold: float, *, lower_is_good: bool = True) -> str:
    safe_values = values or [0.0]
    ceiling = max(max(safe_values), threshold * 1.25, 1.0)
    marker = min(94.0, max(4.0, threshold / ceiling * 100))
    bars = "".join(
        f'<i style="height:{max(3.0, value / ceiling * 100):.1f}%"></i>'
        for value in safe_values[-30:]
    )
    direction = "≤" if lower_is_good else "≥"
    return (
        '<div class="chart">'
        f'<div class="threshold" style="bottom:{marker:.1f}%"><b>{direction} {threshold:g}</b></div>'
        f'<div class="bars">{bars}</div>'
        "</div>"
    )


def panel(
    title: str,
    unit: str,
    headline: str,
    metrics: list[str],
    values: list[float],
    threshold: float,
    passed: bool,
    *,
    lower_is_good: bool = True,
) -> str:
    status = "Within threshold" if passed else "Threshold breached"
    status_class = "ok" if passed else "bad"
    return f"""
    <section class="panel">
      <header><div><h2>{html.escape(title)}</h2><small>{html.escape(unit)}</small></div>
      <span class="status {status_class}">{status}</span></header>
      <div class="headline">{html.escape(headline)}</div>
      <div class="metrics">{''.join(metrics)}</div>
      {chart(values, threshold, lower_is_good=lower_is_good)}
    </section>
    """


def render_dashboard(records: list[dict[str, Any]]) -> str:
    responses = [record for record in records if record.get("event") == "response_sent"]
    received = [record for record in records if record.get("event") == "request_received"]
    failed = [record for record in records if record.get("event") == "request_failed"]
    tool_events = [record for record in records if isinstance(record.get("tool_success"), bool)]

    latencies = [float(record["latency_ms"]) for record in responses if isinstance(record.get("latency_ms"), (int, float))]
    ttfts = [float(record["ttft_ms"]) for record in responses if isinstance(record.get("ttft_ms"), (int, float))]
    costs = [float(record["cost_usd"]) for record in responses if isinstance(record.get("cost_usd"), (int, float))]
    tokens_in = [float(record["tokens_in"]) for record in responses if isinstance(record.get("tokens_in"), (int, float))]
    tokens_out = [float(record["tokens_out"]) for record in responses if isinstance(record.get("tokens_out"), (int, float))]
    qualities = [float(record["quality_score"]) for record in responses if isinstance(record.get("quality_score"), (int, float))]

    p50 = percentile(latencies, 0.50)
    p95 = percentile(latencies, 0.95)
    p99 = percentile(latencies, 0.99)
    ttft_p95 = percentile(ttfts, 0.95)
    traffic_by_minute = minute_series(received)
    request_rate = mean(traffic_by_minute) if traffic_by_minute else 0.0
    error_rate = len(failed) / len(received) * 100 if received else 0.0
    retrieval_success = (
        sum(record["tool_success"] is True for record in tool_events) / len(tool_events) * 100
        if tool_events
        else 100.0
    )
    total_cost = sum(costs)
    total_tokens_in = sum(tokens_in)
    total_tokens_out = sum(tokens_out)
    total_tokens = total_tokens_in + total_tokens_out
    quality_avg = mean(qualities) if qualities else 0.0
    errors_by_type = Counter(str(record.get("error_type", "unknown")) for record in failed)
    error_detail = ", ".join(f"{name}: {count}" for name, count in errors_by_type.items()) or "none"

    panels = [
        panel(
            "Latency percentiles & TTFT",
            "milliseconds",
            f"P95 {p95:,.0f} ms",
            [metric("P50", f"{p50:,.0f}"), metric("P99", f"{p99:,.0f}"), metric("TTFT P95", f"{ttft_p95:,.0f}")],
            minute_series(responses, "latency_ms"),
            2000,
            p95 <= 2000,
        ),
        panel(
            "Request traffic",
            "requests / minute",
            f"{len(received)} requests",
            [metric("Average rate", f"{request_rate:.1f}/min"), metric("Active minutes", str(len(traffic_by_minute)))],
            traffic_by_minute,
            1,
            request_rate >= 1,
            lower_is_good=False,
        ),
        panel(
            "Errors & retrieval success",
            "percent",
            f"{error_rate:.1f}% errors",
            [metric("Retrieval success", f"{retrieval_success:.1f}%"), metric("Error types", error_detail)],
            [error_rate],
            2,
            error_rate <= 2 and retrieval_success >= 90,
        ),
        panel(
            "Cost over time",
            "USD",
            f"${total_cost:.4f}",
            [metric("Responses", str(len(responses))), metric("Average", f"${mean(costs) if costs else 0:.5f}")],
            [sum(costs)] if costs else [0.0],
            2.5,
            total_cost <= 2.5,
        ),
        panel(
            "Input & output tokens",
            "tokens",
            f"{total_tokens:,.0f} total",
            [metric("Input", f"{total_tokens_in:,.0f}"), metric("Output", f"{total_tokens_out:,.0f}")],
            minute_series(responses, "tokens_out"),
            50000,
            total_tokens <= 50000,
        ),
        panel(
            "Quality proxy",
            "score 0–1",
            f"{quality_avg:.2f} average",
            [metric("Samples", str(len(qualities))), metric("Minimum", f"{min(qualities) if qualities else 0:.2f}")],
            qualities,
            0.75,
            quality_avg >= 0.75,
            lower_is_good=False,
        ),
    ]

    newest = max((record["_timestamp"] for record in records), default=None)
    updated = newest.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z") if newest else "No log data"
    empty_notice = "" if records else '<div class="empty">No records in the last 60 minutes. Run the load test first.</div>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{REFRESH_SECONDS}">
  <title>K4-L3B LLM Operations Dashboard</title>
  <style>
    :root {{ color-scheme: dark; --bg:#07111f; --card:#0e1b2d; --line:#26364d; --text:#eef5ff; --muted:#91a4bd; --cyan:#31d8c6; --amber:#ffb84d; --red:#ff6b75; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-width:1000px; background:radial-gradient(circle at 20% 0,#123151 0,#07111f 42%); color:var(--text); font:14px/1.4 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif; }}
    main {{ width:min(1500px,96vw); margin:0 auto; padding:24px 0 32px; }}
    .top {{ display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:18px; }}
    h1 {{ margin:0; font-size:28px; letter-spacing:-.04em; }}
    .eyebrow {{ color:var(--cyan); font-size:11px; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }}
    .meta {{ text-align:right; color:var(--muted); }}
    .meta b {{ color:var(--text); }}
    .grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
    .panel {{ min-height:290px; background:linear-gradient(145deg,rgba(18,36,59,.96),rgba(10,24,41,.96)); border:1px solid var(--line); border-radius:16px; padding:17px; box-shadow:0 16px 35px rgba(0,0,0,.18); }}
    .panel header {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
    h2 {{ margin:0; font-size:15px; }}
    small {{ color:var(--muted); }}
    .status {{ border-radius:99px; padding:5px 9px; font-size:10px; font-weight:800; text-transform:uppercase; white-space:nowrap; }}
    .ok {{ color:var(--cyan); background:rgba(49,216,198,.11); }}
    .bad {{ color:var(--red); background:rgba(255,107,117,.13); }}
    .headline {{ margin:17px 0 13px; font-size:27px; font-weight:800; letter-spacing:-.03em; }}
    .metrics {{ display:flex; gap:18px; min-height:42px; }}
    .metric {{ min-width:82px; display:flex; flex-direction:column; }}
    .metric span {{ color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.08em; }}
    .metric strong {{ font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:180px; }}
    .chart {{ position:relative; height:104px; margin-top:15px; border-bottom:1px solid var(--line); background:repeating-linear-gradient(to top,transparent 0,transparent 25px,rgba(145,164,189,.08) 26px); overflow:hidden; }}
    .bars {{ position:absolute; inset:0; display:flex; align-items:flex-end; gap:3px; }}
    .bars i {{ flex:1; min-width:4px; max-width:24px; border-radius:4px 4px 1px 1px; background:linear-gradient(to top,#178d99,var(--cyan)); opacity:.82; }}
    .threshold {{ position:absolute; z-index:2; left:0; right:0; border-top:1px dashed var(--amber); color:var(--amber); font-size:9px; }}
    .threshold b {{ position:absolute; right:0; bottom:2px; background:var(--card); padding-left:5px; }}
    .empty {{ margin-bottom:14px; padding:10px 14px; border:1px solid var(--amber); border-radius:10px; color:var(--amber); }}
    footer {{ display:flex; justify-content:space-between; margin-top:14px; color:var(--muted); font-size:11px; }}
  </style>
</head>
<body>
  <main>
    <div class="top"><div><div class="eyebrow">Day 13 · Monitoring & LLMOps</div><h1>Operational evidence dashboard</h1></div>
      <div class="meta"><b>Last 60 minutes · UTC source</b><br>Auto-refresh 30s · Latest event: {html.escape(updated)}</div></div>
    {empty_notice}
    <div class="grid">{''.join(panels)}</div>
    <footer><span>Source: data/logs.jsonl · Student 2A202602831</span><span>Thresholds follow config/dashboard.yaml</span></footer>
  </main>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        payload = render_dashboard(load_records()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the six-panel Day 13 dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard: http://{args.host}:{args.port}")
    print("Source: data/logs.jsonl | Window: 60 minutes | Refresh: 30 seconds")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
