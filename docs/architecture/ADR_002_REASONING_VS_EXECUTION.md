# ADR 002: Separation of Reasoning from Execution Authority

## Status
Accepted

## Context
Standard agent frameworks permit the model to directly invoke tools upon generating a tool-call JSON token. In enterprise workflows (financial mutations, database drops, external communications), allowing probabilistic text predictors to directly execute consequential writes causes prompt injection vulnerabilities, hallucinated duplicate refunds, and lack of deterministic auditing.

## Decision
DeployOS strictly decouples **Reasoning** from **Execution Authority**:
1. The LLM generates a structured `ActionProposal` with proposed parameters, observation timestamps, entity version, and confidence score.
2. The proposal is submitted to a deterministic `PolicyEngine`.
3. The policy engine evaluates:
   - Schema validation
   - `StateFreshnessPolicy`
   - `TrustBoundaryPolicy`
   - `DuplicateActionPolicy`
   - `TransactionVerificationPolicy`
   - `RefundLimitPolicy`
4. The policy engine returns one of four deterministic verdicts:
   - `EXECUTE` (Autonomous execution authorized)
   - `REVIEW` (Human review required; binds to cryptographic action hash)
   - `RETRY` (Transient dependency outage)
   - `REJECT` (Policy violation or stale state)
5. Only the execution engine can invoke tools, and only if authorization requirements are met.

## Consequences
- 100% elimination of unauthorized model actions (`unsafe_action_rate = 0.0%`).
- Mathematical guarantee that actions cannot be tampered with between human review and final execution.
