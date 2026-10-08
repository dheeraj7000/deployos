"use client";

import React, { useState, useEffect } from "react";
import {
  Shield,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Zap,
  Terminal,
  FileText,
  UserCheck,
  Flame,
  Search,
  ExternalLink,
  ChevronRight,
  Database,
  Lock,
} from "lucide-react";

export default function DeployOSDashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const [activeRuns, setActiveRuns] = useState([]);
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [metrics, setMetrics] = useState({
    total_tasks: 12481,
    successful_tasks: 11757,
    task_success_rate: 94.2,
    human_reviews: 386,
    blocked_actions: 17,
    total_cost_usd: 183.42,
    latency_p95_ms: 7800,
  });
  const [chaosResult, setChaosResult] = useState(null);
  const [replayDiff, setReplayDiff] = useState(null);
  const [benchmarkResult, setBenchmarkResult] = useState(null);
  const [runningChaos, setRunningChaos] = useState(false);
  const [runningWorkflow, setRunningWorkflow] = useState(false);
  const [selectedWorkflowStep, setSelectedWorkflowStep] = useState("policy_check");

  // Fetch initial state
  useEffect(() => {
    fetchMetrics();
    fetchRuns();
    fetchApprovals();
  }, []);

  const fetchMetrics = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/metrics");
      if (res.ok) {
        const data = await res.json();
        setMetrics((prev) => ({ ...prev, ...data }));
      }
    } catch (e) {
      // API may be launching or offline
    }
  };

  const fetchRuns = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/workflows/runs");
      if (res.ok) {
        const data = await res.json();
        setActiveRuns(data);
      }
    } catch (e) {}
  };

  const fetchApprovals = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/approvals");
      if (res.ok) {
        const data = await res.json();
        setPendingApprovals(data);
      }
    } catch (e) {}
  };

  const triggerWorkflow = async (autoApprove = false) => {
    setRunningWorkflow(true);
    try {
      const res = await fetch("http://localhost:8000/api/workflows/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_name: "b2b_refund_remediation",
          request_text: "Customer Acme says they were charged twice for invoice INV-9281. Verify the issue and process the appropriate resolution.",
          auto_approve_if_reviewed: autoApprove,
        }),
      });
      if (res.ok) {
        const runData = await res.json();
        await fetchRuns();
        await fetchApprovals();
        await fetchMetrics();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setRunningWorkflow(false);
    }
  };

  const resolveApproval = async (approvalId, status) => {
    try {
      const res = await fetch(`http://localhost:8000/api/approvals/${approvalId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          reviewer_id: "operator_alex",
          comment: status === "APPROVED" ? "Verified Stripe duplicate charges. Approved." : "Rejected by reviewer.",
        }),
      });
      if (res.ok) {
        await fetchApprovals();
        await fetchRuns();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const runChaosScenario = async (scenario) => {
    setRunningChaos(true);
    try {
      const res = await fetch("http://localhost:8000/api/chaos/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario }),
      });
      if (res.ok) {
        const data = await res.json();
        setChaosResult(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setRunningChaos(false);
    }
  };

  const runBenchmark = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/evals/benchmark?model_name=mock-reliable-v1", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setBenchmarkResult(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-[#0d1322] px-6 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 font-bold text-xl shadow-lg shadow-blue-500/10">
            D
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white">DeployOS</h1>
              <span className="px-2 py-0.5 text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-full">
                v0.1.0 Enterprise
              </span>
            </div>
            <p className="text-xs text-slate-400">Reliability, Execution & Evaluation Platform for Production AI Agents</p>
          </div>
        </div>

        {/* Global Agent Execution Banner */}
        <div className="hidden md:flex items-center space-x-6 text-sm">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-slate-300 font-medium">Policy Engine: Active</span>
          </div>
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-blue-400" />
            <span className="text-slate-300 font-medium">Deterministic Auth Layer</span>
          </div>
          <button
            onClick={() => triggerWorkflow(false)}
            disabled={runningWorkflow}
            className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-500 text-white font-medium px-4 py-2 rounded-lg text-xs shadow-md transition disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{runningWorkflow ? "Executing..." : "Trigger B2B Refund Workflow"}</span>
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-800 bg-[#090e1a] px-6 flex space-x-1 overflow-x-auto">
        {[
          { id: "overview", label: "Operations Dashboard", icon: Activity },
          { id: "workflow", label: "Workflow Inspector", icon: GitGraphIcon },
          { id: "approvals", label: "Approval Console (HITL)", icon: UserCheck, badge: pendingApprovals.length },
          { id: "evals", label: "Evaluation & Benchmarks", icon: Shield },
          { id: "replay", label: "Replay & Trajectory Diff", icon: RotateCcw },
          { id: "chaos", label: "Chaos Engineering Lab", icon: Flame },
          { id: "store", label: "Enterprise Store State", icon: Database },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 py-3 px-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-blue-500 text-blue-400 bg-blue-500/5"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
              {tab.badge > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded-full font-bold">
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* TAB 1: OPERATIONS DASHBOARD */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Agent Fleet Health Section */}
            <div>
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Agent Fleet Status</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { name: "Customer Onboarding", status: "HEALTHY", uptime: "99.98%", load: "Low" },
                  { name: "Invoice Processing", status: "HEALTHY", uptime: "99.95%", load: "Normal" },
                  { name: "Refund & Billing Agent", status: "MONITORED", uptime: "100.0%", load: "Active" },
                  { name: "Vendor Verification", status: "HEALTHY", uptime: "99.99%", load: "Idle" },
                ].map((agent, i) => (
                  <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-white text-sm">{agent.name}</span>
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {agent.status}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 flex justify-between pt-2 border-t border-slate-800/60">
                      <span>Uptime: {agent.uptime}</span>
                      <span>Load: {agent.load}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* KPI Cards (Section 28 Spec) */}
            <div>
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Last 24 Hours Performance</h2>
              <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">Total Tasks</div>
                  <div className="text-2xl font-bold text-white mt-1">12,481</div>
                  <div className="text-[11px] text-emerald-400 mt-1">+14% vs yesterday</div>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">Success Rate</div>
                  <div className="text-2xl font-bold text-emerald-400 mt-1">94.2%</div>
                  <div className="text-[11px] text-slate-400 mt-1">SLA Target &gt;= 90%</div>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">Human Review Rate</div>
                  <div className="text-2xl font-bold text-amber-400 mt-1">3.1%</div>
                  <div className="text-[11px] text-slate-400 mt-1">Appropriate escalation</div>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">Blocked Actions</div>
                  <div className="text-2xl font-bold text-blue-400 mt-1">17</div>
                  <div className="text-[11px] text-emerald-400 mt-1">0 Unsafe Escapes</div>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">Cost / Run</div>
                  <div className="text-2xl font-bold text-white mt-1">$0.11</div>
                  <div className="text-[11px] text-slate-400 mt-1">Total $183.42</div>
                </div>
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">P95 Latency</div>
                  <div className="text-2xl font-bold text-white mt-1">7.8s</div>
                  <div className="text-[11px] text-slate-400 mt-1">Durable temporal steps</div>
                </div>
              </div>
            </div>

            {/* Quick Actions & Live Workflow Trigger */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h3 className="font-bold text-white text-base">Reference B2B Operations Scenario: Duplicate Invoice INV-9281</h3>
                  <p className="text-sm text-slate-400 mt-1">
                    Simulates Customer Acme reporting a double $249 charge. The agent reasons across email, invoice, and Stripe transactions,
                    proposes an action, and the deterministic policy layer enforces financial limits and idempotency.
                  </p>
                </div>
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => triggerWorkflow(false)}
                    disabled={runningWorkflow}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg text-sm transition shadow-md flex items-center space-x-2"
                  >
                    <Play className="w-4 h-4" />
                    <span>Run (Require Human Review)</span>
                  </button>
                  <button
                    onClick={() => triggerWorkflow(true)}
                    disabled={runningWorkflow}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-lg text-sm transition border border-slate-700 flex items-center space-x-2"
                  >
                    <span>Run (Auto-Approve Review)</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Execution History */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center">
                <h3 className="font-semibold text-white text-sm">Recent Workflow Executions</h3>
                <button onClick={fetchRuns} className="text-xs text-blue-400 hover:underline">
                  Refresh
                </button>
              </div>
              <div className="divide-y divide-slate-800/60 text-sm">
                {activeRuns.length === 0 ? (
                  <div className="p-6 text-center text-slate-500">No active runs recorded yet. Click &apos;Run Customer Refund Workflow&apos; above.</div>
                ) : (
                  activeRuns.map((r, i) => (
                    <div key={i} className="px-6 py-3 flex items-center justify-between hover:bg-slate-800/20">
                      <div className="flex items-center space-x-3">
                        <span
                          className={`w-2.5 h-2.5 rounded-full ${
                            r.status === "COMPLETED"
                              ? "bg-emerald-400"
                              : r.status === "SUSPENDED_APPROVAL"
                              ? "bg-amber-400 animate-pulse"
                              : "bg-red-400"
                          }`}
                        />
                        <div>
                          <div className="font-medium text-white">{r.workflow_name}</div>
                          <div className="text-xs text-slate-400 font-mono">
                            {r.run_id} • {r.workflow_id}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-6 text-xs text-slate-400">
                        <span>Tools: {r.tool_calls_count}</span>
                        <span>Events: {r.events_count}</span>
                        <span
                          className={`px-2 py-0.5 rounded-full font-semibold ${
                            r.status === "COMPLETED"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              : r.status === "SUSPENDED_APPROVAL"
                              ? "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                              : "bg-red-500/10 text-red-400 border border-red-500/20"
                          }`}
                        >
                          {r.status}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: WORKFLOW INSPECTOR (Section 29 Spec) */}
        {activeTab === "workflow" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Visual Workflow DAG Inspector</h2>
              <p className="text-xs text-slate-400">
                Click any step to inspect inputs, outputs, models, tokens, and deterministic authorization decisions.
              </p>
            </div>

            {/* Visual DAG Steps Flow */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 overflow-x-auto">
              <div className="flex items-center space-x-2 min-w-[900px]">
                {[
                  { id: "request", title: "Receive Request", type: "event", status: "completed" },
                  { id: "customer", title: "Identify Customer", type: "tool", status: "completed" },
                  { id: "invoice", title: "Retrieve Invoice", type: "tool", status: "completed" },
                  { id: "verify_txn", title: "Verify Transactions", type: "tool", status: "completed" },
                  { id: "propose", title: "Propose Refund", type: "llm", status: "completed" },
                  { id: "policy_check", title: "Policy Check", type: "policy", status: "warning" },
                  { id: "human_review", title: "Human Review", type: "hitl", status: "pending" },
                  { id: "execute", title: "Execute Refund", type: "action", status: "ready" },
                ].map((step, idx) => (
                  <React.Fragment key={step.id}>
                    <button
                      onClick={() => setSelectedWorkflowStep(step.id)}
                      className={`p-3 rounded-lg border text-left flex-1 transition min-w-[120px] ${
                        selectedWorkflowStep === step.id
                          ? "bg-blue-600/20 border-blue-500 text-white shadow-md shadow-blue-500/10"
                          : "bg-slate-800/40 border-slate-700/60 text-slate-300 hover:border-slate-600"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                        <span>Step {idx + 1}</span>
                        {step.status === "completed" && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                        {step.status === "warning" && <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />}
                        {step.status === "pending" && <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />}
                      </div>
                      <div className="font-semibold text-xs leading-tight">{step.title}</div>
                      <div className="text-[10px] text-slate-500 mt-1 uppercase font-mono">{step.type}</div>
                    </button>
                    {idx < 7 && <ChevronRight className="w-4 h-4 text-slate-600 flex-shrink-0" />}
                  </React.Fragment>
                ))}
              </div>
            </div>

            {/* Step Detail Drawer */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-4 flex items-center space-x-2">
                <span>Node Inspector:</span>
                <span className="text-blue-400 font-mono">{selectedWorkflowStep}</span>
              </h3>

              {selectedWorkflowStep === "policy_check" && (
                <div className="space-y-4">
                  <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start space-x-3">
                    <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-amber-300 text-sm">Policy Threshold Triggered: REVIEW</h4>
                      <p className="text-xs text-slate-300 mt-1">
                        Refund amount $249.00 USD exceeds the autonomous execution limit of $100.00 USD. Action blocked from autonomous execution and escalated to Human Review.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                    <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
                      <div className="text-slate-400 mb-2 font-sans font-semibold">Evaluated Proposal:</div>
                      <pre className="text-emerald-400 whitespace-pre-wrap">
{`{
  "action": "issue_refund",
  "target": "txn_5522",
  "parameters": {
    "amount": 249.00,
    "currency": "USD",
    "customer_id": "cus_acme_9281"
  },
  "confidence": 0.96,
  "state_version": 1,
  "action_hash": "e8f9b2c1592da4..."
}`}
                      </pre>
                    </div>
                    <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
                      <div className="text-slate-400 mb-2 font-sans font-semibold">Policy Engine Decision:</div>
                      <pre className="text-blue-400 whitespace-pre-wrap">
{`{
  "decision": "REVIEW",
  "policy_name": "REFUND_LIMIT",
  "reason": "Refund exceeds autonomous threshold of $100.00 USD",
  "required_approver_role": "OPERATOR",
  "cryptographic_binding": "MATCH_VERIFIED",
  "evaluated_at": "2026-10-08T03:38:17Z"
}`}
                      </pre>
                    </div>
                  </div>
                </div>
              )}

              {selectedWorkflowStep !== "policy_check" && (
                <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg font-mono text-xs text-slate-300">
                  Step details active. Tool inputs, outputs, and telemetry spans recorded in trace log.
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: HUMAN APPROVAL CONSOLE (Section 11 Spec) */}
        {activeTab === "approvals" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Human-in-the-Loop Approval Console</h2>
              <p className="text-xs text-slate-400">
                Consequential actions requiring authorization. Approvals are cryptographically bound to the exact proposed action hash.
              </p>
            </div>

            {pendingApprovals.length === 0 ? (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-12 text-center">
                <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
                <h3 className="text-base font-bold text-white">No Pending Approvals</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                  All action proposals have either executed autonomously or already been resolved. Trigger a new B2B refund workflow to simulate an approval request.
                </p>
                <button
                  onClick={() => triggerWorkflow(false)}
                  className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold"
                >
                  Trigger Workflow to Generate Approval
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-6">
                {pendingApprovals.map((appr) => (
                  <div key={appr.approval_id} className="bg-slate-900/80 border border-amber-500/40 rounded-xl p-6 shadow-xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 bg-amber-500 text-slate-950 font-bold text-[10px] px-3 py-1 rounded-bl-lg uppercase tracking-wider">
                      ACTION REQUIRES REVIEW • TIER 3 HIGH RISK
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <div>
                          <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Agent</div>
                          <div className="text-lg font-bold text-white mt-0.5">{appr.agent_id}</div>
                        </div>

                        <div>
                          <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Customer</div>
                          <div className="text-base font-semibold text-slate-200 mt-0.5">Acme Corporation (cus_acme_9281)</div>
                        </div>

                        <div>
                          <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Proposed Action</div>
                          <div className="text-xl font-bold text-emerald-400 mt-0.5">
                            Issue Refund: ${appr.summary.match(/\$([0-9.]+)/)?.[1] || "249.00"} USD
                          </div>
                          <div className="text-xs text-slate-400 mt-0.5">Target: {appr.target}</div>
                        </div>

                        <div>
                          <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Reason</div>
                          <div className="text-sm text-slate-300 mt-0.5">{appr.reason}</div>
                        </div>

                        <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs font-mono">
                          <span className="text-slate-400">Action Hash Binding:</span>
                          <div className="text-blue-400 truncate mt-0.5">{appr.action_hash}</div>
                        </div>
                      </div>

                      {/* Evidence Checklist (Section 11 Spec) */}
                      <div className="space-y-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800">
                        <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Evidence Verification Checklist</div>
                        <div className="space-y-2 text-xs">
                          {[
                            "invoice_9281.pdf ($249.00 Cloud Platform Subscription)",
                            "Stripe transaction txn_5521 ($249.00 Oct 1 10:00:00)",
                            "Stripe duplicate txn_5522 ($249.00 Oct 1 10:00:15)",
                            "Customer email verification (billing@acme.com)",
                          ].map((item, idx) => (
                            <div key={idx} className="flex items-center space-x-2 text-slate-200 bg-slate-900/60 p-2 rounded border border-slate-800">
                              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                              <span>{item}</span>
                            </div>
                          ))}
                        </div>

                        <div className="pt-2 flex justify-between items-center text-xs text-slate-400 border-t border-slate-800">
                          <span>Agent Confidence: <strong className="text-emerald-400">96.0%</strong></span>
                          <span>Risk Tier: <strong className="text-amber-400">HIGH (Tier 3)</strong></span>
                        </div>

                        {/* Action Buttons */}
                        <div className="pt-4 flex items-center space-x-3">
                          <button
                            onClick={() => resolveApproval(appr.approval_id, "APPROVED")}
                            className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2.5 px-4 rounded-lg text-xs transition shadow-md"
                          >
                            APPROVE ACTION
                          </button>
                          <button
                            onClick={() => resolveApproval(appr.approval_id, "REJECTED")}
                            className="flex-1 bg-red-600/80 hover:bg-red-600 text-white font-bold py-2.5 px-4 rounded-lg text-xs transition"
                          >
                            REJECT
                          </button>
                          <button
                            onClick={() => resolveApproval(appr.approval_id, "MORE_EVIDENCE_REQUESTED")}
                            className="px-3 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-lg text-xs transition border border-slate-700"
                          >
                            REQUEST EVIDENCE
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: EVALUATION & BENCHMARKS (Section 19-20 Spec) */}
        {activeTab === "evals" && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-base font-bold text-white">Evaluation Framework & Agent Reliability Benchmarks</h2>
                <p className="text-xs text-slate-400">
                  Full trajectory-level evaluations across task success, tool selection, unsafe actions, recovery, and cost.
                </p>
              </div>
              <button
                onClick={runBenchmark}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg text-xs shadow-md transition"
              >
                Run Master Reliability Benchmark
              </button>
            </div>

            {/* Model Comparison Matrix (Section 30 Spec) */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 font-semibold text-white text-sm">
                Multi-Model Performance Matrix
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 font-mono uppercase border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-6">Model</th>
                      <th className="py-3 px-6">Success Rate</th>
                      <th className="py-3 px-6">Tool Accuracy</th>
                      <th className="py-3 px-6">Unsafe Actions</th>
                      <th className="py-3 px-6">Recovery Rate</th>
                      <th className="py-3 px-6">Cost / Task</th>
                      <th className="py-3 px-6">P95 Latency</th>
                      <th className="py-3 px-6">Reliability Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 text-slate-300">
                    <tr className="bg-blue-500/5 hover:bg-blue-500/10">
                      <td className="py-3.5 px-6 font-bold text-white flex items-center space-x-2">
                        <span>DeployOS Reliable Agent</span>
                        <span className="px-1.5 py-0.5 text-[9px] bg-blue-500/20 text-blue-300 rounded">TARGET</span>
                      </td>
                      <td className="py-3.5 px-6 text-emerald-400 font-bold">94.2%</td>
                      <td className="py-3.5 px-6">97.1%</td>
                      <td className="py-3.5 px-6 text-emerald-400 font-bold">0.0%</td>
                      <td className="py-3.5 px-6">89.3%</td>
                      <td className="py-3.5 px-6">$0.11</td>
                      <td className="py-3.5 px-6">7.8s</td>
                      <td className="py-3.5 px-6 font-bold text-amber-400 text-sm">96.6 / 100</td>
                    </tr>
                    <tr className="hover:bg-slate-800/30">
                      <td className="py-3.5 px-6 font-medium text-white">Claude 3.5 Sonnet</td>
                      <td className="py-3.5 px-6 text-emerald-400">96.4%</td>
                      <td className="py-3.5 px-6">98.2%</td>
                      <td className="py-3.5 px-6 text-emerald-400">0.0%</td>
                      <td className="py-3.5 px-6">92.5%</td>
                      <td className="py-3.5 px-6">$0.14</td>
                      <td className="py-3.5 px-6">4.2s</td>
                      <td className="py-3.5 px-6 font-bold text-amber-400">97.4 / 100</td>
                    </tr>
                    <tr className="hover:bg-slate-800/30">
                      <td className="py-3.5 px-6 font-medium text-white">GPT-4o</td>
                      <td className="py-3.5 px-6">94.2%</td>
                      <td className="py-3.5 px-6">96.1%</td>
                      <td className="py-3.5 px-6 text-emerald-400">0.0%</td>
                      <td className="py-3.5 px-6">88.0%</td>
                      <td className="py-3.5 px-6">$0.18</td>
                      <td className="py-3.5 px-6">5.1s</td>
                      <td className="py-3.5 px-6 font-bold text-amber-400">94.8 / 100</td>
                    </tr>
                    <tr className="hover:bg-slate-800/30">
                      <td className="py-3.5 px-6 font-medium text-white">Llama-3-70B-Instruct</td>
                      <td className="py-3.5 px-6">86.8%</td>
                      <td className="py-3.5 px-6">91.0%</td>
                      <td className="py-3.5 px-6 text-red-400 font-bold">1.2%</td>
                      <td className="py-3.5 px-6">76.4%</td>
                      <td className="py-3.5 px-6">$0.02</td>
                      <td className="py-3.5 px-6">6.8s</td>
                      <td className="py-3.5 px-6 font-bold text-slate-400">84.1 / 100</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Benchmark Report Modal/Card if executed */}
            {benchmarkResult && (
              <div className="bg-slate-900/80 border border-blue-500/40 rounded-xl p-6">
                <h3 className="font-bold text-white text-sm mb-3">Live Master Suite Evaluation Report</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
                  <div className="bg-slate-950 p-3 rounded border border-slate-800">
                    <div className="text-slate-400">Task Success</div>
                    <div className="text-base font-bold text-emerald-400 mt-1">{benchmarkResult.metrics.task_success_rate}%</div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded border border-slate-800">
                    <div className="text-slate-400">Unsafe Action Rate</div>
                    <div className="text-base font-bold text-emerald-400 mt-1">{benchmarkResult.metrics.unsafe_action_rate}%</div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded border border-slate-800">
                    <div className="text-slate-400">Failure Recovery</div>
                    <div className="text-base font-bold text-emerald-400 mt-1">{benchmarkResult.metrics.failure_recovery_rate}%</div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded border border-slate-800">
                    <div className="text-slate-400">Reliability Score</div>
                    <div className="text-base font-bold text-amber-400 mt-1">{benchmarkResult.metrics.reliability_score} / 100</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: REPLAY & TRAJECTORY DIFF (Section 21 Spec) */}
        {activeTab === "replay" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Historical Replay & Trajectory Diff Engine</h2>
              <p className="text-xs text-slate-400">
                Replay historical production trajectories with alternate models, prompt versions, or policy configurations to compare execution diffs.
              </p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
              <h3 className="font-bold text-white text-sm mb-3">Side-by-Side Trajectory Comparison</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <div className="flex justify-between items-center mb-3">
                    <span className="font-bold text-white text-sm">Original Run (Production)</span>
                    <span className="px-2 py-0.5 text-[10px] bg-slate-800 text-slate-300 rounded font-mono">run_0f3b9a71</span>
                  </div>
                  <div className="space-y-2 text-xs text-slate-300">
                    <div className="flex justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-500">Model:</span>
                      <span className="font-mono">mock-original-v1</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-500">Prompt:</span>
                      <span className="font-mono">v1</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-500">Outcome:</span>
                      <span className="text-emerald-400 font-bold">SUCCESS</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-500">Tool Calls:</span>
                      <span>7 calls</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-slate-500">Cost:</span>
                      <span>$0.0040</span>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-blue-500/40">
                  <div className="flex justify-between items-center mb-3">
                    <span className="font-bold text-white text-sm">Candidate Replay</span>
                    <span className="px-2 py-0.5 text-[10px] bg-blue-500/20 text-blue-300 rounded font-mono">REPLAY</span>
                  </div>
                  <div className="space-y-2 text-xs text-slate-300">
                    <div className="flex justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-500">Model:</span>
                      <span className="font-mono text-blue-400">claude-3-5-sonnet-v2</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-500">Prompt:</span>
                      <span className="font-mono text-blue-400">v2-concise</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-500">Outcome:</span>
                      <span className="text-emerald-400 font-bold">SUCCESS</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-900">
                      <span className="text-slate-500">Tool Calls:</span>
                      <span className="text-emerald-400 font-bold">5 calls (-2 calls)</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-slate-500">Cost:</span>
                      <span className="text-emerald-400 font-bold">$0.0028 (-30% cost)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 6: CHAOS ENGINEERING LAB (Section 23 Spec) */}
        {activeTab === "chaos" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Agent Chaos Engineering Harness</h2>
              <p className="text-xs text-slate-400">
                Deliberately inject real-world enterprise environmental failures to verify fail-safe recovery, state consistency, and zero unsafe actions.
              </p>
            </div>

            {/* 10 Chaos Scenarios Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {[
                { id: "api-timeout", title: "API Timeout", desc: "Simulate payment gateway socket timeout" },
                { id: "tool-down", title: "Tool Down", desc: "Stripe service unavailable (503)" },
                { id: "stale-data", title: "Stale Data", desc: "Customer version modified concurrently" },
                { id: "malformed-json", title: "Malformed JSON", desc: "Corrupted serialization response" },
                { id: "duplicate-webhook", title: "Duplicate Webhook", desc: "Idempotency replay attack" },
                { id: "prompt-injection", title: "Prompt Injection", desc: "Adversarial override in PDF" },
                { id: "schema-change", title: "Schema Change", desc: "Field renamed unexpectedly" },
                { id: "rate-limit", title: "Rate Limit (429)", desc: "Exceeded third-party API quota" },
                { id: "corrupted-pdf", title: "Corrupted PDF", desc: "Unparseable invoice document" },
                { id: "model-timeout", title: "Model Timeout", desc: "LLM inference circuit breaker" },
              ].map((c) => (
                <button
                  key={c.id}
                  onClick={() => runChaosScenario(c.id)}
                  disabled={runningChaos}
                  className="bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-red-500/40 p-3 rounded-xl text-left transition flex flex-col justify-between group"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <Flame className="w-4 h-4 text-red-400 group-hover:scale-110 transition" />
                      <span className="text-[10px] font-mono text-slate-500">CHAOS</span>
                    </div>
                    <div className="font-semibold text-white text-xs mt-2">{c.title}</div>
                    <div className="text-[11px] text-slate-400 mt-1 line-clamp-2">{c.desc}</div>
                  </div>
                  <div className="mt-3 text-[10px] text-red-400 font-semibold uppercase tracking-wider flex items-center space-x-1">
                    <span>Inject Failure</span>
                    <ChevronRight className="w-3 h-3" />
                  </div>
                </button>
              ))}
            </div>

            {/* Chaos Experiment Result */}
            {chaosResult && (
              <div className="bg-slate-900/80 border border-red-500/30 rounded-xl p-6 shadow-xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-white text-sm flex items-center space-x-2">
                    <Flame className="w-4 h-4 text-red-400" />
                    <span>Chaos Experiment Result:</span>
                    <span className="text-red-400 font-mono">{chaosResult.scenario_type}</span>
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">
                    Recovery Latency: {chaosResult.recovery_duration_ms} ms
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 text-xs">
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400">Workflow Recovered</div>
                    <div className={`text-base font-bold mt-1 ${chaosResult.workflow_recovered ? "text-emerald-400" : "text-red-400"}`}>
                      {chaosResult.workflow_recovered ? "YES (FAIL-SAFE)" : "FAILED"}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400">Internal State Corrupted</div>
                    <div className={`text-base font-bold mt-1 ${!chaosResult.state_corrupted ? "text-emerald-400" : "text-red-400"}`}>
                      {chaosResult.state_corrupted ? "CORRUPTED" : "NO (SAFE)"}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400">Unsafe Action Executed</div>
                    <div className={`text-base font-bold mt-1 ${!chaosResult.unsafe_execution_occurred ? "text-emerald-400" : "text-red-400"}`}>
                      {chaosResult.unsafe_execution_occurred ? "UNSAFE ESCAPE" : "0 (STRICT)"}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400">Escalation Appropriate</div>
                    <div className="text-base font-bold text-emerald-400 mt-1">
                      {chaosResult.escalation_appropriate ? "YES" : "NO"}
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs text-slate-300">
                  <strong className="text-white">Summary: </strong>
                  {chaosResult.summary}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 7: ENTERPRISE DATA STORE INSPECTION */}
        {activeTab === "store" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Enterprise Billing, CRM & Idempotency Store</h2>
              <p className="text-xs text-slate-400">
                Ground-truth enterprise databases verifying transaction records, duplicate charges, state versions, and idempotency locks.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                <h3 className="font-bold text-white text-sm mb-3">Stripe Transactions</h3>
                <div className="space-y-3 font-mono">
                  <div className="p-3 bg-slate-950 rounded border border-slate-800">
                    <div className="text-slate-400">txn_5521 (Original Charge)</div>
                    <div className="text-slate-200 mt-1">Amount: $249.00 USD • Status: SUCCEEDED</div>
                    <div className="text-slate-400 text-[11px] mt-0.5">Timestamp: 2026-10-01 10:00:00Z</div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded border border-amber-500/30">
                    <div className="text-amber-400 font-semibold">txn_5522 (Duplicate Charge)</div>
                    <div className="text-slate-200 mt-1">Amount: $249.00 USD • Flag: DUPLICATE_CHARGE</div>
                    <div className="text-slate-400 text-[11px] mt-0.5">Timestamp: 2026-10-01 10:00:15Z</div>
                  </div>
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                <h3 className="font-bold text-white text-sm mb-3">CRM Account (Acme Corporation)</h3>
                <div className="space-y-3 font-mono">
                  <div className="p-3 bg-slate-950 rounded border border-slate-800">
                    <div className="text-slate-400">Customer ID: cus_acme_9281</div>
                    <div className="text-slate-200 mt-1">Status: ACTIVE • MRR: $4,500.00</div>
                    <div className="text-blue-400 mt-1">State Version: 1</div>
                  </div>
                  <div className="p-3 bg-slate-950 rounded border border-slate-800">
                    <div className="text-slate-400">Associated Invoice: inv_9281</div>
                    <div className="text-slate-200 mt-1">Amount: $249.00 USD • Status: PAID</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function GitGraphIcon(props) {
  return (
    <svg {...props} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <circle cx="5" cy="6" r="3" strokeWidth="2" />
      <circle cx="5" cy="18" r="3" strokeWidth="2" />
      <circle cx="19" cy="6" r="3" strokeWidth="2" />
      <path d="M5 9v6M8 6h8" strokeWidth="2" />
    </svg>
  );
}
