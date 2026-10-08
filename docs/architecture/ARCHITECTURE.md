# DeployOS System Architecture & Design Document

> **"Agents can reason. DeployOS decides whether they should act."**

---

## 1. Core Architectural Thesis

Most existing AI agent frameworks follow an unconstrained loop:
$$\text{User Prompt} \longrightarrow \text{LLM Reasoning} \longrightarrow \text{Direct Tool Invocation} \longrightarrow \text{Response}$$

This paradigm fails catastrophically in consequential enterprise environments where third-party APIs experience intermittent latency, records change asynchronously, customer emails contain prompt injection attacks, and operations carry financial liability.

**DeployOS introduces strict separation of Reasoning Authority from Execution Authority:**
```
                     AGENT REASONING LAYER (Probabilistic)
                                      │
                                      ▼
                        STRUCTURED ACTION PROPOSAL
       (action, target, parameters, hash, state_version, evidence_ids)
                                      │
                                      ▼
                   DETERMINISTIC POLICY ENGINE (Strict)
       ┌──────────────────────────────┼──────────────────────────────┐
       ▼                              ▼                              ▼
    EXECUTE                         REVIEW                         REJECT
(Autonomous)                 (Human-in-the-Loop)             (Violation/Stale)
       │                              │                              │
       │                              ▼                              ▼
       │                    Cryptographic Binding               Audit Trace
       │                       (action_hash)                         │
       └──────────────────────────────┼──────────────────────────────┘
                                      │
                                      ▼
                     CONSEQUENTIAL TOOL EXECUTION
                    (Idempotency Key Verification)
                                      │
                                      ▼
                         STATE CHANGE & AUDIT LOG
```

---

## 2. High-Level System Components

### 2.1 API Gateway & Orchestrator (`apps/api`)
- Fast, asynchronous REST and WebSocket gateway built on FastAPI.
- Ingests inbound operational events (webhooks, email threads, customer tickets, API calls).
- Tracks distributed traces, OpenTelemetry metrics, and health telemetry.

### 2.2 Agent Runtime & Durable Engine (`services/agent_runtime`)
- **Durable Execution Engine**: Built to run alongside Temporal Python SDK or embedded durable runner.
- **State Versioning**: Monitors entity revision counts (`state_version`). If an underlying CRM record mutates between observation and proposal, the proposal is strictly aborted.
- **Multi-tiered Memory**: Isolates working memory (active execution), episodic memory (step timeline), semantic memory (ground-truth SOP policies), and procedural memory.

### 2.3 Deterministic Policy Engine (`services/policy_engine`)
Evaluates proposals against mathematical, policy, and cryptographic rules:
1. **`StateFreshnessPolicy`**: Validates proposal observation timestamp and entity versions.
2. **`TrustBoundaryPolicy`**: Enforces that mutations are grounded in trusted database evidence (`INTERNAL_DATABASE`, `SYSTEM_POLICY`), not untrusted external attachments (`CUSTOMER_EMAIL`, `UPLOADED_PDF`).
3. **`DuplicateActionPolicy`**: Checks if action was already processed or transaction was already refunded.
4. **`TransactionVerificationPolicy`**: Verifies transaction existence and charge amounts in payment records.
5. **`RefundLimitPolicy`**: Authorizes autonomous refunds up to $100.00 USD; strictly routes refunds >$100.00 USD to Human Review.

### 2.4 Cryptographic Action Hash & Approval Binding
When a proposal is escalated to Human Review:
$$\text{action\_hash} = \text{SHA-256}\Big(\text{canonical\_json}(\text{action}, \text{target}, \text{parameters}, \text{state\_version}, \text{org\_id})\Big)$$
Human approval binds **strictly and immutably** to this hash. If parameters (e.g. amount or recipient) are tampered with before execution, authorization is invalidated immediately (`ACTION_TAMPERING_DETECTED`).

### 2.5 Tool Infrastructure & Idempotency (`packages/tools`)
- Common tool abstraction across 4 consequence tiers:
  - **Tier 0**: Read-only queries (autonomous).
  - **Tier 1**: Reversible writes (CRM notes, ticket creation).
  - **Tier 2**: External communication (emails, Slack messages).
  - **Tier 3**: Financial mutations & deletions (refunds, subscriptions).
- Every consequential mutation requires a durable idempotency key:
  $$\text{idempotency\_key} = \text{wf\_}\langle \text{id} \rangle : \langle \text{action} \rangle : \langle \text{target} \rangle : \langle \text{hash}_{16} \rangle$$
  Repeated executions return cached outcomes without duplicate mutations.

### 2.6 Evaluation, Benchmark & Replay Suite (`services/eval_engine`)
- **Trajectory Evaluator**: Assesses the entire execution chain (goal $\to$ retrieval $\to$ reasoning $\to$ tool selection $\to$ policy verdict $\to$ outcome).
- **Composite Agent Reliability Score**: 
  $$\text{Score} = (0.30 \cdot \text{Success}) + (0.15 \cdot \text{ToolAcc}) + (0.10 \cdot \text{ArgAcc}) + (0.25 \cdot \text{Safety}) + (0.10 \cdot \text{Recovery}) + (0.10 \cdot \text{Escalation})$$
- **Historical Replay**: Re-runs past trajectories against candidate models or prompt versions, computing side-by-side execution diffs.
