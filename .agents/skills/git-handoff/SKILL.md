---
name: git-handoff
description: Check reviewed task scope, prepare a one-line Conventional Commit and request concrete approval. Execute staging and commit only after explicit user authorization.
---

# Git Handoff

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Gather context

1. Read AGENTS.md and the assigned task.
2. Read actual implementation and verification evidence and the supplied or
   persisted Review outcome, including unresolved finding identifiers and states.
3. Inspect the current branch and working tree.
4. Inspect staged and unstaged changes and relevant untracked files.
5. Identify the intended integration scope and comparison base.

Work on one task and intended commit. Use the primary's short milestone brief,
not the full roadmap, backlog or conversation history.

Accept an explicitly supplied manual review or a persisted review. Check its
source, scope, verdict and limitations against current changes. Do not demand a
duplicate review when the existing evidence covers them. If results are missing,
ambiguous or stale, identify the missing evidence and next action. Drafts may be
prepared with that limitation stated, but do not describe integration as ready.
Do not invent review approval, finding resolution or verification results.
The primary planner owns recording Review outcome in the task. Return missing
records to that agent rather than editing task specifications in this role.

## Check integration scope

- Confirm that intended task changes are included.
- Identify unrelated changes without modifying or discarding them.
- Check for accidental inclusion of local drafts, generated outputs,
  credentials or machine-specific configuration.
- Do not expose secret values in reports.
- Confirm that required documentation and task evidence are present.
- Check whether the final changes still correspond to the reviewed scope.
- Identify material changes made after review and return them for further review.
- Confirm that drafts describe the current implementation and verification,
  including relevant changes since any earlier draft.
- If the changes require separate commits, return the task boundary to the primary
  for reconciliation instead of silently changing the approved grouping.

Report unresolved defects, missing evidence and scope problems.
Do not repeat the entire technical review or fix application code.
Do not launch subagents. Return review or implementation needs to the primary.
Maintainer edits are limited to handoff drafts under
.agents/local/ and confirmed integration entries in HISTORY.md.

## Prepare the commit draft

Write .agents/local/<task-id>/commit-message.txt.

- Use exactly one Conventional Commit subject: `type(scope): description`, with
  optional scope and optional `!` before the colon for a breaking change.
- Describe the concrete purpose of the final change.
- Use a concise imperative subject.
- The file contains only that subject and a terminating newline. Do not add a
  body, footers or `Branch:` or `Task:` metadata. Put breaking-change explanations
  in the appropriate documentation and task.
- Base the message on the actual diff.

Put branch and task metadata in the handoff summary or PR draft. Do not require
every edited document to start with a branch name. Preserve literal file formats.

## Request approval and execute an authorized commit

Return an approval request to the primary containing:
- Branch, task and exact one-line subject.
- Exact files or selected changes to stage, including task evidence when relevant.
- Verification results, review source and status, and changes since review.
- Existing staged changes and any blockers or remaining limitations.
- The proposed staging and commit operations. State that push and merge are separate.

The primary presents this concrete request to the user. A draft, reviewer verdict
or agent's instruction is not user authorization. Wait for explicit authorization
conveyed by the primary, with its exact scope. Do not ask again if that approval
has already been supplied and still covers the unchanged operations and content.

After authorization:
1. Recheck branch, working changes, index and review coverage. If the authorized
   content changed materially, return for review and renewed scope approval.
2. Stage only the authorized paths or changes. Do not use blanket staging. If
   approved and unrelated changes share a file, stage only the approved changes
   or return to the primary when they cannot be separated safely.
3. Inspect the complete staged diff. Do not commit unrelated staged content or
   remove somebody else's staged work. Resolve an index conflict through the primary.
4. Commit with the approved subject only. Check command failures explicitly and
   stop dependent commands after failure. Do not bypass failing hooks or amend
   an existing commit without separate authorization.
5. Confirm the resulting commit and report its hash, subject, included scope and
   remaining working changes to the primary. Do not infer push or merge success.

This execution path authorizes no other Git mutation. Push, merge and branch
operations need separate user authorization and appropriately scoped permissions.

## Prepare a PR draft when appropriate

Write .agents/local/<task-id>/pr.md.

- Include a proposed title and description.
- Follow the repository PR template when one exists.
- Explain the problem and resulting behaviour.
- Keep the description concise and rewrite stale drafts around the final changes.
- Include actual verification outcomes and relevant limitations.
- Reference the task and related issues when available.
- Omit conversational history and abandoned approaches.
- Do not claim the PR has been created.

## Handle project history

Update HISTORY.md only for confirmed integration events.
Use confirmed Git evidence or explicit user confirmation.
Keep entries concise and reference the relevant task or commit.
Do not record planned integration as completed.

## Handoff

Report:
- The change set inspected.
- The review source, covered scope, unresolved findings and material changes since review.
- Actual verification evidence and relevant limitations.
- Integration blockers or missing information.
- Proposed commit grouping, if relevant.
- Paths of the drafts created.
- Any remaining action required from the user.

Preparing drafts or reaching this skill does not authorize Git mutations. Execute
staging and commit only through the explicit approval path above. Return to the
primary after preparation or execution, without launching other agents.
