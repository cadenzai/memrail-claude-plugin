# SDK Integration (Python)

## Installation

Use Python 3.9 or newer and install `memrail` into the application's virtual environment:

```bash
python -m pip install memrail
memrail --help
memrail emu-plan --help
memrail emu-apply --help
```

Check the installed SDK version and CLI capabilities. A merged SDK change is not necessarily available in a published package. Candidate-validation workflows below require a CLI exposing `--strict` and a server supporting candidate validation.

## Configuration

Obtain an API key from your Memrail organization. Keep credentials outside source control.

```bash
export AMI_API_KEY="your-api-key"
export AMI_ORG="your-org"
export AMI_WORKSPACE="staging"
export AMI_PROJECT="support"
```

```python
from memrail import AsyncAMIClient

async def inspect_configuration():
    async with AsyncAMIClient() as client:
        return client.config.workspace, client.config.project
```

Both `AMIClient` (synchronous) and `AsyncAMIClient` accept explicit configuration. An explicit `base_url` takes precedence over `AMI_BASE_URL`; otherwise the public endpoint is used. `use_env=False` disables environment fallbacks. Workspace/project arguments on a call override client configuration. Specify them explicitly for deployments and tenant-sensitive operations.

The SDK uses `Authorization: AMI-Key <key>`, not Bearer authentication.

## ATOM Builders

State keys use lowercase dotted names with 2–7 segments. Tag kinds may be single-segment. Keep classifications within a fixed taxonomy and label their actual source.

```python
from memrail.atoms import state, tag, atoms_from_dict

context = [
    state("ticket.id", "T-456"),
    state("ticket.priority", "high", source="system"),
    tag("sentiment", "negative", source="ml"),
    *atoms_from_dict(
        {"id": "U-123", "tier": "premium", "preferences": {"language": "en"}},
        prefix="user",
    ),
]
```

`atoms_from_dict` flattens nested dictionaries into state atoms. Use scalar facts that match the policy contract; do not silently convert an absent fact into an affirmative default. Source metadata is carried to the API, but the application must ensure model output cannot impersonate trusted facts.

### Event ATOMs

Event topics use `subject.verb.object` or `project.subject.verb.object`. Supply a UTC timestamp. Anchors bind entity roles; attributes are available to event WHERE filters.

```python
from datetime import datetime, timezone
from memrail.atoms import event

email_sent = event(
    "agent.sent.email",
    ts=datetime.now(timezone.utc),
    subject_anchor=("agent", "A-123"),
    object_anchor=("email", "E-456"),
    attributes={"user_id": "U-123", "template": "welcome"},
)
```

## EMU Management (CLI)

Use the [JSONL workflow](12-emu-jsonl-workflow.md) for production EMUs. SDK write methods are useful for isolated tests and authorized migration tooling, not an alternative source of deployed policy.

### CLI Commands

| Command | Purpose |
|---|---|
| `memrail emu-pull` | Export EMUs and the local sync lock |
| `memrail emu-plan --strict` | Review changes and validate candidates before writes |
| `memrail emu-apply --strict` | Validate the complete candidate set, then apply |
| `memrail emu-plan --validate-only` | Local JSONL/DSL validation |
| `memrail emu-validate` | Check already-deployed EMUs |
| `memrail change-state` | Explicit lifecycle transition |
| `memrail get-emu`, `memrail list-emus` | Inspect deployed definitions |

New EMUs default to draft. `--target-state` controls new records; it does not silently promote existing records. An explicit JSONL state must agree with the requested lifecycle workflow. Omitting state preserves an existing lifecycle. Likewise, omitting `decision_point` preserves an existing binding; explicit null clears it.

## Invoking the Engine

`decide` evaluates policy and returns selections; it does not call business tools.

```python
from memrail import AsyncAMIClient
from memrail.atoms import state, tag
from memrail.models import InvokeOptions, TraceOptions

async def inspect_ticket():
    async with AsyncAMIClient(workspace="staging", project="support") as client:
        response = await client.decide(
            context=[
                state("ticket.id", "T-456"),
                state("ticket.priority", "high"),
                tag("sentiment", "negative", source="ml"),
            ],
            decision_point="triage",
            options=InvokeOptions(dry_run=True),
            trace=TraceOptions(enable=True),
        )
        for item in response.selected:
            print(item.emu_key, item.emu_version, item.lifecycle_state)
            print(item.policy, item.action)
        for candidate in (response.trace or {}).get("candidates", []):
            print(candidate["emu_key"], candidate["passed"], candidate["suppressed_by"])
        return response
```

A named `decision_point` selects EMUs bound to that exact point. Provision the matching binding in JSONL; it is not just a trace label. The HTTP field is `context_atoms`; SDK methods accept `context` or its `atoms` alias, not both.

### With Options

`InvokeOptions` exposes `dry_run`, `top_k`, `human_consent`, `store_read_cutoff_ts`, `pin_registry_version`, and `pin_policy_version`. `TraceOptions` takes `enable`; there is no `explain` or `include_all_emus` option.

Top-k is subject to arbitration and exclusion-group constraints, not an unconditional number of actions. A trace candidate's `passed` value alone does not mean it was selected: also inspect `suppressed_by` and the response selections.

### With Context Timestamp

Pass a timezone-aware `context_ts` for temporal evaluation. Event windows and retained history are evaluated relative to that context. This does not freeze the registry, policy, cooldowns, or idempotency state for historical replay.

### With Idempotency

Use an invocation `idempotency_key` when retrying the same logical request. During its cache lifetime, the key is bound to the normalized request and tenant/project scope. Reusing it with a different context, point, or options returns a conflict; choose a new key for a genuinely new request.

