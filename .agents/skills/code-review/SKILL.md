---
name: code-review
description: Review a specified set of code or documentation changes against task requirements and project instructions. Use to identify defects, regressions, unmet acceptance criteria and verification gaps before integration.
---

# Code Review

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Establish the review scope

1. Read AGENTS.md and the assigned task.
2. Identify the requested comparison: working changes, a commit or a branch.
3. Identify the comparison base when reviewing committed changes.
4. Include relevant staged, unstaged and untracked files when reviewing working changes.
5. Read available implementation evidence and previous findings.

Clarify missing scope when it prevents a meaningful review.
Do not assume unrelated local changes belong to the task.

## Inspect the changes

- Read the actual diff and relevant surrounding code.
- Follow affected callers, data flow and error paths.
- Check acceptance criteria and applicable project constraints.
- Inspect resource cleanup, state changes and external interactions where relevant.
- Check that documentation and examples match the implementation.
- Evaluate whether verification exercises the claimed behaviour.
- Distinguish checks without CST, MCP integration and actual CST execution.
- Identify incorrect task assumptions without rewriting the task.

## Verify suspected defects

- Establish a concrete triggering scenario.
- Inspect existing checks or run focused checks when useful and permitted.
- Separate observed failures from conclusions based on code inspection.
- Describe uncertainty when evidence is incomplete.
- Do not change source files, tests or documentation.
- Respect the task's authorization for external operations.

## Report findings

Report actionable defects introduced or exposed by the changes.

For each finding, provide:
- Severity.
- File and the smallest useful line range.
- Triggering scenario.
- Incorrect behaviour and its impact.
- Supporting evidence or reproduction steps.

Do not report stylistic preferences as defects.
Keep useful optional suggestions separate and brief.

## Handoff

Return:
1. Review scope and comparison base.
2. Findings, ordered by severity.
3. Checks executed and their outcomes.
4. Unverified acceptance criteria or remaining uncertainty.
5. Whether blocking findings remain.

If no defects are found, state that explicitly.
Do not present absence of findings as proof of correctness.

After corrections, inspect the changed areas and relevant effects.
State which previous findings are resolved or remain open.

Return the report in the conversation.
Do not create report files or modify Git state.