# AgentMedic 🩺

**AgentMedic** is an engineering-grade diagnostic framework designed to subject autonomous AI agents to synthetic, high-pressure validation scenarios. It automates the detection of regressions, monitors token/cost overhead, and validates agentic tool-use reliability within isolated environments.

## 🏗️ Architectural Overview
AgentMedic is built for **production-ready agentic systems** where performance stability and structural integrity are non-negotiable.

- **Isolation Engine:** Executes target agents as independent subprocesses, preventing memory leaks or state contamination from bleeding into the host orchestrator.
- **Observability Hooks:** Implements OpenTelemetry-style structured logging to capture state transitions, latency, and tool interaction telemetry.
- **Delta Analysis:** Maintains a persistent historical baseline, automatically flagging performance regressions (duration or token inflation) against previous runs.
- **Structural Enforcement:** Validates agent output against strictly defined schemas (JSON/Markdown) to ensure predictable downstream integration.

- agentmedic/
├── config/              # Environment and threshold specifications
│   ├── env.yaml         # Sensitive keys and system constraints
│   └── metrics.yaml     # Baseline performance thresholds
├── src/                 # Core engine logic
│   ├── core/            # Sub-process orchestration & lifecycle management
│   ├── telemetry/       # Data collection, logging, and state snapshots
│   └── analysis/        # Delta Analysis and regression logic
├── tests/               # Unit tests for the harness itself
├── assets/              # Visualization samples and architecture diagrams
├── requirements.txt     # Pin-down dependencies
└── main.py              # CLI entry point for executing test batches

## 📊 Performance Matrix (Example)
The framework generates a scannable performance matrix for every execution suite:

| Scenario ID | Status | Duration | Token Volume | Cost (USD) | Tool Interactions | Observations |
|---|---|---|---|---|---|---|
| **SCEN_001_DIRTY_INPUT** | `PASS` | 1.4s (±0.0%) | 1800 (±0.0%) | $0.009960 | 1 | N/A |
| **SCEN_002_TOOL_FAILURE** | `FAIL` | 2.1s (+5.2%) | 1220 (+2.1%) | $0.008700 | 2 | Runtime Exit Code 2 |

## 🚀 Quick Start

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
