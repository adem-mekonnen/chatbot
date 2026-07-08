# app/logger.py
import json
import logging
import sys
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Any

class JSONFormatter(logging.Formatter):
    """Formats logs into structured JSON payloads for automated ingest systems."""
    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "metadata"):
            log_payload["metadata"] = record.metadata
        return json.dumps(log_payload)

def setup_logger(name: str = "enterprise-agent") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    return logger

structured_logger = setup_logger()

class EnterpriseMetricsCollector:
    """Thread-safe Prometheus-style metrics collector for system operational monitoring."""
    def __init__(self):
        self.lock = Lock()
        self.metrics = {
            "api_requests_total": 0,
            "api_failures_total": 0,
            "tool_executions_total": 0,
            "rag_lookups_total": 0,
            "llm_calls_total": 0,
            "llm_latency_sum_ms": 0.0,
            "llm_latency_count": 0,
            "auth_successes": 0,
            "auth_failures": 0,
            "auth_errors": 0,
            "chat_requests_success": 0,
            "chat_requests_error": 0,
            "app_starts_total": 0
        }
        # Store histogram data (sum and count for each metric)
        self.histograms: Dict[str, Dict[str, float]] = {}

    def increment(self, metric_name: str, count: int = 1):
        with self.lock:
            if metric_name not in self.metrics:
                self.metrics[metric_name] = 0
            self.metrics[metric_name] += count

    def record_latency(self, latency_ms: float):
        with self.lock:
            self.metrics["llm_latency_sum_ms"] += latency_ms
            self.metrics["llm_latency_count"] += 1
    
    def histogram(self, metric_name: str, value: float):
        """Record a histogram observation (e.g., duration, size)."""
        with self.lock:
            if metric_name not in self.histograms:
                self.histograms[metric_name] = {"sum": 0.0, "count": 0}
            self.histograms[metric_name]["sum"] += value
            self.histograms[metric_name]["count"] += 1

    def export_prometheus_format(self) -> str:
        """
        Serializes current metric values as Prometheus text exposition format 0.0.4.

        The returned string is ready to be served with:
            Content-Type: text/plain; version=0.0.4; charset=utf-8
        Each metric block ends with a blank line and the whole payload ends with
        a trailing newline, both required by the spec.
        """
        blocks = []
        with self.lock:
            for k, v in self.metrics.items():
                metric_type = "counter" if "total" in k else "gauge"
                block = (
                    f"# HELP {k} Enterprise agent operational metric.\n"
                    f"# TYPE {k} {metric_type}\n"
                    f"{k} {v}"
                )
                blocks.append(block)
            
            # Add histogram metrics
            for name, data in self.histograms.items():
                block = (
                    f"# HELP {name} Histogram metric for {name}.\n"
                    f"# TYPE {name} histogram\n"
                    f"{name}_sum {data['sum']}\n"
                    f"{name}_count {data['count']}"
                )
                blocks.append(block)
        
        return "\n\n".join(blocks) + "\n"

metrics_collector = EnterpriseMetricsCollector()