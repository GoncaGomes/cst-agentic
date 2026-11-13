# Project source language

First-party identifiers, comments, docstrings, prompts, exceptions, terminal
messages, authored fixture replies and documentation use English. Ordinary user
input, model replies and external tool data retain their original language and
contents; this convention is not a runtime translation layer.

External protocol keys, canonical MCP names/schemas and public interfaces remain
compatible. Renaming a public or persisted identifier requires an explicit
compatible migration.
