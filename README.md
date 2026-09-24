# AgentGuard

**Find what your agent evals aren't testing.**

AgentGuard is an open-source developer tool that scans an AI-agent repository
and identifies potentially important agent behaviors that appear to be missing
from the existing eval or regression-test suite.

## Status

AgentGuard is currently pre-alpha and under active development. The current
milestone provides repository discovery plus deterministic eval and behavior
extraction, behavior-to-eval matching, curated findings, and repository-local
feedback and lifecycle persistence.

## Installation

AgentGuard requires Python 3.12 or newer. To install the project for local
development:

```bash
python -m pip install -e ".[dev]"
```

The installed CLI supports repository artifact discovery, help, and version
output:

```bash
agentguard --help
agentguard --version
agentguard scan path/to/repository
agentguard findings --repository path/to/repository
agentguard feedback <finding-id> add_eval --repository path/to/repository
agentguard confirm-impact <finding-id> --repository path/to/repository
```

Running `agentguard` without arguments also displays help.

The scan currently discovers repository artifacts and statically extracts
pytest-style tests and supported JSONL eval scenarios. It never imports target
modules or executes target tests. Eval IDs are stable across formatting,
whitespace, and line movement because they derive from the repository-relative
file and test symbol, or from the JSONL metadata name/input. File moves, symbol
renames, duplicate JSONL identities, and major test restructuring may change or
limit identity in V0.

Behavior extraction uses Python's AST and currently recognizes conservative,
explicit patterns:

- functions decorated with `@tool`, qualified `@*.tool`, or `@function_tool`
- local functions in literal tool lists and `bind_tools([...])` calls
- declared tool arguments, explicit raises, and explicit failure returns
- conditional tool branches with a visible return, raise, escalation, or handoff
- literal LangGraph `add_edge` and `add_conditional_edges` calls on a graph
  statically assigned from `StateGraph(...)`

Prompt files remain discovery artifacts. Natural-language prompt obligations are
deferred because V0 has no deterministic rule precise enough to interpret them.
Behavior IDs derive from a versioned structural identity containing the
repository-relative path, symbol or graph, behavior type, normalized condition,
and action. Separate AST fingerprints detect material source changes. IDs survive
formatting and line movement, but may change after file or symbol renames,
condition rewrites, or action changes.

Try the deterministic example repository with:

```bash
agentguard scan examples/refund_agent
```

Matching first retrieves candidate evals through indexes of referenced symbols,
expected exceptions, action names, literal values, and normalized identity
terms. It then applies behavior-specific deterministic rules. `covered` requires
evidence that an eval exercises the behavior and explicitly verifies its outcome;
subject overlap without exact outcome evidence is `partially_covered`. A JSONL
scenario without `expected` cannot establish covered status. Incomplete upstream
analysis produces an unavailable assessment instead of treating missing evidence
as a potentially uncovered behavior.

The matcher does not use embeddings, semantic similarity, or prompt-derived
behaviors. Aliases, indirect calls, dynamic values, fixtures, parametrization,
and semantically equivalent wording may therefore be missed.

Complete scans select a conservative set of high-confidence actionable findings
and store them under the scanned repository's `.agentguard/agentguard.db` SQLite
database. Repeated scans retain stable finding IDs and feedback history. A
finding is resolved only when a later complete scan finds verified coverage;
disappearance becomes `no_longer_observed`, and incomplete scans preserve the
prior state.

Supported feedback dispositions are `add_eval`, `valid_later`,
`already_covered`, `not_relevant`, and `suppressed`. Feedback never resolves a
finding by itself. `add_eval` records intent, while `confirm-impact` separately
records an explicit statement that AgentGuard influenced an eval change.

## Configuration

The scan command reads an optional `agentguard.toml` from the repository root.
The configuration loader validates it without importing or executing repository
code.

```toml
include = ["**/*.py", "**/*.txt", "**/*.md", "**/*.jsonl"]
exclude = ["**/.git/**", "**/.venv/**", "**/node_modules/**"]
```

When the file is absent, AgentGuard uses defaults covering Python, text,
Markdown, and JSONL artifacts while excluding common generated and local-state
directories. Unknown settings and invalid field types are rejected.

## V0 Goal

Given an agent repository containing prompts, tools, workflows, and evals,
AgentGuard will identify:

- detected agent behaviors
- behaviors covered by existing evals
- partially covered behaviors
- potentially uncovered behaviors
- evidence supporting each finding
- suggested missing eval scenarios

AgentGuard will also track whether engineers act on findings by adding or
modifying evals.

## Philosophy

AgentGuard does not attempt to certify that an agent is safe or production-ready.

Its initial job is much narrower:

> Help engineers discover important behaviors they may not be testing.

## Development checks

```bash
pytest
ruff check .
ruff format --check .
mypy src/agentguard
```
