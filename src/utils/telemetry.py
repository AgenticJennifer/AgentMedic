import time
import json
import sys
from typing import Dict, Any, Optional

class TelemetryTracker:
    def __init__(self, pricing_dict: Optional[Dict[str, float]] = None) -> None:
        self.pricing: Dict[str, float] = pricing_dict or {
            "input_token_cost_per_m": 3.00,
            "output_token_cost_per_m": 15.00
        }
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.tool_calls_count: int = 0

    def reset(self) -> None:
        self.start_time = 0.0
        self.end_time = 0.0
        self.input_tokens = 0
        self.output_tokens = 0
        self.tool_calls_count = 0

    def start(self) -> None:
        self.start_time = time.perf_counter()

    def stop(self) -> None:
        self.end_time = time.perf_counter()

    def log_tokens(self, input_cnt: int, output_cnt: int) -> None:
        self.input_tokens += input_cnt
        self.output_tokens += output_cnt

    def log_tool_call(self) -> None:
        self.tool_calls_count += 1

    def emit_otel_log(self, scenario_id: str, stage: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Emits structured, OpenTelemetry-compliant JSON logs to stderr."""
        log_record = {
            "timestamp": time.time(),
            "service_name": "agent_profiler",
            "scenario_id": scenario_id,
            "stage": stage,
            "body": message,
            "attributes": metadata or {}
        }
        sys.stderr.write(json.dumps(log_record) + "\n")
        sys.stderr.flush()

    def calculate_metrics(self) -> Dict[str, Any]:
        duration = self.end_time - self.start_time
        cost = ((self.input_tokens / 1_000_000) * self.pricing["input_token_cost_per_m"]) + \
               ((self.output_tokens / 1_000_000) * self.pricing["output_token_cost_per_m"])
        return {
            "duration_seconds": round(duration, 3),
            "total_tokens": self.input_tokens + self.output_tokens,
            "calculated_cost_usd": round(cost, 6),
            "total_tool_calls": self.tool_calls_count
        }