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

Keep the five development profiles under `.opencode/agents/` and the six skills
under `.agents/skills/`. Load a relevant skill before performing its procedure.
Profiles define role boundaries and skills contain the detailed procedures.

| Profile | Responsibility | Required skills when applicable |
| --- | --- | --- |
| `planner` | Primary contact, roadmap owner, task validator and sole dispatcher | `plan-keeper` |
| `subplanner` | Investigate a milestone and prepare small commit-sized tasks | `task-planning` |
| `implementer` | Execute the approved approach, document, verify and correct findings | `documentation-update`, `python-verification` |
| `reviewer` | Inspect actual changes and return an independent, read-only report | `code-review` before every review |
| `maintainer_git` | Check final scope and review coverage, prepare drafts and request commit approval | `git-handoff` |

The planner uses `openai/gpt-6.1-sol` and delegates technical planning to the
subplanner using the same model. The three execution roles use
`skynet/qwen3.8-27b`. Only the planner launches subagents. Children return results
to it instead of launching siblings or nested agents.

The planner can start from the user's objective when `PLAN.md` is missing or
empty. Each milestone represents one coherent branch deliverable and names its
branch, main contract, dependencies and task links. Keep the roadmap concise,
normally around 80 lines or fewer, with technical detail in tasks. Track
implementation, verification, independent review and integration separately.

Write `PLAN.md` and create or revise task specifications only with user approval.
Approval already supplied in the current conversation is sufficient for its
stated scope. Do not ask for the same approval again. Routine status,
implementation evidence, limitations and review outcome updates within an
approved task do not require separate specification approval.

The subplanner prepares only the next actionable tasks. Each task targets one
small, coherent, independently verifiable commit with a one-line Conventional
Commit subject. Include expected created or modified files, acceptance criteria,
an actionable `Implementation approach` and checks. Keep directly related code,
tests and documentation together. Split independent outcomes into separate tasks.

The subplanner owns technical investigation based on actual code, installed
dependencies and confirmed public APIs. Resolve design-critical uncertainty
before readiness. The primary validates the proposal and presents it to the user
for approval before implementation. An adequate approach and scope approval are
both required. Return missing or stale planning to the primary before affected
implementation. Do not retroactively invent approval for existing tasks.

The implementer checks that the approved approach still fits the repository and
makes local decisions within it. Reuse recorded technical conclusions rather
than repeating broad SDK investigation. Targeted inspection and small experiments
are appropriate for implementation and debugging. Record minor justified
deviations in the task. Material gaps or changes to architecture, dependencies,
scope or public interfaces return to planning with evidence and follow the same
approval policy. Continue independent work only where that decision has no effect.

### Context, investigation and continuation

Qwen roles work on one task at a time. The primary supplies the task path, a short
milestone contract, branch and comparison base, necessary references and the
expected result. Read the current task and relevant code, not the whole roadmap,
all tasks or raw chat history. Expand context only for a concrete dependency or
unresolved question. Keep handoffs and evidence concise, with paths and symbols
instead of copied modules, SDK source or successful command logs.

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

### Dispatch and review transfer

After task approval, the planner dispatches implementation, independent review,
corrections and Git preparation without asking for permission at every handoff.
Dispatch sequentially in a shared checkout. Do not mix unfinished tasks in one
review or intended commit. Scope changes follow the planning approval policy.

The reviewer returns a read-only report to the primary. The primary records the
actual report in the task's `Review outcome`, including source, reviewed scope and
base, verdict, finding identifiers and states, and relevant limitations. Include
dates or session references only when supplied. Never invent or strengthen a
review verdict. The implementer owns implementation and verification evidence.

Return blocking findings to the implementer, then re-review the corrections with
the original findings. After two unsuccessful correction rounds, the primary
reassesses the task, findings and approach before dispatching more corrections.
Escalate material design gaps immediately. The primary adjudicates disagreements
and examines sensitive changes involving credentials, CST mutations or recovery.

The Git manager checks that the supplied or persisted review covers current
changes. Missing or stale evidence is a handoff limitation, not approval. Manual
review reports may be supplied to the primary and recorded without duplicate
review when their coverage is sufficient. Only explicit user authorization
permits staging and committing the prepared scope.

### OpenCode selection and permissions

Project-local `opencode.jsonc` selects `planner` and GPT-6.1 Sol for new sessions.
The other four profiles are subagents. Existing sessions retain their selected
agent and model, so select the planner and its model explicitly when resuming.
Preserve provider definitions, credentials and model context limits. GPT-6.1 Sol
tool calling requires a compatible Responses API route. Configuration alone
does not verify authentication or runtime model routing.

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
- NEVER read `.env`, authentication databases or raw chat logs for workflow
  configuration tasks. Credential rotation is separate work.

## Repository Operations

- Do not stage, commit, push, merge, or delete branches
  without explicit authorization.
- Only `maintainer_git` performs authorized staging and commits in the delegated
  workflow. Before approval, present the branch, one-line Conventional Commit
  subject, exact changes, checks and review status through the primary. Approval
  covers that concrete scope. Push, merge and branch operations require their
  own authorization. Never stage unrelated work or use a blanket add operation.
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
