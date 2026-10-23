# Domain Docs

## Layout

Use one root `GLOSSARY.md` and root `docs/adr/` directory.

## Before exploring

Read `GLOSSARY.md` when present and ADRs relevant to the area being explored.

If these documents are absent, proceed silently. Create them through
domain-modeling as terminology and architectural decisions are resolved,
rather than scaffolding empty documents upfront.

## Vocabulary and decisions

Use glossary terminology consistently in code, tests, issues, and documentation.
Raise missing or ambiguous concepts for domain-modeling.

If a proposal conflicts with an existing ADR, identify the conflict explicitly
rather than silently overriding the decision.
