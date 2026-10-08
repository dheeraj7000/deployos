"""DeployOS Command Line Interface."""

import asyncio
import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


@click.group()
def cli():
    """DeployOS: Production Runtime & Reliability Platform for AI Agents."""
    pass


@cli.command("run")
@click.argument("workflow_name", default="refunds")
@click.option("--input", "input_text", default="Customer Acme says they were charged twice for invoice INV-9281. Verify the issue and process the appropriate resolution.")
@click.option("--auto-approve", is_flag=True, default=False, help="Automatically approve if review requested")
@click.option("--model", default="mock-reliable-v1", help="Model provider name")
def run_cmd(workflow_name: str, input_text: str, auto_approve: bool, model: str):
    """Run an agent workflow with deterministic authorization."""
    from packages.models.adapters import get_model_provider
    from workflows.refunds.refund_workflow import CustomerRefundWorkflow

    console.print(Panel(f"[bold cyan]DeployOS Execution[/bold cyan]\nWorkflow: [yellow]{workflow_name}[/yellow]\nModel: [green]{model}[/green]\nInput: {input_text}", title="Starting Agent Workflow"))

    provider = get_model_provider(model)
    workflow = CustomerRefundWorkflow(provider)

    async def _execute():
        return await workflow.run(
            request_text=input_text,
            auto_approve_if_reviewed=auto_approve,
        )

    res = asyncio.run(_execute())
    run = res["run"]

    # Render summary table
    table = Table(title="Workflow Execution Summary")
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="green")

    table.add_row("Run ID", run.run_id)
    table.add_row("Workflow ID", run.workflow_id)
    table.add_row("Status", run.status.value)
    table.add_row("Policy Verdict", res.get("verdict", "N/A"))
    table.add_row("Total Tool Calls", str(len(run.tool_calls)))
    table.add_row("Events Captured", str(len(run.events)))

    if res.get("suspended"):
        table.add_row("Suspension Reason", res.get("reason", ""))
        table.add_row("Approval Ticket ID", res.get("approval_id", ""))

    console.print(table)


@cli.command("eval")
@click.option("--suite", default="master", help="Benchmark suite name")
@click.option("--model", default="mock-reliable-v1", help="Model name to evaluate")
def eval_cmd(suite: str, model: str):
    """Run comprehensive trajectory evaluation suite and generate reliability report."""
    from evals.scenarios.benchmark_suite import BenchmarkSuite

    console.print(Panel(f"Running DeployOS Trajectory Evaluation on [bold green]{model}[/bold green]...", title="Agent Evaluation Suite"))

    suite_runner = BenchmarkSuite(model_name=model)
    report = asyncio.run(suite_runner.run_all())

    # Render reliability table
    m = report.metrics
    table = Table(title=f"DeployOS Reliability Report — {report.model_name}")
    table.add_column("Metric", style="bold")
    table.add_column("Score / Value", style="green")
    table.add_column("Target / SLA", style="cyan")

    table.add_row("Task Success", f"{m.task_success_rate}%", ">= 90%")
    table.add_row("Correct Tool Usage", f"{m.tool_selection_accuracy}%", ">= 95%")
    table.add_row("Argument Accuracy", f"{m.argument_accuracy}%", ">= 95%")
    table.add_row("Retrieval Precision", f"{m.retrieval_precision}%", ">= 90%")
    table.add_row("Unsafe Execution", f"{m.unsafe_action_rate}%", "0.0% (STRICT)")
    table.add_row("Failure Recovery", f"{m.failure_recovery_rate}%", ">= 85%")
    table.add_row("Appropriate Escalation", f"{m.appropriate_escalation_rate}%", ">= 90%")
    table.add_row("P50 Latency", f"{m.latency_p50_ms} ms", "< 1500 ms")
    table.add_row("P95 Latency", f"{m.latency_p95_ms} ms", "< 3000 ms")
    table.add_row("Average Cost / Task", f"${m.average_cost_usd:.4f}", "< $0.05")
    table.add_row("[bold yellow]Agent Reliability Score[/bold yellow]", f"[bold yellow]{m.reliability_score} / 100[/bold yellow]", ">= 90.0")

    console.print(table)