Invocation caching is distinct from `policy.idempotency` and executor/business deduplication. A cached selection is not proof that a tool has or has not executed.

### Response Handling

SDK selections expose `action`, `policy`, `lifecycle_state`, `emu_version`, `activation_id`, and `score`. The HTTP selection uses `payload`, which the SDK adapts to `action`. Do not assume a `priority` or `processing_time_ms` response field.

For execution, use [Tool Registry & Executors](09-tool-registry-executors.md), which preserves policy and lifecycle handling. Do not replace it with a loop that blindly dispatches every selected tool.

## Event Ingestion

Persist events separately from invocation. Building an event atom is not the same as storing it.

```python
from memrail import AsyncAMIClient
from memrail.atoms import event
from datetime import datetime, timezone

async def record_email():
    async with AsyncAMIClient(workspace="staging", project="support") as client:
        return await client.emit_event(event(
            "agent.sent.email",
            ts=datetime.now(timezone.utc),
            attributes={"user_id": "U-123"},
        ))
```

For a batch, call `await client.emit_events(events, workspace=..., project=...)` with a list of EventAtom objects. Emit the actual outcome after the application completes an action. Do not blindly retry ingestion: duplicate events can affect COUNT rules.

## Complete Workflows

A typical support handler loads trusted ticket/customer facts, adds constrained classification tags, invokes the matching decision point, and executes through the configured client helper. Record success/failure events with entity identifiers and preserve execution results for monitoring.

The complete, executable integration shape is in [the combined execution example](09-tool-registry-executors.md#decide-and-execute). Supply real handlers with business authorization and operation-level deduplication before enabling effects.

## Testing & Debugging

### Dry Run Mode

Use `InvokeOptions(dry_run=True)` to evaluate without activation locks or business execution. The combined helper also skips handlers and ACK. Diagnostic traces/accounting may still be written; dry-run is not a promise of zero API activity.

### Tracing

Use `TraceOptions(enable=True)`; `response.trace` is a dictionary with `candidates`, not an object exposing `evaluated_emus`. Inspect reasons and suppression independently of trigger results.

### Shadow Mode Testing

Server-side shadow EMUs appear in trace candidates, not executable selections. They are arbitrated separately from live EMUs. Compare expected matches and negative cases in tracing, then use an explicit reviewed lifecycle transition.

### Unit Testing

Use a mocked transport for SDK unit tests and an isolated project for integration tests. Cover positive, negative, missing/null, boundary, duplicate, shadow, canary, approval, and dry-run cases relevant to the policy. A test that calls a real service with credentials is an integration test, not an isolated unit test.

## Error Handling

Catch `AMIError` from `memrail.errors` or narrower types such as `AMIBadRequest`, `AMIConflict`, `AMIUnauthorized`, `AMIForbidden`, `AMINotFound`, `AMIUnprocessable`, `AMIRateLimited`, and `AMIServerError`.

Use the SDK's bounded retry configuration where appropriate. Do not retry validation/authentication failures unchanged. Retrying a business handler after an uncertain outcome requires application-level duplicate protection; request-level idempotency alone does not provide it.

## Tool Management

```bash
memrail tool-list --help
memrail tool-register --help
memrail action-connectivity -w staging -p support
```

Follow the [tool registry reference](09-tool-registry-executors.md) for module-level schema discovery, project visibility, handlers, and execution configuration.

## Workspace Management

### Purging a Workspace

Purging is destructive and requires an org-level API key. Only do it when the user authorizes that exact workspace and target set; do not infer permission from a debugging request.

```bash
memrail purge-workspace development --targets emus,traces,events
```

Inspect the confirmation and installed command's `--help`. Use `--yes` only in an already-authorized reset workflow.

## EMU Validation Reports

### Agent Validation Workflow

```bash
memrail emu-plan ./emus/ -w staging -p support --strict
memrail emu-apply ./emus/ -w staging -p support --strict --yes
```

Strict validation rejects errors, missing reports, or unavailable validation before writes. `--validate` requests diagnostics but is not the strict gate. See [JSONL validation](12-emu-jsonl-workflow.md#candidate-validation) for deployment details.

### SDK Validation (Programmatic)

For proposed definitions, `await client.validate_emu_candidates(candidates, workspace=..., project=...)` performs scoped read-only validation. Use complete wire-format EMUs, including explicit policy and intended state; inspect each `reports[].report`.

For existing EMUs, use the CLI's `emu-validate` command or the installed client's available validator methods. Do not assume methods exposed on the synchronous client also exist on the asynchronous client.

### Warning Code Reference

| Code | Meaning | Response |
|---|---|---|
| `WARN-NEVER-SEEN` | ATOM not observed in the registry | Check producer, spelling, and scope |
| `WARN-SCHEMA-MISMATCH` | Type/operator mismatch | Correct the contract or expression |
| `WARN-LOW-REACH` | Stale/low-reach dependency | Check the producer and expected traffic |
| `WARN-ACTION-TOOL-NOT-FOUND` | Registered tool unavailable | Check tool registration/project visibility |
| `WARN-ACTION-PLACEHOLDER-NEVER-SEEN` | Unobserved template input | Ensure the invocation provides that fact |
| `WARN-POLICY-GAP` | Execution controls absent or ineffective | Review cooldown and structured idempotency |

Reports provide evidence, not automatic proof of business correctness. Review any proposed remediation before changing policy.

## Best Practices

Keep policy in reviewed JSONL, preserve provenance and selection metadata, and test execution separately from matching. Collect outcome evidence for improvement; keep deployment and lifecycle changes explicit.
