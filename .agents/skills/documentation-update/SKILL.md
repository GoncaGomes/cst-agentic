---
name: documentation-update
description: Update repository documentation after behaviour, usage, configuration or structure changes. Use for README instructions, technical documentation and meaningful docstrings while keeping claims consistent with implementation evidence.
---

# Documentation Update

Resolve project paths from the repository root.
Resolve bundled skill resources from this skill's directory.

## Identify affected documentation

1. Read AGENTS.md and the assigned task.
2. Inspect the implementation changes and existing documentation.
3. Identify changes to usage, configuration, interfaces or project structure.
4. Determine which existing documents need updating.
5. Prefer updating the authoritative document over creating duplicates.

Use the approved task's Implementation approach and confirmed investigation
conclusions as context. Return material contradictions to planning under
AGENTS.md rather than silently documenting a replacement design.

## Update the README

Keep the README focused on:
- Project purpose and current capabilities.
- Necessary prerequisites and configuration.
- The shortest useful usage example.
- Important limitations.
- Links to detailed documentation when needed.

Use concise language and concrete examples.
Separate available functionality from future plans.
Include commands only when supported by the implementation.
State verification limitations when an example could not be exercised.

Do not include internal agent handoffs, implementation diaries
or extensive task evidence in the README.

## Update technical documentation and docstrings

- Explain interfaces, responsibilities and relevant architectural decisions.
- Add docstrings to public APIs and non-obvious behaviour.
- Document meaningful constraints, side effects and exceptions.
- Avoid repeating function names, type annotations or obvious code.
- Keep terminology, paths and configuration names consistent.
- Remove obsolete instructions affected by the change.

## Handle agent instructions

- Update factual project information in AGENTS.md when the task makes it outdated.
- Keep any project structure summary limited to useful directories and responsibilities.
- Treat changes to workflow rules, agent profiles or skills as configuration changes.
- Make those changes only when they belong to the agreed task.
- Report other necessary instruction changes without silently expanding scope.

## Verify consistency

- Check documented paths and configuration names against the repository.
- Check local links and referenced files.
- Exercise examples when appropriate and permitted.
- Use existing verification evidence when it covers an unchanged example.
- Ensure documentation does not claim unsupported functionality.
- Keep documentation and examples free of credentials.
- Inspect configuration through variable names and presence or missing status.
  Do not dump configuration or run examples that could emit secret-bearing errors.

## Handoff

Include in the implementation summary:
- Documentation files changed.
- The behaviour or usage change they explain.
- Examples checked and remaining limitations.

Record the evidence in the assigned task under AGENTS.md's checkpoint rules.
Independent review belongs in Review outcome and is recorded by its coordinating
agent from the supplied report, not inferred from documentation checks.

Do not create a separate documentation report by default.
Do not update PLAN.md or record integration events as part of this procedure.
