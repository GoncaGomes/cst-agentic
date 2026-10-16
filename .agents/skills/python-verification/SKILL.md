---
name: python-verification
description: Select and run proportionate verification for Python changes, investigate failures and record implementation evidence. Use before handing an implementation to review or after correcting review findings.
---

# Python Verification

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Identify the verification contract

1. Read AGENTS.md and the assigned task.
2. Inspect pyproject.toml, relevant checks and CI configuration for this task.
3. Identify the changed behaviour and affected interfaces.
4. Match acceptance criteria to available automated or manual checks.
5. Identify checks requiring external services or CST.

Start from the subplanner's approved Implementation approach and recorded technical
conclusions. Confirm they still match the repository without repeating broad SDK
investigation. Follow AGENTS.md's shell, working-directory, credential and
`uv run` conventions for checks and experiments.

Verify one task's outcome at a time. Do not load the whole roadmap or backlog.
Keep directly related tests and documentation with the implementation commit.

## Select proportionate checks

- Prefer existing checks that exercise the affected behaviour.
- Add or update tests when they meaningfully verify a changed contract
  or protect against a relevant regression.
- Avoid tests that merely repeat implementation details.
- Do not require new tests for every function or trivial documentation change.
- Use non-mutating lint and formatting checks when verifying.
- Broaden verification when failures or affected dependencies justify it.
- Do not add tooling or dependencies solely to produce a passing report.

## Execute and investigate

- Run the selected checks from the appropriate working directory.
- Inspect each command's failure before running dependent commands. Use a
  temporary script for complex quoting under the shared environment rules.
- Record the actual command and outcome.
- Investigate failures rather than suppressing them or weakening assertions.
- Distinguish existing failures from regressions using evidence.
- Report missing tooling or unavailable services explicitly.
- After corrections, rerun affected checks.
- Avoid repeating successful checks without a relevant change or concern.
- After repeated failures of the same method, change the investigation method
  and record the conclusion. Return material design contradictions to planning.

## Classify the evidence

Distinguish:
- Checks without external services or CST.
- Integration with an MCP server.
- Actual CST operations and result validation.

Do not describe a simulated response as successful real integration.
Respect the task's scope and authorization for external operations.
Do not claim checks that were not executed.

## Record evidence

Update the assigned task's Implementation evidence section with:
- A concise implementation summary.
- Commands executed and relevant working directories.
- Outcomes and acceptance criteria covered.
- The verification category used.
- Completed and active verification, blockers and the next action when resuming.

Update Remaining limitations with:
- Unverified behaviour and the reason.
- Unresolved failures or environmental constraints.

Keep detailed logs outside the task unless needed to explain a failure.
Never emit credentials through commands, errors or evidence. Check configuration
using variable names and presence or missing status rather than values.
Do not run inference, real MCP integration or CST merely to validate instruction-only changes.

## Handoff

Return to the primary with a concise summary:
- What was verified.
- What failed or remains unverified.
- Whether unresolved issues prevent the intended acceptance criteria.

Do not launch reviewer or claim independent review or integration. The primary
dispatches review and records its actual report separately in Review outcome.
