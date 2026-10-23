# Issue tracker: GitHub

Specs and tickets live in GitHub Issues. Use the `gh` CLI for tracker operations.

## Repository selection

Run commands from this repository. Confirm the selected GitHub repository
before making remote changes. Ask the user if selection is missing or ambiguous.

Missing CLI access, authentication, or permissions are blockers to report,
not reasons to silently switch trackers.

## Common operations

- Publish a spec or ticket: `gh issue create --title "..." --body-file <path>`.
- Read an issue: `gh issue view <number> --json number,title,body,labels,comments`.
- List issues: `gh issue list --state open --json number,title,labels,assignees`.
- Comment: `gh issue comment <number> --body-file <path>`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Close an issue: `gh issue close <number>`.

For multiline bodies, use UTF-8 files outside the intended change set.
Use PowerShell-compatible commands and check each command's result.

## Parent and blocking relationships

Use native GitHub sub-issues for parent-child relationships. Retrieve an issue's
database ID with `gh api repos/<owner>/<repo>/issues/<number> --jq .id`.

Add a child with:

```text
gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues -F sub_issue_id=<child-database-id>
```

Add a blocking relationship with:

```text
gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-database-id>
```

Database IDs are not issue numbers or node IDs.

If native relationships are unavailable, use `Part of #<parent>` and
`Blocked by: #<blocker>` in issue bodies, with a child task list in the parent.
Distinguish unsupported features from authentication or request failures.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Wayfinding operations

- Map: a parent issue labelled `wayfinder:map`.
- Decision tickets: child issues labelled `wayfinder:research`,
  `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- Ensure the required wayfinder labels exist before publishing.
- Wayfinder issues carry wayfinder labels, not triage-state labels.
- Frontier: open, unassigned children whose blockers are all closed.
  Enumerate all relevant children and check their dependencies.
- Claim: assign the selected ticket with `gh issue edit <number> --add-assignee "@me"`.
- Resolve: post a resolution comment, close the ticket, and add a short linked
  summary to the map's Decisions so far.
- Link supporting artifacts from tickets rather than duplicating them in the map.
