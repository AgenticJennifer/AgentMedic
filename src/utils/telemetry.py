import time
from typing import Dict


class TelemetryTracker:
    """
    Tracks execution telemetry for a single profiling run.
    Metrics include elapsed time, token counts, tool‑call count and cost.
    """

    def __init__(self, pricing: Dict[str, float] | None = None) -> None:
        """
        :param pricing: Optional pricing dict with keys ``input_token_cost_per_m`` and
                        ``output_token_cost_per_m``. If omitted, default cloud pricing is used.
        """
        self.pricing: Dict[str, float] = pricing or {
            "input_token_cost_per_m": 3.00,
            "output_token_cost_per_m": 15.00,
        }
        self.reset()

    def reset(self) -> None:
        """Reset all counters and timers to their initial state."""
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.tool_calls_count: int = 0

    def start(self) -> None:
        """Mark the start of a profiling window."""
        self.start_time = time.perf_counter()

    def stop(self) -> None:
        """Mark the end of a profiling window."""
        self.end_time = time.perf_counter()

    def log_tokens(self, input_cnt: int, output_cnt: int) -> None:
        """
        Register token counts for the current run.

        :param input_cnt: Number of input tokens.
        :param output_cnt: Number of output tokens.
        """
        if input_cnt < 0 or output_cnt < 0:
            raise ValueError("Token counts must be non‑negative.")
        self.input_tokens += input_cnt
        self.output_tokens += output_cnt

    def log_tool_call(self) -> None:
        """Increment the internal tool‑call counter."""
        self.tool_calls_count += 1

    def calculate_metrics(self) -> Dict[str, float]:
        """
        Compute derived telemetry metrics.

        :return: Dictionary containing duration, total token volume and cost.
        """
        if self.start_time == 0.0 or self.end_time == 0.0:
            raise RuntimeError("Telemetry tracker must be started and stopped before calculating metrics.")
        duration: float = self.end_time - self.start_time
        input_cost: float = (self.input_tokens / 1_000_000) * self.pricing["input_token_cost_per_m"]
        output_cost: float = (self.output_tokens / 1_000_000) * self.pricing["output_token_cost_per_m"]
        total_cost: float = round(input_cost + output_cost, 6)

        return {
            "duration_seconds": round(duration, 3),
            "total_tokens": self.input_tokens + self.output_tokens,
            "calculated_cost_usd": total_cost,
            "total_tool_calls": self.tool_calls_count,
        }
