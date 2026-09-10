# Tool Registry & Executors

## Overview

Memrail selects an action; the application executes it. The SDK's ToolRegistry describes available handlers, while ActionExecutor applies execution policy, lifecycle checks, argument validation, timeouts, and configured operational controls.

Keep tool schemas visible in the same project as their EMUs. Uploading a schema does not deploy its implementation. A selected action is not proof that its handler exists or that the application has authorized its business effect.

## Tool Registry

### Decorator-Based Registration (Python)

```python
from memrail.tools import ToolRegistry

registry = ToolRegistry(strict_validation=True)

@registry.tool(
    name="format_receipt",
    description="Format a receipt for display",
    schema={"receipt_id": str},
    projects=["support"],
    timeout_ms=8000,
    rate_limit="100/minute",
)
async def format_receipt(receipt_id: str) -> dict:
    return {"text": f"Receipt {receipt_id}"}
```

This example is deliberately read-only. For side effects, the handler must authorize the operation and enforce business-level deduplication before calling external services.

### Method-Based Registration (TypeScript)

```typescript
import { ToolRegistry } from '@memrail/sdk';

const registry = new ToolRegistry();
registry.registerTool(
    "format_receipt",
    "Format a receipt for display",
    {
        type: "object",
        properties: { receipt_id: { type: "string" } },
        required: ["receipt_id"],
        additionalProperties: false
    },
    ["support"],
    async (args) => ({ text: `Receipt ${args.receipt_id}` }),
    { timeoutMs: 8000, rateLimit: "100/minute" }
);
```

### Handler Patterns

Python decorator registration supports typed keyword parameters or a single `args: dict` handler. Use the dictionary form for the programmatic handler below. Keep schemas consistent with handler signatures. `ToolRegistry(strict_validation=True)` turns signature problems into registration errors.

Decorator registration uses `schema`. The Python `ToolDefinition` dataclass uses `input_schema`; programmatic `registry.register_tool` takes named fields, not a ToolDefinition positional argument.

Tool metadata includes project visibility, description, capabilities, constraints, examples, timeout, a string rate limit, and optional `idempotency_key` (TypeScript: `idempotencyKey`). This tool-template field is distinct from the EMU policy's literal-key `idempotency.scope`.

### CLI Tool Registration

For Python schema discovery, keep a populated `registry` or `tool_registry` at module level. Make imports safe: discovery imports the module. Tool bodies may be stubs when the file exists only to publish schemas, but the application needs real bound handlers for execution.

```bash
memrail tool-register --file emus/tools.py -j support -w staging
memrail action-connectivity -w staging -p support
```

Inspect the discovered tools before uploading. A registry created only inside an uncalled function is not available to module-level discovery. Use the installed CLI's `--help` when selecting scanning/import options.

## ActionExecutor

### Python

```python
from memrail.tools import ActionExecutor, ExecutorConfig, MissingToolBehavior, ShadowMode

executor = ActionExecutor(
    registry,
    project="support",
    config=ExecutorConfig(
        missing_tool_behavior=MissingToolBehavior.ERROR,
        execution_timeout_ms=30000,
        max_retries=0,
    ),
)
executor.configure_shadow(ShadowMode.SKIP)
```

### TypeScript

```typescript
import { ActionExecutor, MissingToolBehavior, ShadowMode } from '@memrail/sdk';

const executor = new ActionExecutor(registry, "support", {
    missingToolBehavior: MissingToolBehavior.ERROR,
    executionTimeoutMs: 30000,
    maxRetries: 0
});
executor.configureShadow(ShadowMode.SKIP);
```

Use `execute_decisions(decisions, context=...)` or `executeDecisions(decisions, context)` for an already-constructed decision list. Preserve policy and lifecycle data when adapting selections. Prefer the client helper below for API results, since it performs that conversion and coordinates dry-run and ACK behavior.

Missing-tool ERROR produces a failed execution result; SKIP/WARN do not execute the missing handler. Always inspect `was_executed`/`wasExecuted`, `success`, and `error`; “not executed” is not business success.

## Decide and Execute

Register handlers on the client used for the combined call. Creating a separate registry without connecting its definitions does not configure the client's executor.

### Python

```python
from memrail.atoms import state
from memrail.models import InvokeOptions, TraceOptions

async def process_receipt(client, *, dry_run=True):
    async def format_receipt(args: dict) -> dict:
        return {"text": f"Receipt {args['receipt_id']}"}

    client.register_tool(
        name="format_receipt",
        description="Format a receipt for display",
        schema={"receipt_id": str},
        projects=["support"],
        handler=format_receipt,
    )
    return await client.decide_and_execute(
        context=[state("receipt.id", "R-123")],
        decision_point="receipt",
        options=InvokeOptions(dry_run=dry_run),
        trace=TraceOptions(enable=True),
        executor_context={"user_id": "U-123"},
        auto_ack=True,
    )
```

Pass an `AsyncAMIClient` configured with the intended workspace and project. The synchronous counterpart is `AMIClient.decide_and_execute_sync`. `invoke_and_execute` is a legacy alias; new examples should use `decide_and_execute`.

### TypeScript

```typescript
import { AMIClient, state } from '@memrail/sdk';

async function processReceipt(client: AMIClient, dryRun = true) {
    client.registerTool(
        "format_receipt",
        "Format a receipt for display",
        {
            type: "object",
            properties: { receipt_id: { type: "string" } },
            required: ["receipt_id"]
        },
        ["support"],
        async (args) => ({ text: `Receipt ${args.receipt_id}` })
    );
    return client.decideAndExecute({
        context: [state("receipt.id", "R-123")],
        decisionPoint: "receipt",
        options: { dry_run: dryRun },
        trace: { enable: true },
        executorContext: { user_id: "U-123" },
        autoAck: true
    });
}
```

