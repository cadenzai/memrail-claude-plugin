# SDK Integration (TypeScript)

## Installation

Install `@memrail/sdk` in your TypeScript project:

```bash
npm install @memrail/sdk
```

The `memrail` CLI is distributed with the Python package, not the npm package. Install it in a virtual environment for the [JSONL workflow](12-emu-jsonl-workflow.md). Check installed versions and command help before relying on a new capability: merged source and published packages may differ.

## Configuration

Keep credentials outside source control. The client reads `AMI_API_KEY`, `AMI_ORG`, `AMI_TEAM`, `AMI_WORKSPACE`, `AMI_PROJECT`, and `AMI_BASE_URL` when environment loading is enabled.

```typescript
import { AMIClient } from '@memrail/sdk';

const client = new AMIClient({
    workspace: "staging",
    project: "support"
});
```

Explicit configuration overrides environment values. Workspace/project arguments on individual calls override client configuration. Use explicit scope for deployments and tenant-sensitive operations.

## ATOM Builders

State keys use lowercase dotted names. Tag kinds may be single-segment. Preserve actual provenance and keep ML classifications within a fixed taxonomy.

```typescript
import { state, tag, atomsFromDict } from '@memrail/sdk';

const context = [
    state("ticket.id", "T-456"),
    state("ticket.priority", "high", "system"),
    tag("sentiment", "negative", "ml"),
    ...atomsFromDict({
        id: "U-123", tier: "premium", preferences: { language: "en" }
    }, "user")
];
```

`atomsFromDict` flattens nested objects. Match the policy's expected scalar types rather than silently converting absent facts into affirmative defaults. The application must prevent model output from impersonating trusted facts.

### Event ATOMs

```typescript
import { event } from '@memrail/sdk';

const emailSent = event("agent.sent.email", {
    ts: new Date(),
    subject_anchor: ["agent", "A-123"],
    object_anchor: ["email", "E-456"],
    attributes: { user_id: "U-123", template: "welcome" }
});
```

Use subject.verb.object topics, timestamps, and entity identifiers consistently. Building an event atom does not persist it.

## EMU Management

Use [JSONL sync](12-emu-jsonl-workflow.md) for production definitions. SDK registration/update methods are for isolated tests and authorized migration tooling.

```bash
memrail emu-pull ./emus/ -w staging -p support
memrail emu-plan ./emus/ -w staging -p support --strict
memrail emu-apply ./emus/ -w staging -p support --strict --yes
```

New records default to draft. `--target-state` controls new records, not silent promotion of existing ones. Explicit JSONL lifecycle intent must agree with the chosen transition workflow; omission preserves existing state. An omitted `decision_point` preserves its existing binding, while explicit null clears it.

Wire-format policy modes are `auto`, `require_human`, and `advisory`; priority is 0–9. See [EMU Fundamentals](01-emu-fundamentals.md) for complete action and policy shapes.

## Invoking the Engine

```typescript
import { AMIClient, state, tag } from '@memrail/sdk';

async function inspectTicket() {
    const client = new AMIClient({ workspace: "staging", project: "support" });
    const response = await client.decide({
        context: [
            state("ticket.id", "T-456"),
            state("ticket.priority", "high"),
            tag("sentiment", "negative", "ml")
        ],
        decisionPoint: "triage",
        options: { dry_run: true },
        trace: { enable: true }
    });
    for (const item of response.selected) {
        console.log(item.emu_key, item.emu_version, item.lifecycle_state);
        console.log(item.policy, item.action);
    }
    for (const candidate of response.trace?.candidates ?? []) {
        console.log(candidate.emu_key, candidate.passed, candidate.suppressed_by);
    }
    return response;
}
```

A named `decisionPoint` selects EMUs bound to that exact site; it is not only an analytics label. The SDK accepts `context` or `atoms`, not both. The HTTP body uses `context_atoms`.

### With Options

Method arguments such as `decisionPoint`, `contextTs`, and `idempotencyKey` are camelCase. Fields inside `options` are **snake_case**: `dry_run`, `top_k`, `human_consent`, `store_read_cutoff_ts`, `pin_registry_version`, `pin_policy_version`. Trace options expose `enable`, not `includeAllEmus` or `explain`.

Top-k is constrained by arbitration and exclusion groups. A candidate may pass its trigger and still be suppressed.

### With Idempotency

