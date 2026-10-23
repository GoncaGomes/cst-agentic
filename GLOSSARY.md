# CST-Agentic

Language for conversational CST modeling and simulation work.

## Language

**CST Controller**:
The user-facing agent responsible for interpreting modeling requests and directing CST project work.
_Avoid_: Main agent

**Instruction-following mode**:
A restricted CST Controller role in which the user supplies engineering choices. The Controller still inspects, clarifies, executes supported authorized instructions, and reports evidence.

**Controller session**:
One run of the CST Controller, potentially spanning multiple user tasks. Finishing or interrupting a user task does not by itself end the Controller session.

**Results Analyst**:
The specialist responsible for interpreting simulation results and producing evidence-backed analyses and reports.
_Avoid_: Report agent

**Parameterized model**:
A CST model whose geometry or simulation settings depend on named design parameters, allowing those features to be changed through the existing parameter definitions.

**User task**:
A CST modeling or simulation outcome requested by the user, which may be an isolated action or a multi-step workflow. Clarifications and intermediate operations serving that outcome belong to the same task.

**Task authorization**:
The user's permission to pursue a requested outcome in the selected project within agreed changes and consequences. It is distinct from the availability of an individual tool.

**Decision memory**:
The small set of key project-specific choices explicitly confirmed by the user and retained for reference across Controller conversations. Remembered decisions are neither verified project facts nor continuing task authorization.

**Task interruption**:
The user's withdrawal of permission to continue a user task. It does not itself undo completed changes or stop a simulation run.

**Human reconciliation**:
The user's inspection and resolution of uncertain CST work to establish what changed and what remains active. The reported findings are human-provided evidence, not independent Controller observations.

**Selected project**:
The independently identified live CST project explicitly designated as the target of a user task. An offline file reference is not a selected project.

**Project overview**:
A broad account of an existing CST project's inspectable contents and setup, with explicit gaps. It is not an exhaustive verification of every feature or a substitute for inspecting the details relevant to an edit.

**Project units**:
The effective unit system configured in a CST project, distinct from the units requested by the user or suggested in a tool description.

**Stored parameter expression**:
The definition retained by CST for a named design parameter, which may reference other parameters. Its evaluated numerical value is not the expression itself.

**Verified project fact**:
An observation about an identified CST project supported by current evidence with known provenance. A conversational assertion alone is not a verified project fact.

**Simulation run**:
An individual solver execution associated with an identified CST project and the model and simulation setup being simulated. Observing that execution end is distinct from establishing solver success.

**Simulation stop**:
A request to end an identified simulation run before its natural completion. The request is distinct from evidence that the solver has stopped.

**Result applicability**:
The evidenced relationship between simulation results and a project's current model and simulation setup. The presence of results alone does not establish their applicability.

**Model rebuild**:
CST's application of current project definitions to dependent model features. Storing a parameter definition is distinct from successfully rebuilding those features.

**Saved project snapshot**:
The persisted version of a CST project, which may differ from its live, unsaved state.