Provision the `receipt` decision-point binding and a matching EMU separately through JSONL. The default dry-run evaluates only; setting it false enables eligible handlers.

The combined result has `invoke_result`, `execution_results`, `ack_results` in Python, and `invokeResult`, `executionResults`, `ackResults` in TypeScript. An execution result contains its decision, output/error, duration, execution mode, and whether the handler ran.

### Execution Policy

| Policy | Tool call / route | Decision prompt / context directive |
|---|---|---|
| `auto` | Eligible for dispatch | Eligible for dispatch |
| `require_human` | Requires application-verified consent | Requires application-verified consent |
| `advisory` | Not dispatched | Advisory handler may run |

Application authorization still applies. `require_human` does not create an approval UI automatically. After verifying approval for this specific operation, pass literal `True`/`true` as `options.human_consent` or the executor context's `human_consent`. The combined helper propagates it to both eligibility and execution. Never derive it from an LLM assertion or a truthy string.

An API-derived decision with missing or unknown policy must fail closed. Do not reconstruct selections as legacy decisions that discard that metadata.

### ACK and Idempotency

With `auto_ack`/`autoAck`, successful executed results are acknowledged using their activation identity; skipped and dry-run actions are not. ACK works independently of optional trace persistence. Retain identifiers and inspect failures so an ACK failure is not mistaken for an unexecuted business operation.

Use literal state keys in `policy.idempotency.scope`, provide all explicitly required scope/role inputs, and select a positive TTL for a suppression window. Missing/null required inputs suppress selection; zero and false remain valid values. Policy suppression and request caching do not replace a transactional business-operation key before side effects.

## Lifecycle-Aware Execution

| State | Normal API/executor behavior |
|---|---|
| `draft`, `inactive`, `archived` | Not live selections; executor skips if supplied directly |
| `shadow` | Server evaluates into trace diagnostics, not executable selections |
| `canary` | Requires an explicitly configured application cohort decision |
| `active` | Dispatch remains subject to policy, handler availability, and application checks |

Unknown lifecycle values should not become active. New deployments should preserve metadata end-to-end; legacy responses that omit lifecycle are compatibility inputs, not a reason to strip a known state.

## Shadow Mode

Use server shadow state to compare eligibility without executing the shadow action. Inspect `trace.candidates`, including `passed` and `suppressed_by`; shadows cannot displace live candidates in arbitration.

The low-level executor also supports manually supplied shadow decisions:

| Executor mode | Behavior |
|---|---|
| `SKIP` | No handler call |
| `DRY_RUN` | Validate inputs without calling the handler |
| `EXECUTE_AND_COMPARE` | Actually calls the handler and compares output |

The last mode is not production-safe observation for a side-effecting tool. Use only an explicitly isolated comparison environment or a read-only handler. It does not make server shadow selections appear in the normal response.

## Canary Mode

Choose cohorts in application-owned executor configuration; there is no `policy.canary` percentage field. For example, an allowlisted test user set is predictable and easy to review:

```python
canary_users = {"internal-test-user"}
client.configure_canary(
    decider=lambda decision, context: context.get("user_id") in canary_users
)
```

```typescript
const canaryUsers = new Set(["internal-test-user"]);
client.configureCanary({
    decider: (_decision, context) => canaryUsers.has(context.user_id)
});
```

Supply the same application identity in `executor_context`/`executorContext`. Without an affirmative cohort decision the handler is skipped. If percentage rollout is needed, implement and test a stable application hash/cohort contract; do not assume API responses contain a percentage.

A selected but skipped canary must not consume its action lock or cooldown. Successful canary ACK establishes those controls, so enforce business deduplication before the handler. Review outcome quality, sample size, failure cases, and rollback criteria before an explicit lifecycle promotion; success-rate comparison alone is insufficient.

## Circuit Breaker

Configure the Python executor, not a fictional decorator field:

```python
from memrail.tools import CircuitBreakerConfig

executor.configure_circuit_breaker(
    enabled=True,
    default_config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout_ms=60000,
    ),
)
```

Closed allows execution; open rejects calls; half-open probes recovery. In TypeScript, `executor.circuitBreakersEnabled = true` enables the executor's circuit breakers. Inspect execution results for circuit failures rather than assuming every failure is raised to the caller as an exception.

## Rate Limiting

Tool rates use strings such as `"100/minute"`, not a `{requests, period_seconds}` object. Default controls are local to the process. For a distributed Python deployment, supply a compatible RateLimiterBackend through `executor.configure_rate_limiter(backend=...)`. Do not assume an invented Redis backend class is included; implement/test shared admission where needed.

## Metrics Collection

Python execution metrics are opt-in:

```python
collector = executor.enable_metrics()
metrics = collector.get_metrics("support.receipt", window_seconds=3600)
print(metrics.active_count, metrics.active_success_rate)
print(metrics.canary_count, metrics.canary_success_rate)
```

These are bounded local samples grouped by EMU key and execution mode, not a cross-deployment version analytics database. Export the execution results to your application's monitoring system for durable aggregation. Installing a metrics package alone does not configure an exporter.

## See Also

- [Python SDK](05-sdk-integration-python.md)
- [TypeScript SDK](05b-sdk-integration-typescript.md)
- [Action connectivity](07-action-connectivity.md)
- [JSONL deployment and lifecycle](12-emu-jsonl-workflow.md)
