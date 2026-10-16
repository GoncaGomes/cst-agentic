---
name: task-planning
description: Prepare or refine a development task in docs/tasks/ from an agreed objective or PLAN.md milestone. Use when defining scope, dependencies, acceptance criteria and verification before implementation.
---

# Task Planning

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Investigate

1. Read AGENTS.md, available PLAN.md and relevant existing tasks.
2. Inspect the working tree and code, configuration and documentation affected by the objective.
3. Identify existing interfaces, installed dependencies, SDK integrations and available checks.
4. Separate confirmed facts from assumptions and unresolved decisions.

The planner owns this investigation and the proposed technical approach. Apply
AGENTS.md's focused search and continuation rules. Reuse recorded conclusions
that still match current files. Inspect installed SDK integrations and their
public APIs before proposing equivalent custom infrastructure. Confirm signatures,
versions and capabilities through relevant source or official documentation.
Never invent them or treat a proposed integration as verified behaviour.

Resolve design-critical uncertainty with focused inspection or an explicitly
scoped experiment. Define the question, boundaries and evidence sought first.
Stay within authorized side effects. Record the conclusion, useful references
and remaining uncertainty, without extensive SDK source, raw logs or conversation.
If an essential question remains unresolved, the affected task is not ready.

## Bound the task

- Select a coherent change that can be implemented and reviewed independently.
- State included and excluded behaviour.
- Identify dependencies and blocking decisions.
- Preserve existing interfaces unless changing them is part of the objective.
- Provide an actionable implementation approach proportional to the task.
- Split the task when it contains independently deliverable changes.

If missing information affects correctness or acceptance, identify the question
and mark the task as not ready for implementation.

## Write the task

Write or revise the specification only with explicit user approval under
AGENTS.md. Approval already provided in the current conversation covers its
stated scope. Do not request it again. Present an unapproved proposal in the
conversation and keep its readiness distinct from approval.

Create docs/tasks/TNNN-short-description.md.
Choose the next unused identifier without renaming existing tasks.
Preserve useful existing task structure when refining a task.

Use these sections:

### Status
State planning readiness and approval status based on available evidence.
Track implementation, verification, independent review and integration separately.

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
Identify mandatory conditions so review can determine acceptance blockers.

### Implementation approach
Required before every development task is ready for implementation. Give another
session concrete technical instructions based on the investigated repository.
Cover these points where relevant:

- Files and modules to create or modify, with their responsibilities and boundaries.
- Existing code, interfaces and patterns to reuse, with useful locations.
- Libraries and SDK integrations to use, with confirmed public API references.
  Explain why an existing capability is insufficient before proposing a new dependency.
- Public interfaces, data models and component interactions that constrain implementation.
- A sequence of small verifiable steps, including relevant documentation updates.
- Important failure paths, resource acquisition and cleanup, side effects and constraints.
- Checks demonstrating the acceptance criteria, with links to Verification as useful.

Record material decisions, reasons and confirmed investigation conclusions here
or in Context and dependencies. Distinguish approved design from open questions.
A small change may need only a few concrete bullets. Integration work must carry
enough context to implement without rediscovering the architecture.

### Verification
Describe checks appropriate to the change.
Use existing commands when available.
Identify checks that must be introduced or require external resources.

### Implementation evidence
Leave this section for the implementer to record changes, commands and outcomes.
Use it for completed and active work, minor justified deviations, blockers and
the next action at meaningful checkpoints. Keep planning conclusions in their
existing sections and apply AGENTS.md's continuation rules.

### Review outcome
Leave this section for the agent coordinating an explicitly requested review.
It records the actual supplied review source, reviewed scope, verdict,
unresolved finding identifiers and states, and relevant limitations. Include
dates or session references only when available. Preserve prior finding states
and explain changes on re-review. Keep this distinct from implementation evidence.
An empty section is pending review, not approval. The reviewer returns its report
without editing this file. Follow AGENTS.md for manual review transfer.

### Remaining limitations
Leave this section for limitations confirmed during implementation.

## Check readiness

Confirm that:
- The objective and scope agree.
- Acceptance criteria can be evaluated.
- Dependencies and blocking decisions are explicit.
- Implementation approach is present, technically actionable and consistent with
  current code, installed dependencies and confirmed APIs.
- Design-critical questions are resolved and proposed dependencies are justified.
- Verification matches the behaviour being claimed.
- Required documentation changes are included in scope.
- Another session can begin without relying on unrecorded conversation.

Do not mark a task ready with a placeholder approach or unresolved material design
decision. Reconcile material implementation discoveries under the existing approval
policy. Routine evidence and review outcome updates are not specification approval.

## Handoff

Report:
- The task path.
- Whether it is ready for implementation.
- Whether the specification is approved within the current conversation's scope.
- Blocking questions or dependencies.
- The expected implementation and verification scope.

Do not implement the task or record checks that have not been executed.
