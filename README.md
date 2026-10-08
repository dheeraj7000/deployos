# DeployOS

### Production infrastructure for reliable AI agents.

> **Agents can reason. DeployOS decides whether they should act.**

DeployOS provides:
- **Durable agent workflows** (Temporal SDK & embedded checkpointed runner)
- **Deterministic execution policies** (`EXECUTE`, `REVIEW`, `RETRY`, `REJECT`)
- **Human approvals** (Cryptographically bound to exact action parameter hashes)
- **MCP / tool infrastructure** (Tier 0–3 consequence classifications & idempotency keys)
- **Trajectory-level evaluation** (Task success, tool accuracy, recovery rate, cost, latency)
- **Replay & regression testing** (Historical run replay with candidate models & prompt versions)
- **Observability** (OpenTelemetry spans, structured JSON logs, metrics)
- **Chaos testing** (10-scenario failure injection harness)
- **Prompt-injection defenses** (Trust boundary classifications & lexical scanners)
- **Multi-model benchmarking** (Claude 3.5 Sonnet, GPT-4o, Gemini, Llama-3, local models)

---

## Architecture Overview

```
                   USER / WEBHOOK / INBOUND EMAIL
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ DeployOS API Gateway  │
                     │       (FastAPI)       │
                     └───────────┬───────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ Durable Workflow      │
                     │ Engine (Temporal SDK) │
                     └───────────┬───────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │     Agent Runtime     │
                     └───────────┬───────────┘
                                 │
                   ┌─────────────┼─────────────┐
                   ▼             ▼             ▼
               Retrieval     Reasoning     Tool Layer
                   │             │             │
                   │             │             ▼
                   │             │          MCP / API
                   │             │             │
                   └─────────────┼─────────────┘
                                 ▼
                          ACTION PROPOSAL
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ Deterministic Policy  │
                     │        Engine         │
                     └───────────┬───────────┘
                                 │
                   ┌─────────────┼─────────────┐
                   ▼             ▼             ▼
                EXECUTE       REVIEW        REJECT
                   │             │
                   │             ▼
                   │       Human Approval
                   │      (Action Hash)
                   │             │
                   └──────────┬──┘
                              ▼
                      Tool Execution
                  (Idempotency Key Check)
                              ▼
                     Outcome Verification
                              ▼
                    Audit / Telemetry (OTel)
```

---

## Core Capabilities

### 1. Separation of Reasoning from Execution Authority
Instead of allowing an LLM to directly execute actions when generating tokens, DeployOS requires the model to produce a structured `ActionProposal`. The deterministic policy layer evaluates the proposal against:
- **`StateFreshnessPolicy`**: Checks if entity state changed concurrently or proposal expired.
- **`TrustBoundaryPolicy`**: Prevents untrusted external customer text (email/PDF) from granting authorization without database verification.
- **`DuplicateActionPolicy`**: Enforces idempotency and prevents double-refunds or duplicate charges.
- **`TransactionVerificationPolicy`**: Verifies transaction existence in Stripe/ERP.
- **`RefundLimitPolicy`**: Authorizes autonomous execution $\le \$100.00$; routes $>\$100.00$ to Human Review.

### 2. Cryptographic Human Approval Binding
When an action is flagged for `REVIEW`, DeployOS computes:
$$\text{action\_hash} = \text{SHA-256}\Big(\text{canonical}(\text{action}, \text{target}, \text{parameters}, \text{state\_version}, \text{org\_id})\Big)$$
Human review binds strictly to this hash. If an attacker or bug tampers with the parameters between review and execution, authorization is automatically invalidated.

### 3. Tool Consequence Tiers & Idempotency
- **Tier 0 (Read-Only)**: `get_customer`, `get_invoice`, `get_payment`, `search_documents`.
- **Tier 1 (Reversible Writes)**: `update_crm`, `create_support_ticket`.
- **Tier 2 (External Communication)**: `send_email`, `send_slack_message`.
- **Tier 3 (Financial / Destructive)**: `issue_refund`, `cancel_subscription`.

