# Tool Registry & Executors

**Building a Production-Ready Action Execution System**

## Table of Contents

- [Overview](#overview)
- [Tool Registry](#tool-registry)
- [ActionExecutor](#actionexecutor)
- [invoke_and_execute Pattern](#invoke_and_execute-pattern)
- [Lifecycle-Aware Execution](#lifecycle-aware-execution)
- [Shadow Mode](#shadow-mode)
- [Canary Mode](#canary-mode)
- [Circuit Breaker](#circuit-breaker)
- [Rate Limiting](#rate-limiting)
- [Metrics Collection](#metrics-collection)

---

## Overview

The SDK provides a **Tool Registry** for declarative tool management and an **ActionExecutor** for lifecycle-aware execution with:

- **Shadow testing** before production
- **Canary rollouts** with sticky sessions
- **Circuit breakers** for fault tolerance
- **Rate limiting** per tool
- **Metrics collection** for monitoring

---

## Tool Registry

Register tools using decorators (Python) or method calls (TypeScript):

### Decorator-Based Registration (Python)

```python
from memrail.tools import ToolRegistry, ToolDefinition

registry = ToolRegistry()

@registry.tool(
    name="mailer",
    description="Send emails via SendGrid",
    schema={
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "template": {"type": "string"}
        },
        "required": ["to", "subject"]
    },
    projects=["support", "marketing"],  # Scope to specific projects
    timeout_ms=8000,
    rate_limit={"requests": 100, "period_seconds": 60}
)
async def send_email(to: str, subject: str, template: str = "default"):
    await sendgrid.send(to=to, subject=subject, template=template)
    return {"sent": True}

@registry.tool(
    name="slack",
    description="Post messages to Slack",
    schema={
        "type": "object",
        "properties": {
            "channel": {"type": "string"},
            "message": {"type": "string"}
        },
        "required": ["channel", "message"]
    },
    projects=["support", "alerts"],
    rate_limit={"requests": 50, "period_seconds": 60}
)
async def post_slack(channel: str, message: str):
    await slack_client.post_message(channel=channel, text=message)
    return {"posted": True, "channel": channel}
```

### Method-Based Registration (TypeScript)

```typescript
import { ToolRegistry } from '@memrail/sdk';

const registry = new ToolRegistry();

registry.tool({
    name: "mailer",
    description: "Send emails via SendGrid",
    schema: {
        type: "object",
        properties: {
            to: { type: "string" },
            subject: { type: "string" },
            template: { type: "string" }
        },
        required: ["to", "subject"]
    },
    projects: ["support", "marketing"],
    timeoutMs: 8000,
    rateLimit: { requests: 100, periodSeconds: 60 },
    handler: async (args) => {
        await sendgrid.send({ to: args.to, subject: args.subject, template: args.template });
        return { sent: true };
    }
});

registry.tool({
    name: "slack",
    description: "Post messages to Slack",
    schema: {
        type: "object",
        properties: {
            channel: { type: "string" },
            message: { type: "string" }
        },
        required: ["channel", "message"]
    },
    projects: ["support", "alerts"],
    rateLimit: { requests: 50, periodSeconds: 60 },
    handler: async (args) => {
        await slackClient.postMessage({ channel: args.channel, text: args.message });
        return { posted: true, channel: args.channel };
    }
});
```

### Handler Patterns

The SDK supports two handler signatures. Both are validated at registration time when `validate_signatures=True` (default).

#### Pattern 1: Typed Parameters (Recommended)

Use individual keyword arguments with type annotations. The SDK validates that your annotations match the declared schema and wraps the handler automatically:

```python
@registry.tool(
    "send_email",
    "Send an email using a template",
    {"to": str, "subject": str, "template": str},
    projects=["support"],
)
async def send_email(to: str, subject: str, template: str = "default") -> dict:
    await sendgrid.send(to=to, subject=subject, template=template)
    return {"sent": True}
```

Benefits:
- Type-safe — SDK validates annotations match schema at registration
- IDE autocompletion on parameters
- Optional parameters map to schema fields not in `required`
- `Optional[str]` annotations supported for nullable fields

#### Pattern 2: Args Dict

Single `args: dict` parameter — you unpack manually:

```python
@registry.tool(
    "send_email",
    "Send an email using a template",
    {"to": str, "subject": str},
    projects=["support"],
)
async def send_email(args: dict) -> dict:
    await sendgrid.send(to=args["to"], subject=args["subject"])
    return {"sent": True}
```

Use this for stubs (CLI registration) or when you need dynamic argument handling.

#### Signature Validation

```python
# Enable strict mode — extra params become errors instead of warnings
registry = ToolRegistry(validate_signatures=True, strict_validation=True)

# Disable validation entirely (not recommended)
registry = ToolRegistry(validate_signatures=False)
```

Validation checks:
- Required schema fields have matching handler parameters
- Type annotations match schema types (`str`↔`string`, `int`↔`integer`, etc.)
- Extra handler parameters that aren't in schema produce warnings (errors in strict mode)
- Return type must be `dict` or `Dict[str, Any]`

### CLI Tool Registration (`memrail tool-register`)

The `memrail tool-register` CLI command discovers and uploads tool definitions to Memrail. It uses a two-phase process:

1. **AST scanning** — Finds `@*.tool(...)` decorators in the source file
2. **Module import** — Imports the file and looks for a populated `ToolRegistry` instance (variable named `registry` or `tool_registry`)

**Both phases must succeed** for tools to register. If the CLI finds decorators in AST but the imported module has no populated `ToolRegistry`, you get `"Tools count: 0"` and nothing uploads.

#### Correct Pattern: Module-Level Registry (REQUIRED)

```python
# emus/tools.py — standalone file with no app dependencies
from memrail.tools import ToolRegistry

registry = ToolRegistry(server_name="my-tools")

@registry.tool(
    "send_email",
    "Send an email using a template",
    {"template": str, "recipient": str},
    projects=["default"],
)
async def send_email(args: dict) -> dict:
    ...  # Stub — actual handler lives in app/services/
```

Key points:
- `ToolRegistry` must be instantiated at **module level** (not inside a function)
- The variable must be named `registry` or `tool_registry`
- Use `server_name` to group tools under a logical server name
- Tool bodies can be stubs (`...`) — the CLI only uploads the schema, not the implementation
- Keep the file **dependency-free** (no app imports) so the CLI can import it cleanly

#### Wrong Pattern: Registry Inside a Function (BROKEN)

```python
# WRONG — CLI imports module but never calls register(), so ToolRegistry is empty
from memrail.tools import ToolRegistry

def register(client):
    registry = ToolRegistry()

    @registry.tool("send_email", ...)
    async def send_email(args: dict) -> dict:
        ...

    return registry
```

The CLI finds `@registry.tool(...)` in AST (phase 1 passes) but `registry` is local to `register()` and never populated at module scope (phase 2 fails → 0 tools).

#### Running the CLI

```bash
# Register tools from a file
memrail tool-register --file emus/tools.py -j default -w production

# Output on success:
# Discovered 6 tools via AST scanning
# Schema tools count: 6
# Uploaded 6 tools to project 'default'
```

---

### Programmatic Registration

```python
registry.register_tool(ToolDefinition(
    name="zendesk",
    description="Create Zendesk tickets",
    schema={
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "description": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]}
        }
    },
    projects=["support"],
    handler=create_zendesk_ticket,
    timeout_ms=10000
))
```

### Tool Definition Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique tool identifier (matches `tool_id` in EMU actions) |
| `description` | Yes | Human-readable description |
| `schema` | Yes | JSON Schema for args validation |
| `projects` | Yes | List of project IDs this tool is available in |
| `handler` | No | Function to execute (can be bound later) |
| `timeout_ms` | No | Execution timeout (default: 30000) |
| `rate_limit` | No | Rate limiting config |
| `circuit_breaker` | No | Circuit breaker config |
| `idempotency_key_template` | No | Template for idempotency keys |

---

## ActionExecutor

The `ActionExecutor` handles lifecycle-aware execution:

**Python:**
```python
from memrail.tools import ActionExecutor, ExecutorConfig
from memrail.tools.models import MissingToolBehavior, ShadowMode

executor = ActionExecutor(
    registry=registry,
    config=ExecutorConfig(
        missing_tool_behavior=MissingToolBehavior.WARN,  # ERROR, SKIP, or WARN
        default_timeout_ms=30000,
        enable_circuit_breaker=True,
        enable_rate_limiting=True,
        shadow_mode=ShadowMode.EXECUTE_AND_COMPARE,  # For shadow EMUs
    )
)
```

**TypeScript:**
```typescript
import { ActionExecutor, ShadowMode, MissingToolBehavior } from '@memrail/sdk';

const executor = new ActionExecutor({
    registry,
    config: {
        missingToolBehavior: MissingToolBehavior.WARN,
        defaultTimeoutMs: 30000,
        enableCircuitBreaker: true,
        enableRateLimiting: true,
        shadowMode: ShadowMode.EXECUTE_AND_COMPARE,
    }
});
```

### Missing Tool Behavior

| Behavior | Description |
|----------|-------------|
| `ERROR` | Raise exception if tool not found |
| `SKIP` | Skip execution, log warning |
| `WARN` | Log warning, continue with other actions |

### Basic Execution

```python
# Execute a single action
result = await executor.execute(decision)

print(f"Success: {result.success}")
print(f"Output: {result.output}")
print(f"Duration: {result.duration_ms}ms")
print(f"Mode: {result.execution_mode}")  # ACTIVE, SHADOW, CANARY

# Execute multiple actions
results = await executor.execute_all(decisions)
```

---

## invoke_and_execute Pattern

The SDK provides a combined `invoke_and_execute()` method that handles invocation, execution, and acknowledgment in one call:

```python
from memrail import AsyncAMIClient
from memrail.atoms import state, tag, StateObject
from memrail.tools import ToolRegistry, ActionExecutor

# Setup
registry = ToolRegistry()

@registry.tool(name="mailer", description="Send emails", schema={...})
async def send_email(to: str, subject: str):
    return {"sent": True}

@registry.tool(name="slack", description="Post to Slack", schema={...})
async def post_slack(channel: str, message: str):
    return {"posted": True}

async with AsyncAMIClient(
    api_key="ami_...",
    org="your-org",
    workspace="production",
    project="support"
) as client:

    executor = ActionExecutor(registry=registry)

    # Build atoms from objects
    user = StateObject("user", {"id": "U-123", "tier": "premium"})
    ticket = StateObject("ticket", {"id": "T-456", "priority": "high"})

    # Combined invoke + execute + ack
    result = await client.invoke_and_execute(
        atoms=user.to_atoms() + ticket.to_atoms() + [
            tag("sentiment", "negative"),
        ],
        executor=executor,
        context={"user_id": "U-123"},  # For canary sticky decisions
        auto_ack=True,                  # Auto-acknowledge on success
        trace=True
    )

    # Access results
    print(f"Invocation ID: {result.invoke_result.invocation_id}")

    for exec_result in result.execution_results:
        print(f"Tool: {exec_result.decision.tool_id}")
        print(f"Success: {exec_result.success}")
        print(f"Output: {exec_result.output}")
        print(f"Duration: {exec_result.duration_ms}ms")
        print(f"Mode: {exec_result.execution_mode}")

    for ack_result in result.ack_results:
        print(f"Ack: {ack_result.activation_id} -> {ack_result.status}")
```

**TypeScript equivalent:**
```typescript
import { AMIClient, state, tag, StateObject } from '@memrail/sdk';
import { ToolRegistry, ActionExecutor } from '@memrail/sdk';

const registry = new ToolRegistry();

registry.tool({
    name: "mailer", description: "Send emails",
    schema: { /* ... */ }, projects: ["support"],
    handler: async (args) => ({ sent: true })
});

const client = new AMIClient({
    org: "your-org", workspace: "production", project: "support"
});

const executor = new ActionExecutor({ registry });

const user = new StateObject("user", { id: "U-123", tier: "premium" });
const ticket = new StateObject("ticket", { id: "T-456", priority: "high" });

const result = await client.decideAndExecute({
    context: [...user.toAtoms(), ...ticket.toAtoms(), tag("sentiment", "negative")],
    executor,
    context: { userId: "U-123" },
    autoAck: true,
    trace: true
});

for (const execResult of result.executionResults) {
    console.log(`Tool: ${execResult.decision.toolId}`);
    console.log(`Success: ${execResult.success}`);
    console.log(`Duration: ${execResult.durationMs}ms`);
}
```

### InvokeAndExecuteResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `invoke_result` | `InvokeResponse` | Full invoke response with selected EMUs |
| `execution_results` | `List[ExecutionResult]` | Results for each executed action |
| `ack_results` | `List[AckResult]` | Acknowledgment results (if `auto_ack=True`) |

### ExecutionResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `decision` | `Decision` | The EMU decision that was executed |
| `success` | `bool` | Whether execution succeeded |
| `output` | `Any` | Tool return value |
| `error` | `Optional[str]` | Error message if failed |
| `duration_ms` | `float` | Execution time |
| `execution_mode` | `LifecycleState` | ACTIVE, SHADOW, or CANARY |

---

## Lifecycle-Aware Execution

The executor automatically handles different lifecycle states:

```python
# Lifecycle state is returned in invoke response
for item in response.selected:
    print(f"EMU: {item.emu_key}")
    print(f"Lifecycle: {item.lifecycle_state}")  # draft, shadow, canary, active, archived
    print(f"Action: {item.action}")
```

### Execution by Lifecycle State

| State | Execution Behavior |
|-------|-------------------|
| `draft` | Never returned (not selectable) |
| `shadow` | Depends on shadow_mode config |
| `canary` | Executed for configured % of traffic |
| `active` | Always executed |
| `archived` | Never returned |

---

## Shadow Mode

Shadow EMUs are returned in invoke responses with `lifecycle_state: "shadow"`. The ActionExecutor handles them based on the configured shadow mode:

### Shadow Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `SKIP` | Don't execute, just log | Safe validation in production |
| `DRY_RUN` | Validate args, don't execute | Schema validation testing |
| `EXECUTE_AND_COMPARE` | Execute and compare output hash | A/B testing before promotion |

### Configuration

```python
from memrail.tools import ActionExecutor, ExecutorConfig
from memrail.tools.models import ShadowMode

# Configure shadow behavior
executor = ActionExecutor(
    registry=registry,
    config=ExecutorConfig(
        shadow_mode=ShadowMode.EXECUTE_AND_COMPARE
    )
)

# Execution results include mode information
for result in execution_results:
    if result.execution_mode == "shadow":
        print(f"Shadow execution: {result.output}")
        # Output hash is recorded for comparison
```

### Shadow Testing Workflow

```python
# 1. Register EMU in shadow mode
await client.register_emu(
    emu_key="new-escalation-v2",
    trigger="...",
    state="shadow"  # Evaluate but execution controlled by shadow_mode
)

# 2. Monitor shadow executions
response = await client.decide(context=[...], trace=True)

for item in response.selected:
    if item.lifecycle_state == "shadow":
        print(f"Shadow EMU would fire: {item.emu_key}")

# 3. When confident, promote to canary
await client.update_emu_lifecycle("new-escalation-v2", "canary")

# 4. Then to active
await client.update_emu_lifecycle("new-escalation-v2", "active")
```

---

## Canary Mode

Canary EMUs execute on a percentage of invocations with sticky session support:

### Configuration

```python
# Canary configuration in EMU policy
{
    "emu_key": "new-escalation-v2",
    "state": "canary",
    "policy": {
        "canary": {
            "percentage": 10,           # 10% of traffic
            "sticky_field": "user.id",  # Same user = same decision
            "salt": "v2-rollout"        # Unique per rollout
        }
    }
}
```

### Sticky Sessions

The same user always gets the same canary decision:

```python
from memrail.tools import make_sticky_decider

# Create deterministic decider
decider = make_sticky_decider(
    canary_percentage=10,
    salt="my-emu-v2"
)

# User U-123 will always get the same result
assert decider("U-123") == decider("U-123")  # Always True

# Different users may get different results (based on hash)
decider("U-123")  # -> True (in canary)
decider("U-456")  # -> False (not in canary)
decider("U-789")  # -> True (in canary)
```

### Canary Metrics

Track success rates before promotion:

```python
# Compare active vs canary performance
active_metrics = collector.get_metrics("my-emu", version=1)
canary_metrics = collector.get_metrics("my-emu", version=2)

print(f"Active success rate: {active_metrics.success_rate}")
print(f"Canary success rate: {canary_metrics.success_rate}")

if canary_metrics.success_rate >= active_metrics.success_rate:
    # Safe to promote
    await client.update_emu_lifecycle("my-emu", "active")
else:
    # Rollback
    await client.update_emu_lifecycle("my-emu", "archived")
```

---

## Circuit Breaker

Protect against cascading failures:

### Configuration

```python
@registry.tool(
    name="external_api",
    circuit_breaker={
        "failure_threshold": 5,      # Open after 5 consecutive failures
        "success_threshold": 3,      # Close after 3 consecutive successes
        "timeout_seconds": 60        # Stay open for 60 seconds
    }
)
async def call_external_api(params: dict):
    return await external_service.call(params)
```

### Circuit Breaker States

```
CLOSED ──[failures >= threshold]──> OPEN
   ^                                   │
   │                                   │
   └──[successes >= threshold]── HALF_OPEN <──[timeout expires]──┘
```

| State | Behavior |
|-------|----------|
| `CLOSED` | Normal operation, requests pass through |
| `OPEN` | All requests fail immediately (fast fail) |
| `HALF_OPEN` | Allow limited requests to test recovery |

### Handling Circuit Breaker Events

**Python:**
```python
from memrail.tools import CircuitBreakerOpen

try:
    result = await executor.execute(decision)
except CircuitBreakerOpen as e:
    print(f"Circuit open for tool: {e.tool_id}")
    print(f"Will retry after: {e.retry_after_seconds}s")
    # Fallback logic
```

**TypeScript:**
```typescript
import { CircuitOpenError } from '@memrail/sdk';

try {
    const result = await executor.execute(decision);
} catch (error) {
    if (error instanceof CircuitOpenError) {
        console.log(`Circuit open for tool: ${error.toolId}`);
        console.log(`Will retry after: ${error.retryAfterSeconds}s`);
    }
}
```

---

## Rate Limiting

Control execution rate per tool:

### Configuration

```python
@registry.tool(
    name="mailer",
    rate_limit={
        "requests": 100,        # Max requests
        "period_seconds": 60    # Per time period
    }
)
async def send_email(...):
    ...
```

### Redis Backend (Distributed)

For distributed systems, use Redis-backed rate limiting:

```python
from memrail.tools import ActionExecutor, RedisRateLimitBackend
import redis.asyncio as redis

redis_client = redis.from_url("redis://localhost:6379")

executor = ActionExecutor(
    registry=registry,
    rate_limit_backend=RedisRateLimitBackend(redis_client)
)
```

### Handling Rate Limit Events

**Python:**
```python
from memrail.tools import RateLimitExceeded

try:
    result = await executor.execute(decision)
except RateLimitExceeded as e:
    print(f"Rate limit exceeded for tool: {e.tool_id}")
    print(f"Retry after: {e.retry_after_seconds}s")
    # Queue for later or fallback
```

**TypeScript:**
```typescript
import { RateLimitExceeded } from '@memrail/sdk';

try {
    const result = await executor.execute(decision);
} catch (error) {
    if (error instanceof RateLimitExceeded) {
        console.log(`Rate limit exceeded for tool: ${error.toolId}`);
        console.log(`Retry after: ${error.retryAfterSeconds}s`);
    }
}
```

---

## Metrics Collection

Track execution metrics for monitoring and shadow comparison:

### Setup

```python
from memrail.tools import MetricsCollector

collector = MetricsCollector()
executor = ActionExecutor(
    registry=registry,
    metrics_collector=collector
)
```

### Querying Metrics

```python
# Get metrics for specific EMU
metrics = collector.get_metrics(
    emu_key="my-emu",
    window_minutes=60  # Last hour
)

print(f"Total executions: {metrics.total_count}")
print(f"Success rate: {metrics.success_rate}")
print(f"P50 latency: {metrics.latency_p50_ms}ms")
print(f"P95 latency: {metrics.latency_p95_ms}ms")
print(f"P99 latency: {metrics.latency_p99_ms}ms")
print(f"Error count: {metrics.error_count}")
```

### Shadow Comparison Metrics

```python
# Compare shadow vs active outputs
shadow_metrics = collector.get_shadow_comparison(
    emu_key="my-emu",
    window_minutes=60
)

print(f"Output match rate: {shadow_metrics.match_rate}")
print(f"Divergent outputs: {shadow_metrics.divergent_count}")
print(f"Shadow faster: {shadow_metrics.shadow_faster_rate}")
```

### Prometheus Integration

```python
from prometheus_client import Counter, Histogram

# Metrics are automatically exported if prometheus_client is installed
# ami_tool_executions_total{tool_id="mailer", status="success"}
# ami_tool_execution_duration_seconds{tool_id="mailer"}
```

---

## Complete Example

```python
from memrail import AsyncAMIClient
from memrail.atoms import state, tag, StateObject
from memrail.tools import ToolRegistry, ActionExecutor, ExecutorConfig, MetricsCollector
from memrail.tools.models import ShadowMode, MissingToolBehavior

# 1. Setup registry
registry = ToolRegistry()

@registry.tool(
    name="mailer",
    description="Send emails",
    schema={"type": "object", "properties": {"to": {"type": "string"}}},
    projects=["support"],
    rate_limit={"requests": 100, "period_seconds": 60},
    circuit_breaker={"failure_threshold": 5, "timeout_seconds": 60}
)
async def send_email(to: str, subject: str, body: str):
    result = await sendgrid.send(to=to, subject=subject, body=body)
    return {"sent": True, "message_id": result.id}

@registry.tool(
    name="slack",
    description="Post to Slack",
    schema={"type": "object", "properties": {"channel": {"type": "string"}}},
    projects=["support", "alerts"]
)
async def post_slack(channel: str, message: str):
    await slack.post_message(channel=channel, text=message)
    return {"posted": True}

# 2. Setup executor with full config
collector = MetricsCollector()
executor = ActionExecutor(
    registry=registry,
    config=ExecutorConfig(
        missing_tool_behavior=MissingToolBehavior.WARN,
        enable_circuit_breaker=True,
        enable_rate_limiting=True,
        shadow_mode=ShadowMode.EXECUTE_AND_COMPARE,
    ),
    metrics_collector=collector
)

# 3. Use invoke_and_execute
async with AsyncAMIClient(
    org="my-org",
    workspace="production",
    project="support"
) as client:

    result = await client.invoke_and_execute(
        atoms=[
            state("user.id", "U-123"),
            state("user.tier", "enterprise"),
            state("ticket.priority", "high"),
            tag("sentiment", "negative"),
        ],
        executor=executor,
        context={"user_id": "U-123"},
        auto_ack=True,
        trace=True
    )

    # 4. Report results
    for exec_result in result.execution_results:
        status = "OK" if exec_result.success else "FAILED"
        mode = exec_result.execution_mode.upper()
        print(f"[{status}] [{mode}] {exec_result.decision.emu_key}")

    # 5. Check metrics
    metrics = collector.get_metrics("support.vip-escalation", window_minutes=60)
    print(f"Success rate: {metrics.success_rate:.1%}")
```

---

**See Also**:
- [05-sdk-integration-python.md](05-sdk-integration-python.md) - Python SDK usage
- [05b-sdk-integration-typescript.md](05b-sdk-integration-typescript.md) - TypeScript SDK usage
- [07-action-connectivity.md](07-action-connectivity.md) - Action requirements
