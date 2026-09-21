# AgentGuard

**Find what your agent evals aren't testing.**

AgentGuard is an open-source developer tool that scans an AI-agent repository
and identifies potentially important agent behaviors that appear to be missing
from the existing eval or regression-test suite.

## Status

AgentGuard is currently pre-alpha and under active development.

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