`idempotencyKey` is for retrying an identical logical invocation. During its cache lifetime, reusing the same key with a different normalized context, decision point, options, or project conflicts. Use a new key for a genuinely new request.

Invocation caching, structured policy idempotency, and business-operation deduplication are different controls. A cached selection does not prove a tool executed exactly once.

### Response Handling

Selections expose `action`, `policy`, `lifecycle_state`, `emu_version`, `activation_id`, and `score`. The SDK adapts the HTTP `payload` field to `action`. Do not assume `priority` or `processing_time_ms` exists on the response.

`decide` does not dispatch actions. Use [the combined helper](09-tool-registry-executors.md#decide-and-execute) to preserve policy and lifecycle checks; do not blindly call every selected tool.

## Event Ingestion

```typescript
import { AMIClient, event } from '@memrail/sdk';

async function recordEmail() {
    const client = new AMIClient({ workspace: "staging", project: "support" });
    return client.emitEvent({
        event: event("agent.sent.email", {
            ts: new Date(),
            attributes: { user_id: "U-123" }
        })
    });
}
```

For batches, use `client.emitEvents({ events: [emailSent], workspace: ..., project: ... })` with EventAtom instances, not raw subject/verb/object objects. Emit actual outcomes after actions; avoid blind ingestion retries that could double-count events.

## Complete Workflows

Load trusted application facts, add constrained classification tags, call the matching decision point, then execute with the configured client helper. Use real application handlers with authorization and operation-level deduplication. Record outcomes and inspect execution results. See [Tool Registry & Executors](09-tool-registry-executors.md) for a complete integration.

## Testing & Debugging

### Dry Run Mode

Use `options: { dry_run: true }`. The combined helper skips handlers and ACK. Dry-run also avoids activation locks, but diagnostics/accounting may still be recorded.

### Tracing

Inspect `response.trace?.candidates`. Candidate fields include `emu_key`, `passed`, `reasons`, and `suppressed_by`, using wire-format snake_case names.

### Shadow Mode Testing

Server-side shadow EMUs are diagnostic trace candidates, not executable selections. Shadow arbitration is separate from live arbitration. Review positive and negative cases before explicitly promoting a policy.

### Unit Testing

Mock the SDK transport for unit tests. Use an isolated project for live integration tests and exercise missing/null inputs, boundaries, duplicates, approval, lifecycle, and dry-run behavior relevant to the policy. Never use production credentials for a destructive test reset.

## Error Handling

Catch `AMIError` or narrower exported classes such as `AMIBadRequest`, `AMIConflict`, `AMIUnauthorized`, `AMIForbidden`, `AMINotFound`, `AMIUnprocessable`, `AMIRateLimited`, and `AMIServerError`.

Use bounded retries for transient failures. Do not retry unchanged invalid requests or assume a request-level key prevents duplicate business effects after a timeout.

## CLI Commands

Install the Python-distributed `memrail` CLI even if the application uses TypeScript. See the [command reference](05-sdk-integration-python.md#cli-commands) and check each installed command's `--help`.

## Workspace Management

Purging is destructive and requires org-level credentials. Only reset an explicitly authorized workspace/target set; a debugging request does not authorize a purge.

```bash
memrail purge-workspace development --targets emus,traces,events
```

Review the confirmation. Add `--yes` only for a previously authorized reset workflow.

## EMU Validation Reports

### Agent Validation Workflow

Use `emu-plan --strict` and `emu-apply --strict` to validate candidates before writes. `--validate` requests diagnostics; it is not the strict gate. `emu-validate` checks deployed records. See [candidate validation](12-emu-jsonl-workflow.md#candidate-validation).

For programmatic preflight, `client.validateEMUCandidates({ candidates, workspace, project })` accepts complete wire-format EMUs. Inspect every `reports[].report`. This endpoint is scoped and read-only.

For existing records, use `client.getEMUValidator(emuKey, { workspace })` or `client.validateWorkspaceEMUs({ workspace })` where exposed by the installed SDK.

### Warning Code Reference

Use the [shared warning reference](05-sdk-integration-python.md#warning-code-reference). Validate remediation against the intended policy before applying it; a passing static report is not a substitute for business tests.

## Best Practices

Keep production policy in reviewed JSONL. Preserve source, policy, and lifecycle metadata through integration boundaries. Separate selection tests from execution tests and make lifecycle promotion an explicit reviewed action.
