# cst-agentic

> Agentic System responsible for CST control and result analysis

`cst-agentic` is a Python-based Model Context Protocol (MCP) server designed to bridge Large Language Models with CST Studio Suite. It enables autonomous agents to interact with electromagnetic simulations by separating the physical execution from data analysis.

## Architecture

The system is divided into two primary agentic roles:
1. **The Implementer (Controller):** Handles the mechanical interaction with CST via the COM interface. It updates parameters, rebuilds meshes, and triggers the solver.
2. **The Reporter (Analyst):** Extracts simulation results (e.g., S-parameters, radiation patterns, mismatch efficiency) and compiles data-driven reports without hallucinating.

## Prerequisites
- Python 3.12+
- `uv` (Package manager)
- CST Studio Suite 2025 (Windows environment for COM object interaction)

