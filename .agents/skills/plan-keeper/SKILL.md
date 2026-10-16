---
name: plan-keeper
description: Maintain a concise PLAN.md of branch milestones and their main contracts. Use for project direction and evidenced progress, not commit-level task specifications.
---

# Plan Keeper

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Gather context

1. Read AGENTS.md and the existing PLAN.md, if present.
2. Read relevant repository documentation and only the tasks needed for current progress.
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

The primary planner owns this skill. Delegate technical investigation and task
specifications to subplanner, which uses task-planning. Pass the selected milestone
contract and relevant references. Keep implementation instructions in tasks.

## Create or update the plan

Maintain these sections:

- Objective and boundaries.
- Milestones, each representing one coherent branch deliverable.
- Current work, with task references.
- Next steps, ordered by dependency and priority.
- Decisions and blockers.
- Completed work, with references to detailed evidence.

Preserve useful existing structure rather than rewriting the plan unnecessarily.

For each milestone, record compactly:
- A stable identifier, title and branch name. A name does not mean a branch exists.
- The main contract: observable outcome, important scope boundaries, public
  interfaces or safety constraints when material, and completion checks.
- Dependencies and links to prepared tasks. Do not elaborate the future backlog.
- Separate implementation, verification, review and integration states.

Use a short table or a few lines per milestone, whichever is easier to read.
Choose branch names consistent with repository conventions and user direction.
Preserve historical branch names. Do not create or rename branches through this skill.

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

- Target about 80 lines or fewer and normally under 700 words. This is a writing
  target, not a model context setting. Preserve essential contracts when condensing.
- Link to task files for specifications and implementation evidence.
- Avoid copying logs, full review reports or detailed command output.
- Replace completed detail with a concise summary and references.
- Avoid per-file instructions, commit checklists, repeated decisions and diaries.
- Put the current task, blocker and next action in a few lines. Read the linked
  task only when its details matter, especially when briefing a Qwen role.
- Keep the next actionable step explicit.
- Apply AGENTS.md's investigation and continuation rules when reconciling resumed work.

## Handoff

Report:
- What changed in PLAN.md.
- What evidence supports progress updates.
- Which decisions or blockers remain.
- The next recommended action.

Do not modify application code or perform Git mutations.
