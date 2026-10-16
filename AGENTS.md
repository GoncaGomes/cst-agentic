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

## Project structure

```
cst-agentic
├── AGENTS.md
├── README.md
├── main.py                 # Thin CLI entry point
├── pyproject.toml
├── src/cst_agentic/        # Application package
├── tests/                  # Offline tests and test helpers
├── docs/tasks/             # Task specifications and implementation evidence
└── uv.lock
```

Use the `src` layout: keep application code in `src/cst_agentic/`, tests in
`tests/`, and root `main.py` as a thin CLI entry point. The distribution name is
`cst-agentic`. Python imports remain `cst_agentic`. Install the package with
`uv sync` using Hatchling's configured package path. Do not add `sys.path` or
`PYTHONPATH` workarounds.

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

### Roles and skill ownership

Keep the four development profiles under `.opencode/agents/` and the six skills
under `.agents/skills/`. Load a relevant skill before performing its procedure.
Profiles define role boundaries and skills contain the detailed procedures.

| Profile | Responsibility | Required skills when applicable |
| --- | --- | --- |
| `planner` | Establish direction, maintain the roadmap, investigate and prepare actionable tasks | `plan-keeper` for roadmaps, `task-planning` for task specifications |
| `implementer` | Execute the approved approach, document, verify and correct findings | `documentation-update`, `python-verification` |
| `reviewer` | Inspect actual changes and return an independent, read-only report | `code-review` before every review |
| `maintainer_git` | Check integration scope and evidence, prepare Git drafts | `git-handoff` before preparing drafts |

The planner can start from the user's objective when `PLAN.md` is missing or
empty. Keep roadmap direction and progress concise, with task links for technical
detail. Track implementation, verification, independent review and integration
as separate states supported by evidence.

Write `PLAN.md` and create or revise task specifications only with user approval.
Approval already supplied in the current conversation is sufficient for its
stated scope. Do not ask for the same approval again. Routine status,
implementation evidence, limitations and review outcome updates within an
approved task do not require separate specification approval.

Every development task needs an `Implementation approach` before it is ready for
implementation. The planner owns the technical investigation and approach. Base
it on the actual repository, installed dependencies and confirmed public APIs.
Resolve design-critical uncertainties before readiness. For an existing task
missing an adequate approach, return the affected planning work to the planner
before substantial implementation.

The implementer checks that the approved approach still fits the repository and
makes local decisions within it. Reuse recorded technical conclusions rather
than repeating broad SDK investigation. Targeted inspection and small experiments
are appropriate for implementation and debugging. Record minor justified
deviations in the task. Material gaps or changes to architecture, dependencies,
scope or public interfaces return to planning with evidence and follow the same
approval policy. Continue independent work only where that decision has no effect.

### Investigation and continuation

For planning and implementation, search for symbols before reading large modules
and inspect the smallest useful code regions. Consolidate confirmed conclusions
and useful references in the task. After repeated failures of an approach, change
method and record what was learned. End exploration when the relevant technical
questions are answered.

Run proportionate checks. Repeat successful checks only after relevant changes,
failures or unresolved concerns. At meaningful checkpoints, record completed and
active work, material decisions or deviations, blockers and the next action in
existing task sections such as `Context and dependencies`, `Implementation
approach`, `Implementation evidence` and `Remaining limitations`. Keep an
unapproved proposal in the conversation until writing it is authorized. Do not
introduce a mandatory checkpoint document.

Treat compaction as normal continuation. Resume from the recorded state and
reconcile it with current files. Accumulated token usage is not context-window
size. Do not invent deployment limits or increase configured limits merely to
delay compaction.

### Review transfer

Reviews are explicit handoffs, without an automatic chain of agents. Support
manual profile selection and reviewer delegation only when the user explicitly
requests delegation. The reviewer returns its report without editing files.

The coordinating agent, normally the implementer, records the actual supplied
report in the assigned task's `Review outcome` section. Include the review source,
reviewed scope, verdict, unresolved findings and relevant limitations. Include
dates or session references only when supplied. Keep this separate from
implementation evidence. Never invent approval or strengthen a review verdict.

In manual sessions, explicitly supply the report to the next session or persist
it before the next handoff. The maintainer can use a supplied or persisted review
and must check its coverage of current changes, including changes since review.
Missing or stale review evidence is a handoff limitation, not inferred approval.

### OpenCode selection and permissions

Project-local `opencode.jsonc` selects `implementer` for new sessions. The four
profiles remain manually selectable. Existing sessions retain their selected
agent and may require an explicit switch to `implementer` or the intended role.
Preserve model selections and provider settings when changing workflow rules.

Use OpenCode V2 `permissions` rules with `action`, `resource` and `effect`.
Edit restrictions are tool restrictions, not a complete filesystem sandbox.
Shell access can still write files and must respect the same role boundaries.

## Credential Handling

- Never print secret values through reads, searches, shell commands, errors or
  recorded evidence. Choose commands and inspected paths before execution so
  secret-bearing output is never emitted.
- Inspect configuration using variable names and presence or missing status.
  Do not dump environment variables or credential-bearing configuration.
- `.gitignore`, masking output later and restricting one tool do not protect all
  access paths. Apply these rules to every tool, shell and delegated operation.
- Do not read `.env`, authentication databases or raw chat logs for workflow
  configuration tasks. Credential rotation is separate work.

## Repository Operations

- Do not stage, commit, push, merge, or delete branches
  without explicit authorization.
- Do not overwrite unrelated uncommitted changes.
- Do not modify secrets or credentials.
- Preparing drafts does not authorize Git mutations. Update `HISTORY.md` only
  for integration events confirmed by Git evidence or explicit user confirmation.

## Documentation

- All source code and documentation must be in English.
- Documentation must describe verified behaviour.
- Do not claim unsupported functionality exists.
- Keep documentation proportional to the change.
- Use concise English without em dashes or semicolons in prose.
- Preserve formats consumed literally by commands. A commit-message file starts
  with the intended commit subject. Put branch and task metadata in a handoff
  summary or PR draft rather than prefixing every document with a branch name.
- Add docstrings to public APIs and functions with non-obvious behaviour.
- Explain relevant constraints, side effects and exceptions.
- Avoid docstrings and comments that merely repeat names or type annotations.