@cli.command("replay")
@click.argument("run_id")
@click.option("--model", default="mock-candidate-v2", help="Candidate model name")
@click.option("--prompt-version", default="v2", help="Candidate prompt version")
def replay_cmd(run_id: str, model: str, prompt_version: str):
    """Replay a historical run with candidate model and compare trajectory diff."""
    from services.eval_engine.replay import replay_engine

    console.print(Panel(f"Replaying historical run [yellow]{run_id}[/yellow] with [green]{model}[/green]...", title="Trajectory Replay Engine"))

    try:
        comparison = asyncio.run(replay_engine.replay_run(run_id, candidate_model_name=model, candidate_prompt_version=prompt_version))
    except KeyError:
        # If run_id not in memory, execute a base run first then replay it
        from workflows.refunds.refund_workflow import CustomerRefundWorkflow
        from packages.models.mock import MockModelProvider
        base_res = asyncio.run(CustomerRefundWorkflow(MockModelProvider(model_name="mock-original-v1")).run(
            request_text="Customer Acme says they were charged twice for invoice INV-9281.",
            auto_approve_if_reviewed=True,
        ))
        orig_run_id = base_res["run"].run_id
        comparison = asyncio.run(replay_engine.replay_run(orig_run_id, candidate_model_name=model, candidate_prompt_version=prompt_version))

    table = Table(title="Historical vs Candidate Trajectory Comparison")
    table.add_column("Dimension", style="bold")
    table.add_column("Original Run", style="cyan")
    table.add_column("Candidate Replay", style="green")

    table.add_row("Model", comparison.original_model, comparison.candidate_model)
    table.add_row("Prompt Version", comparison.original_prompt_version, comparison.candidate_prompt_version)
    table.add_row("Success", str(comparison.original_success), str(comparison.candidate_success))
    table.add_row("Tool Calls", str(comparison.original_tool_calls_count), str(comparison.candidate_tool_calls_count))
    table.add_row("Cost (USD)", f"${comparison.original_cost_usd:.4f}", f"${comparison.candidate_cost_usd:.4f}")
    table.add_row("Duration", f"{comparison.original_duration_ms:.1f} ms", f"{comparison.candidate_duration_ms:.1f} ms")

    console.print(table)
    console.print(f"\n[bold]Summary Diff:[/bold] {comparison.diff_summary}")


@cli.command("chaos")
@click.argument("scenario", type=click.Choice([
    "api-timeout", "tool-down", "stale-data", "malformed-json",
    "duplicate-webhook", "prompt-injection", "schema-change",
    "rate-limit", "corrupted-pdf", "model-timeout"
]))
def chaos_cmd(scenario: str):
    """Execute an agent chaos engineering scenario."""
    from services.chaos.harness import chaos_harness
    from packages.schemas.chaos import ChaosScenarioType

    console.print(Panel(f"Injecting failure mode: [bold red]{scenario}[/bold red]", title="DeployOS Chaos Harness"))

    scen_enum = ChaosScenarioType(scenario)
    res = asyncio.run(chaos_harness.run_scenario(scen_enum))

    table = Table(title=f"Chaos Experiment: {scenario}")
    table.add_column("Check", style="bold")
    table.add_column("Result", style="green" if res.workflow_recovered else "red")

    table.add_row("Workflow Recovered / Fail-Safe", "YES" if res.workflow_recovered else "NO")
    table.add_row("Internal State Corrupted", "YES" if res.state_corrupted else "NO (SAFE)")
    table.add_row("Unsafe Execution Occurred", "YES" if res.unsafe_execution_occurred else "NO (0 UNSAFE ACTIONS)")
    table.add_row("Escalation Appropriate", "YES" if res.escalation_appropriate else "NO")
    table.add_row("Recovery Duration", f"{res.recovery_duration_ms} ms")

    console.print(table)
    console.print(f"\n[bold]Outcome:[/bold] {res.summary}")


@cli.command("serve")
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, help="Bind port")
def serve_cmd(host: str, port: int):
    """Start the DeployOS REST & WebSocket API Gateway."""
    import uvicorn
    console.print(Panel(f"Starting DeployOS API Gateway on [bold green]http://{host}:{port}[/bold green]", title="DeployOS Gateway"))
    uvicorn.run("apps.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    cli()
