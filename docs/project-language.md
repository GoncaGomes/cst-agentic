# Project source language

First-party identifiers, comments, docstrings, prompts, exceptions, terminal
messages, authored fixture replies and documentation use English. This is a
source-language convention, not a runtime translation layer: ordinary user input,
model replies and external tool data retain their original language and contents.
External protocol keys, canonical MCP names/schemas and public interfaces remain
compatible; renaming a public or persisted identifier requires an explicit
compatible migration.

## Audit scope and result (2026-10-28)

The tracked application (`src/cst_agentic/`), tests/helpers, canonical schema
fixtures, root documentation, `docs/`, project metadata and CI workflow were
audited for Portuguese vocabulary and text, including ASCII identifiers. No
Portuguese production identifiers, application-authored messages or first-party
documentation were found. The Portuguese scenario text and scripted replies in
`tests/test_model_led_project.py` were translated to English with their matching
assertions. No public identifier or persisted key needed migration.

Two deliberately Portuguese user inputs in
`test_original_message_can_launch_without_intent_response_or_project` remain
explicitly labelled test data. They prove that the coordinator passes ordinary
non-English input unchanged without requiring English command wording, an intent
declaration or a translation stage. They are not application messages to translate.
Unicode engineering symbols are also test data, not Portuguese source vocabulary.

The audit excludes credentials and credential-bearing local configuration,
generated dependency/skill lockfiles, caches, virtual environments, Git history,
local evidence, the preserved old checkout and externally maintained agent skills.
None were rewritten. This source cleanup does not establish model behavior,
endpoint acceptance or native CST correctness.
