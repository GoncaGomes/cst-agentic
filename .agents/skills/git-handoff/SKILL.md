---
name: git-handoff
description: Inspect the final change set and prepare a commit message and optional pull request draft. Use after implementation and review to check integration scope, evidence and accidental file inclusion.
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

Accept an explicitly supplied manual review or a persisted review. Check its
source, scope, verdict and limitations against current changes. Do not demand a
duplicate review when the existing evidence covers them. If results are missing,
ambiguous or stale, identify the missing evidence and next action. Drafts may be
prepared with that limitation stated, but do not describe integration as ready.
Do not invent review approval, finding resolution or verification results.
The coordinating agent owns recording Review outcome in the task. Return missing
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
- Propose separate commits only when the changes have distinct purposes.

Report unresolved defects, missing evidence and scope problems.
Do not repeat the entire technical review or fix application code.
Do not launch subagents. Transfer review or implementation needs manually to the
coordinating agent or user. Maintainer edits are limited to handoff drafts under
.agents/local/ and confirmed integration entries in HISTORY.md.

## Prepare the commit draft

Write .agents/local/<task-id>/commit-message.txt.

- Follow repository commit conventions when established.
- Describe the concrete purpose of the final change.
- Use a concise imperative subject.
- The first line must be the intended commit subject, as consumed by
  `git commit -F`. Never put `Branch:`, `Task:` or other metadata before it.
- Add a body only when it explains a useful reason or consequence.
- Base the message on the actual diff.

Put branch and task metadata in the handoff summary or PR draft. Do not require
every edited document to start with a branch name. Preserve literal file formats.

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

This procedure prepares drafts and does not authorize Git mutations. Do not
stage, commit, push, merge or delete branches as part of it. Any separately
requested mutation requires explicit user authorization under AGENTS.md.
