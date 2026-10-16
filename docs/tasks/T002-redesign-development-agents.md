# T002: Redesign development agents

## Status

- Planning and implementation authorized by the user's approval of the five-role
  workflow in this conversation.
- Implementation: complete. Configuration verification: passed.
- Independent review: pending. Runtime delegation: unverified.
- Integration: pending. No Git mutation is authorized by this task.

## Objective

Configure a primary planner, a subplanner and three execution roles, with concise
branch milestones and small, independently verifiable tasks that each target one
commit.

## Context and dependencies

- This is workflow maintenance, not a new application roadmap milestone.
- Current branch: `feat/model-mcp-connectivity`. No branch change is requested.
- Proposed commit: `chore(agents): orchestrate small verifiable development tasks`
- OpenCode v2.0.31 is installed. Existing profiles all select
  `skynet/qwen3.8-27b`. Project `opencode.jsonc` is absent.
- The user approved central dispatch by the primary, task validation before
  implementation and explicit approval before staging and committing.
- Official V2 references: [agents](https://opencode.ai/v2/docs/agents/),
  [configuration](https://opencode.ai/v2/docs/config/) and
  [permissions](https://opencode.ai/v2/docs/permissions/).
- GPT-6.1 Sol tool calling requires the Responses API. Its authenticated OpenCode
  route has not been exercised. Preserve institutional provider configuration.

## Scope

Update `AGENTS.md`, the four existing profiles and all six workflow skills. Add
`.opencode/agents/subplanner.md` and a minimal project `opencode.jsonc`. Record
verification here. Preserve application code, dependencies, credentials,
`PLAN.md`, T001 and Git state.

## Acceptance criteria

All conditions are mandatory:

- `planner` is the default primary and both planning roles select GPT-6.1 Sol.
  The implementer, reviewer and Git manager retain institutional Qwen.
- Only the primary dispatches agents. Review corrections return through it, with
  escalation after two unsuccessful correction rounds.
- Roadmap instructions require compact branch milestones and an explicit contract.
- Task instructions require one coherent commit, an exact one-line Conventional
  Commit subject, affected files, an actionable approach and proportionate checks.
- Qwen roles receive one task and necessary references, without loading the whole
  roadmap, task backlog or conversation history.
- The primary records actual independent review reports. The Git manager checks
  current review coverage and requests approval for concrete staging and commit
  scope. Other Git mutations require separate authorization.

## Implementation approach

1. Replace the shared role, planning and review rules in `AGENTS.md`, retaining
   environment, credential, source layout and repository safeguards.
2. Refocus `.opencode/agents/planner.md` on direction and dispatch. Add
   `subplanner.md` for technical investigation and commit-sized specifications.
   Make the three execution profiles subagents that return to the primary.
3. Refine `plan-keeper` and `task-planning` with compactness targets, milestone
   contracts, task identity and just-in-time technical detail. Adapt documentation,
   verification, review and Git handoff skills to the new ownership and approvals.
4. Add project defaults using `openai/gpt-6.1-sol`, preserve provider definitions,
   and use V2 ordered permissions for dispatch and Git operations.
5. Validate skill frontmatter, local references, profile/configuration structure
   and the final diff. Inspect OpenCode discovery without inference if available.

## Verification

- Run the skill-creator validator through `uv run` for modified skills.
- Parse profile frontmatter and project JSON. Confirm models, modes, delegation
  permissions and Git approval rules against V2 documentation or discovery.
- Check references, whitespace and change scope. Do not run inference, MCP or CST
  for this instruction-only change.

## Implementation evidence

- Refocused planner on discussion, concise branch contracts and central dispatch.
  Added subplanner for technical investigation and small commit-sized task specs.
- Updated the three Qwen profiles and six existing skills. The primary owns review
  records, the implementer owns implementation evidence, and the Git manager
  prepares a concrete approval request before authorized staging and committing.
- Added project defaults and V2 permissions. Provider definitions, context limits,
  credentials, application code, dependencies, PLAN.md and T001 were not changed.
- Roadmap writing target: about 80 lines and normally under 700 words. Task
  specification target: roughly 300-700 words before evidence. Essential technical
  detail takes priority over those targets, with oversized work split into tasks.

Verification category: configuration inspection and OpenCode discovery only.
Commands ran from `C:\dev\cst-agentic`. Temporary checkers remain outside the
repository and print only selected non-sensitive metadata.

| Check | Outcome |
| --- | --- |
| `uv run --with pyyaml --with jsonschema python C:\Users\Lenovo\AppData\Local\Temp\cst-agentic-workflow-validation.py` | Passed. All six skills pass the skill-creator validator. Project JSON and five profile frontmatters pass the published OpenCode schema. Models, modes, dispatch, edit and Git permission scenarios, local links and whitespace pass. Extra packages were used only for the temporary checker. |
| `opencode debug agents` | Exit 0. All five project profiles discovered with the intended modes and configured model IDs. |
| `opencode models` | Exit 0. Both `openai/gpt-6.1-sol` and `skynet/qwen3.8-27b` are present in the catalog. This does not verify inference. |
| `uv run python C:\Users\Lenovo\AppData\Local\Temp\cst-agentic-opencode-discovery.py` | Passed scenarios against OpenCode's effective discovered permissions. Only planner may dispatch the four workers. Only maintainer_git may request staging and commit approval. Other tested Git mutations are denied. |
| `git diff --check` | Passed. New files were also checked by the temporary validator. |
| `git diff --name-only`, `git ls-files --others --exclude-standard`, `git diff --cached --quiet` | Scope contains only the approved workflow files and this task. Index remains empty. |

No inference, real MCP, CST, staging, commit or branch operation was performed.
Application tests were not rerun for this instruction-only change.

## Review outcome

Pending independent review. No independent report has been supplied.

## Remaining limitations

Runtime model routing and real delegated behavior require subsequent OpenCode
validation. Configuration inspection alone does not establish those behaviors.
Existing OpenCode sessions retain their selected agent and model. Start a new
session or explicitly select planner and GPT-6.1 Sol when continuing one.
