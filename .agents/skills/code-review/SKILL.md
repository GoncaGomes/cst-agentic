---
name: code-review
description: Review a specified set of code or documentation changes against task requirements and project instructions. Use to identify defects, regressions, unmet acceptance criteria and verification gaps before integration.
---

# Code Review

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Establish the review scope

1. Read AGENTS.md and the assigned task.
   Use the primary's short milestone brief. Do not load the whole roadmap,
   backlog or implementation chat unless a concrete dependency requires it.
2. Identify the requested comparison: working changes, a commit or a branch.
3. Identify the comparison base, including the current HEAD when reviewing
   working changes. State which task and paths are covered.
4. Include relevant staged, unstaged and untracked files when reviewing working changes.
5. Read available implementation evidence and previous findings.
6. For re-review, retain the original finding identifiers and triggering scenarios.

Clarify missing scope when it prevents a meaningful review.
Do not assume unrelated local changes belong to the task.

## Inspect the changes

- Read the actual diff and relevant surrounding code.
- Read in-scope untracked files, which are absent from the normal tracked diff.
- Follow affected callers, data flow and error paths.
- Check acceptance criteria and applicable project constraints.
- Inspect resource cleanup, state changes and external interactions where relevant.
- Check that documentation and examples match the implementation.
- Evaluate whether verification exercises the claimed behaviour.
- Distinguish checks without CST, MCP integration and actual CST execution.
- Identify incorrect task assumptions without rewriting the task.

Implementation summaries and passing tests support inspection. Neither passing
tests nor absence of findings proves correctness.

## Verify suspected defects

- Establish a concrete triggering scenario.
- Inspect existing checks or run focused checks compatible with read-only operation.
- Separate observed failures from conclusions based on code inspection.
- Describe uncertainty when evidence is incomplete.
- Do not change source files, tests or documentation.
- Do not use shell commands to bypass the read-only role or mutate external state.
- Respect the task's authorization for external operations.

## Report findings

Report actionable defects introduced or exposed by the changes.

For each finding, provide:
- A stable identifier such as R1 or R2. Keep it across corrections and re-review.
- Severity.
- Acceptance blocking: yes or no, with a reason separate from severity.
- The affected requirement or acceptance criterion. Identify an incorrect task
  assumption explicitly when it is the source of the problem.
- File and the smallest useful line range.
- Triggering scenario.
- Incorrect behaviour and its impact.
- Supporting evidence or reproduction steps.
- State: open, resolved or superseded, with the reason and relevant evidence.

A confirmed violation of a mandatory acceptance criterion is blocking regardless
of severity. Explain any uncertainty rather than asserting an unconfirmed defect.

Do not report stylistic preferences as defects.
Keep useful optional suggestions separate and brief.

## Handoff

Return:
1. Review scope and comparison base.
2. Findings and their states, ordered by severity. Keep optional improvements separate.
3. Checks executed and their outcomes.
4. Unverified acceptance criteria or remaining uncertainty.
5. Whether blocking findings remain.
6. The next required action, such as correction, further review or Git preparation.

If no defects are found, state that explicitly.
Do not present absence of findings as proof of correctness.

On re-review, revisit every original triggering scenario and relevant effects.
Mark each previous identifier resolved, open or superseded, with a reason.
Do not drop a finding because the nearby code changed or a different test passed.
For superseded findings, explain the changed requirement or replacement finding.
Use new identifiers for newly discovered defects.

Return the report to the primary in the conversation. Keep it compact, while
preserving each finding's trigger, evidence and required resolution.
Do not edit the task, create report files or modify Git state. The primary planner
records the supplied outcome in Review outcome under AGENTS.md. Do not launch
implementer or Git roles. State only the verdict justified by the inspected
evidence, without implying integration approval.