Every consequential tool call generates a durable idempotency key:
`wf_<workflow_id>:<action>:<target>:<hash_prefix>`

---

## Agent Reliability Benchmark

Run the master evaluation benchmark across the 10 standard reliability scenarios:

```bash
deployos eval --suite master --model mock-reliable-v1
```

```text
      DeployOS Reliability Report — mock-reliable-v1       
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Metric                  ┃ Score / Value ┃ Target / SLA  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Task Success            │ 90.0%         │ >= 90%        │
│ Correct Tool Usage      │ 100.0%        │ >= 95%        │
│ Argument Accuracy       │ 100.0%        │ >= 95%        │
│ Retrieval Precision     │ 100.0%        │ >= 90%        │
│ Unsafe Execution        │ 0.0%          │ 0.0% (STRICT) │
│ Failure Recovery        │ 100.0%        │ >= 85%        │
│ Appropriate Escalation  │ 96.0%         │ >= 90%        │
│ P50 Latency             │ 0.0 ms        │ < 1500 ms     │
│ P95 Latency             │ 1.7 ms        │ < 3000 ms     │
│ Average Cost / Task     │ $0.0000       │ < $0.05       │
│ Agent Reliability Score │ 96.6 / 100    │ >= 90.0       │
└─────────────────────────┴───────────────┴───────────────┘
```

---

## Agent Chaos Engineering Harness

DeployOS includes an environmental chaos harness to inject real-world enterprise failures:

```bash
# Test prompt injection defense in uploaded attachments
deployos chaos prompt-injection

# Test transient API socket timeouts & backoff recovery
deployos chaos api-timeout

# Test concurrent CRM mutations & stale state rejection
deployos chaos stale-data

# Test duplicate webhook delivery & idempotency protection
deployos chaos duplicate-webhook
```

---

## Historical Run Replay

Replay past production trajectories with alternate candidate models or prompt versions:

```bash
deployos replay <run_id> --model claude-3-5-sonnet --prompt-version v2
```

---

## Quickstart

### 1. Install & Test CLI
```bash
git clone https://github.com/deployos/deployos.git
cd deployos
pip install -e .

# Run the reference B2B Customer Operations Workflow
deployos run refunds

# Run with auto-approved human review
deployos run refunds --auto-approve

# Run test suite
pytest tests/ -v
```

### 2. Start API Gateway & Control Plane Dashboard
```bash
# Terminal 1: API Gateway
deployos serve --port 8000

# Terminal 2: Next.js Control Plane
cd apps/dashboard
npm run dev
# Open http://localhost:3000 in your browser
```

### 3. Docker Compose Stack
```bash
docker-compose -f docker/docker-compose.yml up -d
```

---

## Project Structure

```
deployos/
  apps/
    api/              # FastAPI REST & WebSocket gateway
    dashboard/        # Next.js / Tailwind Control Plane UI
  services/
    agent_runtime/    # Durable engine, memory tiers, trajectory recorder
    policy_engine/    # Deterministic policy rules, cryptographic action hash
    eval_engine/      # Trajectory evaluator, reliability benchmark, replay
    chaos/            # 10-scenario Agent Chaos Harness
    incidents/        # Automated incident capture & regression test synthesizer
  packages/
    tools/            # Tier 0-3 tool abstraction, idempotency store, registry
    models/           # Provider adapters (OpenAI, Anthropic, Gemini, Mock)
    schemas/          # Pydantic schemas (proposals, decisions, traces)
    telemetry/        # OpenTelemetry spans, JSON structured logger, metrics
    security/         # Prompt injection scanner & trust boundary shield
  workflows/
    refunds/          # Reference B2B customer operations workflow (Temporal & embedded)
  evals/
    scenarios/        # 10-scenario master reliability benchmark suite
  infra/
    terraform/        # AWS ECS Fargate, RDS PostgreSQL, ElastiCache Redis
    docker/           # Dockerfiles & docker-compose.yml
  docs/
    architecture/     # System architecture diagrams & ADRs
    security/         # Security report, threat model, provenance hierarchy
```

---

## License
Apache-2.0.
