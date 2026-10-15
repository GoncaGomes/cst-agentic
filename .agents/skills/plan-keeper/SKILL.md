---
name: plan-keeper
description: Create, update or reconcile PLAN.md when establishing project direction, resuming work, recording confirmed progress or preparing the next development step. Use for project state and milestones, not detailed task specification.
---

# Plan Keeper

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Gather context

1. Read AGENTS.md and the existing PLAN.md, if present.
2. Read the active task and relevant repository documentation.
3. Inspect repository state and available evidence before changing progress.
4. Identify contradictions, missing information and outdated assumptions.

## Create or update the plan

Maintain these sections:

- Objective and boundaries.
- Milestones.
- Current work, with task references.
- Next steps, ordered by dependency and priority.
- Decisions and blockers.
- Completed work, with references to detailed evidence.

Preserve useful existing structure rather than rewriting the plan unnecessarily.

For an initial plan, derive direction from the user's stated objective.
Record unresolved decisions explicitly instead of inventing requirements.

## Reconcile progress

- Distinguish intended behaviour from verified behaviour.
- Record implementation, review and integration separately.
- Do not infer integration from successful checks or a clean working tree.
- Base integration claims on confirmed Git evidence or explicit user confirmation.
- Record blockers with their cause and the next action needed.
- Preserve material decisions and reasons for abandoning an approach.

## Keep the plan compact

- Link to task files for specifications and implementation evidence.
- Avoid copying logs, full review reports or detailed command output.
- Replace completed detail with a concise summary and references.
- Keep the next actionable step explicit.

## Handoff

Report:
- What changed in PLAN.md.
- What evidence supports progress updates.
- Which decisions or blockers remain.
- The next recommended action.

Do not modify application code or perform Git mutations.