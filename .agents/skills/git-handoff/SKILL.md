---
name: git-handoff
description: Inspect the final change set and prepare a commit message and optional pull request draft. Use after implementation and review to check integration scope, evidence and accidental file inclusion.
---

# Git Handoff

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Gather context

1. Read AGENTS.md and the assigned task.
2. Read the implementation evidence and supplied review outcome.
3. Inspect the current branch and working tree.
4. Inspect staged and unstaged changes and relevant untracked files.
5. Identify the intended integration scope and comparison base.

If review results are unavailable, report that limitation.
Do not invent review approval or verification results.

## Check integration scope

- Confirm that intended task changes are included.
- Identify unrelated changes without modifying or discarding them.
- Check for accidental inclusion of local drafts, generated outputs,
  credentials or machine-specific configuration.
- Do not expose secret values in reports.
- Confirm that required documentation and task evidence are present.
- Check whether the final changes still correspond to the reviewed scope.
- Flag material changes made after review for further review.
- Propose separate commits only when the changes have distinct purposes.

Report unresolved defects, missing evidence and scope problems.
Do not repeat the entire technical review or fix application code.

## Prepare the commit draft

Write .agents/local/<task-id>/commit-message.txt.

- Follow repository commit conventions when established.
- Describe the concrete purpose of the final change.
- Use a concise imperative subject.
- Add a body only when it explains a useful reason or consequence.
- Base the message on the actual diff.

## Prepare a PR draft when appropriate

Write .agents/local/<task-id>/pr.md.

- Include a proposed title and description.
- Follow the repository PR template when one exists.
- Explain the problem and resulting behaviour.
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
- Integration blockers or missing information.
- Proposed commit grouping, if relevant.
- Paths of the drafts created.
- Any remaining action required from the user.

This procedure prepares drafts.
Do not stage, commit, push, merge or delete branches as part of it.