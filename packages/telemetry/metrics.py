"""Operational Metrics Collector for DeployOS."""

from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Thread-safe in-memory and Prometheus-ready metrics collector."""

    def __init__(self):
        self.counters: dict[str, float] = defaultdict(float)
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.gauges: dict[str, float] = {}

    def inc(self, metric: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        tag_key = self._format_key(metric, tags)
        self.counters[tag_key] += value

    def observe(self, metric: str, value: float, tags: dict[str, str] | None = None) -> None:
        tag_key = self._format_key(metric, tags)
        self.histograms[tag_key].append(value)

    def set_gauge(self, metric: str, value: float, tags: dict[str, str] | None = None) -> None:
        tag_key = self._format_key(metric, tags)
        self.gauges[tag_key] = value

    def _format_key(self, metric: str, tags: dict[str, str] | None) -> str:
        if not tags:
            return metric
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{metric}{{{tag_str}}}"

    def get_summary(self) -> dict[str, Any]:
        """Produce operational summary snapshot."""
        p50, p95, p99 = 0.0, 0.0, 0.0
        latencies = []
        for k, v in self.histograms.items():
            if "latency" in k:
                latencies.extend(v)

        if latencies:
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            p50 = sorted_lat[int(n * 0.50)]
            p95 = sorted_lat[min(int(n * 0.95), n - 1)]
            p99 = sorted_lat[min(int(n * 0.99), n - 1)]

        return {
            "total_tasks": int(self.counters.get("tasks_total", 0)),
            "successful_tasks": int(self.counters.get("tasks_success_total", 0)),
            "failed_tasks": int(self.counters.get("tasks_failed_total", 0)),
            "blocked_actions": int(self.counters.get("actions_blocked_total", 0)),
            "human_reviews": int(self.counters.get("human_reviews_total", 0)),
            "total_tokens": int(self.counters.get("tokens_total", 0)),
            "total_cost_usd": round(self.counters.get("cost_usd_total", 0.0), 4),
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
        }


metrics = MetricsCollector()
