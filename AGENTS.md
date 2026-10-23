# CST-Agentic Instructions

## Project Overview

CST-Agentic develops an agentic system to control CST Studio Suite, run
simulations and analyze results. The intended application architecture has a CST
controller using MCP and an analysis agent with dedicated tools. This direction
does not establish that every capability is implemented or verified.

## Environment
- **Python** >= 3.12
- **Package Manager**: uv (all Python commands must use `uv run`)

Use Windows PowerShell 5.1-compatible commands unless another shell version has
been verified. Use the tool's working-directory parameter when available and
commands appropriate to the verified shell. Do not assume Bash syntax or
PowerShell 7 operators are available. Use temporary scripts for experiments with
complex quoting. Keep them outside the intended change set.

Check command failures explicitly. In PowerShell, inspect `$LASTEXITCODE` after
native commands and handle cmdlet errors. Stop dependent commands after failure
so a later success cannot hide it. All Python invocations, including temporary
scripts and SDK inspection, must use `uv run`.

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


## Credential Handling

- Never print secret values through reads, searches, shell commands, errors or
  recorded evidence. Choose commands and inspected paths before execution so
  secret-bearing output is never emitted.
- Inspect configuration using variable names and presence or missing status.
  Do not dump environment variables or credential-bearing configuration.

## Agent skills

### Issue tracker

Specs and tickets live in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context glossary and ADR layout. See `docs/agents/domain.md`.
