---
name: task-planning
description: Prepare or refine a development task in docs/tasks/ from an agreed objective or PLAN.md milestone. Use when defining scope, dependencies, acceptance criteria and verification before implementation.
---

# Task Planning

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Investigate

1. Read AGENTS.md, PLAN.md and relevant existing tasks.
2. Inspect the code, configuration and documentation affected by the objective.
3. Identify existing interfaces, dependencies and available checks.
4. Separate confirmed facts from assumptions and unresolved decisions.

## Bound the task

- Select a coherent change that can be implemented and reviewed independently.
- State included and excluded behaviour.
- Identify dependencies and blocking decisions.
- Preserve existing interfaces unless changing them is part of the objective.
- Specify internal design only when a confirmed constraint requires it.
- Split the task when it contains independently deliverable changes.

If missing information affects correctness or acceptance, identify the question
and mark the task as not ready for implementation.

## Write the task

Create docs/tasks/TNNN-short-description.md.
Choose the next unused identifier without renaming existing tasks.

Use these sections:

### Objective
Describe the observable outcome.

### Context and dependencies
Reference relevant files, decisions, prerequisites and unresolved questions.

### Scope
State what is included and excluded.

### Constraints
Record applicable technical and project constraints.

### Acceptance criteria
Write observable conditions that demonstrate completion.

### Verification
Describe checks appropriate to the change.
Use existing commands when available.
Identify checks that must be introduced or require external resources.

### Implementation evidence
Leave this section for the implementer to record changes, commands and outcomes.

### Remaining limitations
Leave this section for limitations confirmed during implementation.

## Check readiness

Confirm that:
- The objective and scope agree.
- Acceptance criteria can be evaluated.
- Dependencies and blocking decisions are explicit.
- Verification matches the behaviour being claimed.
- Required documentation changes are included in scope.
- Another session can begin without relying on unrecorded conversation.

## Handoff

Report:
- The task path.
- Whether it is ready for implementation.
- Blocking questions or dependencies.
- The expected implementation and verification scope.

Do not implement the task or record checks that have not been executed. Write the task file only after explicit user approval.