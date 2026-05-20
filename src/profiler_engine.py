iimport os
import sys
import yaml
import json
import subprocess
from typing import List, Dict, Any, Optional
from src.utils.telemetry import TelemetryTracker

class ProfilerEngine:
    def __init__(self, config_path: str, history_path: str = ".profiler_history.json") -> None:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration profile matrix missing at: {config_path}")
            
        with open(config_path, "r") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)
            
        self.tracker: TelemetryTracker = TelemetryTracker()
        self.history_path: str = history_path
        self.history: Dict[str, Dict[str, Any]] = self._load_history()
        self.results: List[Dict[str, Any]] = []
        
        # Regression thresholds (percentage increase allowed before flagging)
        self.duration_threshold_pct: float = 20.0
        self.token_threshold_pct: float = 15.0

    def _load_history(self) -> Dict[str, Dict[str, Any]]:
        """Loads historical profiling telemetry from local state file."""
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_history(self) -> None:
        """Persists updated moving averages back to the local state file."""
        with open(self.history_path, "w") as f:
            json.dump(self.history, f, indent=2)

    def _calculate_delta(self, current: float, baseline: Optional[float]) -> Dict[str, Any]:
        """Computes percentage variance and formats tracking string."""
        if baseline is None or baseline == 0:
            return {"pct": 0.0, "string": "(--)"}
        
        diff = current - baseline
        pct = (diff / baseline) * 100.0
        
        if abs(pct) < 1.0:
            return {"pct": pct, "string": "±0.0%"}
        
        sign = "+" if pct > 0 else ""
        return {"pct": pct, "string": f"{sign}{pct:.1f}%"}

    def validate_output_format(self, output: str, expected_schema: str) -> bool:
        """Checks if the agent's output structurally conforms to requirements."""
        clean_output = output.strip()
        if expected_schema.lower() == "json":
            try:
                json.loads(clean_output)
                return True
            except json.JSONDecodeError:
                return False
        elif expected_schema.lower() == "markdown":
            return clean_output.startswith("#") or "|\n" in clean_output or "```" in clean_output
        return True

    def execute_suite(self) -> None:
        target_agent: str = self.config.get("suite_meta", {}).get("target_agent_path", "")
        
        for scenario in self.config["scenarios"]:
            scenario_id: str = scenario["id"]
            timeout: int = scenario["timeout_seconds"]
            expected_schema: str = scenario["expected_output_schema"]
            
            print(f"🚀 Running profiling matrix for: {scenario_id}")
            self.tracker.reset()
            self.tracker.start()
            
            self.tracker.emit_otel_log(scenario_id, "INIT", f"Starting evaluation for {scenario_id}")
            
            env_env = os.environ.copy()
            env_env["AGENT_INPUT_PAYLOAD"] = scenario["input_payload"]
            
            status = "PASS"
            failure_reason = ""
            agent_stdout = ""

            try:
                process = subprocess.run(
                    [sys.executable, target_agent],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env_env
                )
                
                agent_stdout = process.stdout
                
                for line in agent_stdout.splitlines():
                    if "[METRIC_TOKENS]" in line:
                        try:
                            token_data = json.loads(line.split("[METRIC_TOKENS]")[1].strip())
                            self.tracker.log_tokens(token_data.get("input", 0), token_data.get("output", 0))
                        except Exception:
                            pass
                    elif "[METRIC_TOOL]" in line:
                        self.tracker.log_tool_call()
                
                if not self.validate_output_format(agent_stdout, expected_schema):
                    status = "FAIL"
                    failure_reason = f"Output structural validation failed. Expected: {expected_schema} format."
                    self.tracker.emit_otel_log(scenario_id, "VALIDATION_ERROR", failure_reason)
                
                if process.returncode != 0:
                    status = "FAIL"
                    failure_reason = f"Subprocess exited with non-zero exit code: {process.returncode}"
                    self.tracker.emit_otel_log(scenario_id, "RUNTIME_ERROR", failure_reason)

            except subprocess.TimeoutExpired:
                status = "FAIL"
                failure_reason = f"Execution exceeded threshold of {timeout}s"
                self.tracker.emit_otel_log(scenario_id, "TIMEOUT", failure_reason)
            except Exception as e:
                status = "FAIL"
                failure_reason = f"Engine orchestration failure: {str(e)}"
                self.tracker.emit_otel_log(scenario_id, "CRITICAL_EXCEPTION", failure_reason)
            
            self.tracker.stop()
            metrics = self.tracker.calculate_metrics()
            
            # Historical Delta Comparison Logic
            baseline = self.history.get(scenario_id)
            duration_delta = self._calculate_delta(metrics["duration_seconds"], baseline.get("duration_seconds") if baseline else None)
            token_delta = self._calculate_delta(metrics["total_tokens"], baseline.get("total_tokens") if baseline else None)
            
            # Evaluate performance regressions if previous run passed perfectly
            if status == "PASS" and baseline:
                if duration_delta["pct"] > self.duration_threshold_pct:
                    status = "REGRESSION"
                    failure_reason = f"Execution speed degraded by {duration_delta['string']}"
                elif token_delta["pct"] > self.token_threshold_pct:
                    status = "REGRESSION"
                    failure_reason = f"Token consumption inflated by {token_delta['string']}"

            # Only update history baseline if the run passes cleanly without regression
            if status == "PASS":
                self.history[scenario_id] = {
                    "duration_seconds": metrics["duration_seconds"],
                    "total_tokens": metrics["total_tokens"],
                    "calculated_cost_usd": metrics["calculated_cost_usd"]
                }
            
            self.results.append({
                "id": scenario_id,
                "metrics": metrics,
                "status": status,
                "reason": failure_reason if status in ["FAIL", "REGRESSION"] else "N/A",
                "deltas": {
                    "duration": duration_delta["string"],
                    "tokens": token_delta["string"]
                }
            })
            
            self.tracker.emit_otel_log(scenario_id, "COMPLETE", f"Finished scenario {scenario_id} with status {status}")
            
        self._save_history()
        self.generate_markdown_report()

    def generate_markdown_report(self) -> None:
        os.makedirs("results", exist_ok=True)
        report_path = "results/matrix.md"
        
        markdown = "# 📊 Agent Performance & Profiling Matrix\n\n"
        markdown += "| Scenario ID | Status | Duration | Token Volume | Cost (USD) | Tool Interactions | Observations / Failures |\n"
        markdown += "|---|---|---|---|---|---|---|\n"
        
        for res in self.results:
            m = res["metrics"]
            d = res["deltas"]
            
            # Format visual markers based on regression status
            duration_display = f"{m['duration_seconds']}s (`{d['duration']}`)" if d["duration"] != "(--)" else f"{m['duration_seconds']}s"
            token_display = f"{m['total_tokens']} (`{d['tokens']}`)" if d["tokens"] != "(--)" else f"{m['total_tokens']}"
            
            markdown += (
                f"| **{res['id']}** | `{res['status']}` | {duration_display} | "
                f"{token_display} | ${m['calculated_cost_usd']:.6f} | "
                f"{m['total_tool_calls']} | {res['reason']} |\n"
            )
            
        with open(report_path, "w") as f:
            f.write(markdown)
        print(f"\n[SUCCESS] Baseline profile matrix exported to {report_path}")

if __name__ == "__main__":
    profiler = ProfilerEngine("config/matrix_suite.yaml")
    profiler.execute_suite()