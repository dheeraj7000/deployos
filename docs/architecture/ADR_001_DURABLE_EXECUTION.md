# ADR 001: Durable Workflow Engine Selection

## Status
Accepted

## Context
AI agent workflows operating in enterprise environments can run for seconds, hours, or days (e.g. awaiting an operator approval or asynchronous payment settlement). If a process restarts, a node crashes, or a container scales down, an in-memory execution loop is permanently lost, leaving the system in a corrupt or indeterminate state.

## Decision
We implement workflow orchestration using **Temporal Python SDK** primitives and an embedded durable runtime (`DurableWorkflowEngine`).
- Workflows are defined as deterministic state machines with activity checkpoints.
- Step activities support automatic exponential retries on transient errors (503s, socket timeouts).
- Suspended workflows (e.g. awaiting human approval) persist state safely without maintaining active server resources.

## Consequences
- Workflows survive process crashes, deployments, and restarts without data loss.
- In-flight operations can be inspected step-by-step with full activity history.
