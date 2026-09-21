# AgentGuard Repository Instructions

## Product

AgentGuard is an open-source developer tool for finding potentially important
AI-agent behaviors that are not adequately represented in the agent's existing
eval or regression-test suite.

The initial product is a local CLI scanner.

The core question AgentGuard should answer is:

> What behaviors in this agent appear insufficiently tested?

AgentGuard is not currently a governance platform, observability platform,
production-monitoring platform, or release-certification system.

---

## V0 Product Goal

V0 must prove two things:

1. AgentGuard can identify genuinely useful gaps in an existing agent eval suite.
2. Those findings cause engineers to add or modify tests.

The most important product signal is therefore:

> Did an AgentGuard finding cause an engineer to change the eval suite?

Optimize for useful findings, explainability, and precision rather than
maximum recall.

---

## V0 Inputs

AgentGuard should initially support analysis of:

- Python source files
- agent prompts
- tool definitions
- agent/workflow definitions
- LangGraph workflows where practical
- pytest-based tests/evals
- JSONL eval datasets
- optional AgentGuard configuration

Requirements documents, PRDs, policies, production traces, and external SaaS
integrations are not required for V0.

---

## V0 Outputs

A scan should produce a set of behaviors and findings.

Each detected behavior should have:

- stable behavior ID
- human-readable description
- behavior type
- source file
- source evidence
- relevant tool/workflow/prompt if applicable

Each coverage finding should have:

- stable finding ID
- associated behavior ID
- coverage status
- confidence
- matched evals, if any
- evidence explaining why the match was made
- evidence explaining why the behavior was flagged
- suggested missing test scenario where useful

Supported coverage statuses:

- `covered`
- `partially_covered`
- `potentially_uncovered`

Do not use language implying mathematical or absolute certainty.

Prefer:

> Potentially uncovered

Do not say:

> Definitely not tested

unless the result is based on a deterministic rule that genuinely supports
that conclusion.

---

## Coverage Semantics

For V0:

### Covered

At least one existing eval materially exercises the behavior and verifies the
expected outcome.

### Partially Covered

The behavior is exercised, but an important condition, branch, failure mode,
or expected outcome is not verified.

### Potentially Uncovered

AgentGuard found no eval that appears to materially exercise and verify the
behavior.

Do not introduce a numeric "coverage percentage" in V0.

The denominator for agent behavioral coverage is not sufficiently trustworthy
yet.

---

## Feedback Loop

Feedback and resolution tracking are mandatory V0 features.

Every actionable finding must support these dispositions:

- `add_eval`
- `valid_later`
- `already_covered`
- `not_relevant`
- `suppressed`

Feedback must persist locally across scans.

A future scan should attempt to determine whether a previously uncovered
finding has become covered because an eval was added or modified.

Stable finding IDs must survive:

- line-number changes
- formatting changes
- harmless whitespace changes

A materially changed behavior may create a new finding ID.

The product should support measuring:

- Valid Gap Rate
- Actionable Gap Rate
- False Positive Rate
- Resolved-by-Test Rate
- repeat scan usage

Do not require cloud telemetry for V0.

Any telemetry added later must be explicitly opt-in.

---

## Explainability

Every finding must be explainable.

A user should be able to answer:

- What behavior did AgentGuard detect?
- Where did that behavior come from?
- Which tests were considered?
- Why does AgentGuard believe coverage may be missing?
- What kind of eval might close the gap?

Prefer file paths, symbols, test names, and structured evidence over opaque
LLM-generated conclusions.

---

## Architecture Principles

Prefer small, composable modules.

Suggested responsibilities:

- `scanners/`
  - repository and file discovery

- `extractors/`
  - convert source artifacts into normalized behaviors and eval scenarios

- `matchers/`
  - map behaviors to eval scenarios

- `feedback/`
  - persist user dispositions and resolution state

- `models.py`
  - typed domain models shared across the product

- `cli.py`
  - CLI commands and presentation only

Business logic should not live directly in CLI handlers.

---

## Deterministic First

Prefer deterministic analysis before semantic/LLM analysis.

Examples:

- Python AST parsing
- function/tool discovery
- explicit exception detection
- pytest test discovery
- workflow edge extraction
- exact metadata relationships

LLMs may later assist with:

- prompt obligation extraction
- semantic behavior normalization
- behavior-to-eval matching
- suggested eval creation

LLM output must never be silently treated as objective truth.

Any LLM-backed result should include confidence and evidence.

---

## LLM Integration Rules

If an LLM integration is added:

- keep it optional
- do not make local scanning require an API key
- validate outputs with Pydantic models
- isolate model-provider code behind an interface
- make prompts testable and versioned
- handle invalid structured output explicitly
- avoid coupling core domain models to a specific model provider

Do not add additional model providers until there is a demonstrated need.

---

## Persistence

For V0, prefer the simplest reliable local persistence mechanism.

Acceptable options:

- JSON
- SQLite

Do not introduce a hosted backend or database.

Local state should live under:

`.agentguard/`

Do not commit user-specific AgentGuard state unless explicitly requested.

---

## Testing Expectations

All new behavior requires tests.

Prefer:

- focused unit tests for extraction and matching
- fixture repositories for realistic scenarios
- end-to-end CLI tests for important workflows

Important cases include:

1. behavior with matching eval
2. behavior with no matching eval
3. partially covered behavior
4. multiple evals matching one behavior
5. one eval covering multiple behaviors
6. suppressed finding
7. finding marked already covered
8. stable finding ID across whitespace changes
9. stable finding ID across line movement
10. new eval resolving a previous finding

Run before completing implementation work:

```bash
pytest
ruff check .
ruff format --check .
mypy src/agentguard
```
