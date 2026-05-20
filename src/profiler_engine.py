import json
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .utils.telemetry import TelemetryTracker


class ProfilerEngine:
    """
    Executes a suite of edge‑case scenarios, runs a mock target agent,
    gathers telemetry and writes a markdown performance matrix.
    """

    def __init__(self, config_path: str) -> None:
        """
        :param config_path: Path to the YAML matrix suite definition.
        """
        self.config_path: str = config_path
        self.scenarios: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []
        self._load_suite()

    # --------------------------------------------------------------------- #
    # Public workflow
    # --------------------------------------------------------------------- #

    def run_all(self) -> None:
        """
        Process every scenario, collect telemetry and emit a markdown report.
        The output file is created under ``results/matrix.md`` and the directory
        is created if it does not already exist.
        """
        for scenario in self.scenarios:
            outcome = self._execute_scenario(scenario)
            self.results.append(outcome)

        self._write_markdown_report()

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _load_suite(self) -> None:
        """Load the YAML configuration and store the list of scenario dicts."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            suite: Dict[str, Any] = yaml.safe_load(f) or {}
        self.scenarios = suite.get("scenarios", [])
        if not isinstance(self.scenarios, list):
            raise TypeError("`scenarios` must be a list in the YAML suite.")

    def _execute_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single scenario through a mock target‑agent interaction,
        record telemetry and return a structured result.

        :param scenario: Single scenario dictionary from the suite.
        :return: Result dict containing status, metrics and scenario identifiers.
        """
        tracker = TelemetryTracker()
        tracker.start()

        payload: Any = scenario.get("input_payload", "")
        # Simulate token consumption based on payload size
        input_token_cnt: int = len(json.dumps(payload))
        # Fixed output token count for deterministic telemetry
        output_token_cnt: int = 10
        tracker.log_tokens(input_token_cnt, output_token_cnt)
        tracker.log_tool_call()                     # one mock tool invocation
        tracker.stop()

        metrics: Dict[str, Any] = tracker.calculate_metrics()

        # Basic validation of the generated output schema (optional)
        expected_schema: str = scenario.get("expected_output_schema", "")
        status: str = "PASS"
        if expected_schema == "json" and not self._is_json_serialisable(metrics):
            status = "FAIL"
        # Respect timeout defined in the suite
        timeout: int = scenario.get("timeout_seconds", 30)
        if metrics["duration_seconds"] > timeout:
            status = "FAIL (timeout)"

        return {
            "scenario_id": scenario["id"],
            "status": status,
            "metrics": metrics,
        }

    @staticmethod
    def _is_json_serialisable(obj: Any) -> bool:
        """Utility to check if ``obj`` can be JSON‑encoded."""
        try:
            json.dumps(obj)
            return True
        except (TypeError, OverflowError):
            return False

    def _write_markdown_report(self) -> None:
        """
        Render the collected results as a markdown table and write it to
        ``results/matrix.md``. The target directory is created automatically.
        """
        report_dir: Path = Path("results")
        report_dir.mkdir(parents=True, exist_ok=True)   # <-- ensures path exists
        report_path: Path = report_dir / "matrix.md"

        header: str = (
            "| Scenario ID | Status | Duration (s) | Token Volume | Cost (USD) | Tool Interactions |\n"
            "|-------------|--------|--------------|--------------|------------|-------------------|\n"
        )
        rows: List[str] = []
        for entry in self.results:
            m = entry["metrics"]
            row = (
                f"| **{entry['scenario_id']}** "
                f"| {entry['status']} "
                f"| {m['duration_seconds']}s "
                f"| {m['total_tokens']} "
                f"| ${m['calculated_cost_usd']:.6f} "
                f"| {m['total_tool_calls']} |"
            )
            rows.append(row)

        markdown: str = "# 📊 Agent Performance & Profiling Matrix\n\n"
        markdown += header + "\n".join(rows) + "\n"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"Performance matrix written to {report_path}")


if __name__ == "__main__":
    # Simple entry point for direct execution
    engine = ProfilerEngine("config/matrix_suite.yaml")
    engine.run_all()
