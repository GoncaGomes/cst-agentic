---
name: task-planning
description: Investigate an approved milestone and prepare small commit-sized tasks with affected files, technical approaches and verification. Used by subplanner before implementation approval.
---

# Task Planning

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Investigate

1. Read AGENTS.md, the assigned milestone contract and relevant dependencies.
   Consult only the necessary PLAN.md sections and existing tasks.
2. Inspect the working tree and code, configuration and documentation affected by the objective.
3. Identify existing interfaces, installed dependencies, SDK integrations and available checks.
4. Separate confirmed facts from assumptions and unresolved decisions.

The subplanner owns this investigation and the proposed technical approach. Apply
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

- Select one small, coherent change that can be implemented, verified and reviewed
  independently and delivered as one commit. A milestone normally needs several tasks.
- State included and excluded behaviour.
- Identify dependencies and blocking decisions.
- Preserve existing interfaces unless changing them is part of the objective.
- Provide an actionable implementation approach proportional to the task.
- Split the task when it contains independently deliverable changes.
- Keep the related code, meaningful tests and documentation for one outcome in
  that task. Do not separate tests just to make the implementation commit smaller.
- Prepare the next actionable tasks, not detailed instructions for every future
  milestone. Give Qwen only one task at a time.
- Aim for roughly 300-700 words of specification before evidence. If essential
  technical detail is much larger, reconsider the task boundary. Do not omit
  failure paths or confirmed API details merely to meet a word target.

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

Include the milestone identifier or approved maintenance objective, target branch,
task dependencies and proposed commit subject. A named branch may be proposed or
existing. Say which it is and do not create it as part of planning.

The commit subject is exactly one line: `type(scope): description`, with optional
scope and optional `!` before the colon for a breaking change. Use a concise
imperative description. Do not add a commit body, footers or task metadata to the
subject. Put migration details in the specification or appropriate documentation.

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

- Expected files and modules to create or modify, identifying each operation,
  responsibility and boundary. Include directly affected tests and documentation.
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

Prefer paths, symbols, confirmed signatures and short explanations to copied
modules, large SDK excerpts or repeated roadmap text. Link only dependencies that
the implementer needs. Expected files guide scope, not an arbitrary file-count limit.

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
Leave this section for the primary planner coordinating review.
It records the actual supplied review source, reviewed scope, verdict,
unresolved finding identifiers and states, and relevant limitations. Include
dates or session references only when available. Preserve prior finding states
and explain changes on re-review. Keep this distinct from implementation evidence.
An empty section is pending review, not approval. The reviewer returns its report
to the primary without editing this file. Follow AGENTS.md for review transfer.

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
- The task has one verifiable outcome and a suitable one-line commit subject.
- The primary can review the proposed approach and obtain user approval before
  implementation. Technical readiness is not self-approval by the subplanner.

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
- Proposed commit subjects, affected paths and dependency order, kept concise.

Return to the primary for validation and user approval. Do not implement, launch
subagents or record checks that have not been executed.
