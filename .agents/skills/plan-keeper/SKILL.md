---
name: plan-keeper
description: Create, update or reconcile PLAN.md when establishing project direction, resuming work, recording confirmed progress or preparing the next development step. Use for project state and milestones, not detailed task specification.
---

# Plan Keeper

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Gather context

1. Read AGENTS.md and the existing PLAN.md, if present.
2. Read relevant repository documentation and existing tasks, if any.
3. Inspect repository state and available evidence before changing progress.
4. Identify contradictions, missing information and outdated assumptions.

Missing or empty PLAN.md is a valid starting point. Establish direction from the
user's objective and repository evidence. Identify objectives, boundaries,
milestones, dependencies, material decisions, unresolved questions and the next
action. Label confirmed facts, assumptions and proposed behaviour separately.
Ask only about uncertainties that materially affect direction or approval.

## Approval and ownership

The planner owns project direction and the roadmap. Propose the initial plan or
material reconciliation in the conversation before writing unless approval for
that scope is already present. Write PLAN.md only with user approval under
AGENTS.md. Do not request the same approval again.

Use task-planning to turn an approved milestone into a technically actionable
task. Keep implementation instructions and investigation conclusions in that
task rather than expanding the roadmap.

## Create or update the plan

Maintain these sections:

- Objective and boundaries.
- Milestones.
- Current work, with task references.
- Next steps, ordered by dependency and priority.
- Decisions and blockers.
- Completed work, with references to detailed evidence.

Preserve useful existing structure rather than rewriting the plan unnecessarily.

State milestone dependencies and the next actionable step explicitly. Record
unresolved decisions instead of inventing requirements. A proposed direction
does not establish implemented or verified capability.

## Reconcile progress

- Distinguish intended behaviour from verified behaviour.
- Record implementation, verification, independent review and integration separately.
- Use actual task evidence and supplied review outcomes for those distinct states.
- Do not infer integration from successful checks or a clean working tree.
- Base integration claims on confirmed Git evidence or explicit user confirmation.
- Record blockers with their cause and the next action needed.
- Preserve material decisions and reasons for abandoning an approach.

## Keep the plan compact

- Link to task files for specifications and implementation evidence.
- Avoid copying logs, full review reports or detailed command output.
- Replace completed detail with a concise summary and references.
- Keep the next actionable step explicit.
- Apply AGENTS.md's investigation and continuation rules when reconciling resumed work.

## Handoff

Report:
- What changed in PLAN.md.
- What evidence supports progress updates.
- Which decisions or blockers remain.
- The next recommended action.

Do not modify application code or perform Git mutations.
