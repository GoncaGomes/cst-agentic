# CST-Agentic Instructions

## Project Overview

CST-Agentic is a codebase for an agentic system capable of controlling CST Studio Suite, run simulations and perform result analysis.

The intended architecture is comprised of two agents:
 1-  CST controller agent - with the use of an MCP 
 2-  Analysis agent - with access to tools


## Environment
- **Python** >= 3.12
- **Package Manager**: uv (all Python commands must use `uv run`)


## Project structure

```
cst-agentic
├── AGENTS.md
├── README.md
├── main.py
├── pyproject.toml
└── uv.lock
```

## Engineering Principles

- Prefer simple, maintainable solutions.
- Respect existing architectural boundaries.
- Preserve public interfaces unless explicitly instructed otherwise.
- Avoid unnecessary abstractions and dependencies.
- Use explicit types and domain models when useful.
- Keep implementation changes focused.

## Development Workflow

- Inspect relevant code before modifying it.
- For nontrivial changes, propose a plan first.
- Prefer small, independently verifiable changes.
- Do not change unrelated files.
- Do not suppress failures or weaken tests.
- Verify changes using the available project checks.
- Report what was tested and what remains unverified.

## Repository Operations

- Do not commit, push, merge, or delete branches
  without explicit authorization.
- Do not overwrite unrelated uncommitted changes.
- Do not modify secrets or credentials.

## Documentation

- All source code and documentation must be in English.
- Documentation must describe verified behaviour.
- Do not claim unsupported functionality exists.
- Keep documentation proportional to the change.
- Add docstrings to public APIs and functions with non-obvious behaviour.
- Explain relevant constraints, side effects and exceptions.
- Avoid docstrings and comments that merely repeat names or type annotations
