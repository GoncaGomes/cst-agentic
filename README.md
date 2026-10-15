# cst-agentic

> Agentic System responsible for CST control and result analysis

`cst-agentic` is a Python-based agentic workflow designed to bridge Large Language Models with CST Studio Suite. It enables autonomous agents to interact with electromagnetic simulations by separating the physical execution from data analysis.

## Architecture

The planned architecture will contain:
1. **The CST Controller:** Handles the mechanical interaction with a MCP-server. It updates parameters, rebuilds meshes, and triggers the solver.
2. **The Result Analyst:** Extracts simulation results (e.g., S-parameters, radiation patterns, mismatch efficiency), compiles the simulation results and generates a report.

## Prerequisites
- Python 3.12+
- `uv` (Package manager)
- CST Studio Suite 2025 (Windows environment for COM object interaction)

