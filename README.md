# AgentGuard

**Find what your agent evals aren't testing.**

AgentGuard is an open-source developer tool that scans an AI-agent repository
and identifies potentially important agent behaviors that appear to be missing
from the existing eval or regression-test suite.

## Status

AgentGuard is currently pre-alpha and under active development. The current
milestone provides the CLI and typed configuration foundation. Repository
scanning and findings are not implemented yet.

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
```

Running `agentguard` without arguments also displays help. Behavior extraction,
findings, and feedback commands will be added in later milestones.

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
