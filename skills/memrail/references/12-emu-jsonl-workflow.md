# EMU JSONL Sync Workflow

**The ONLY recommended approach for production EMU management.**

## Why JSONL Sync for Write Operations?

| Feature | JSONL Sync | SDK Write Methods |
|---------|------------|-------------------|
| Version control | Git-tracked | Not tracked |
| PR reviews | One EMU per line, diff-friendly | Code changes only |
| Rollback | Revert desired JSONL, review plan, apply | Manual |
| Team coordination | Lock file tracks the last synced content | Race conditions |
| CI/CD | Native support | Custom scripts |
| Audit trail | Git history | API logs only |
| Production writes | **REQUIRED** | **NOT ALLOWED** |
| Read operations | N/A | **ALLOWED** (list, get, invoke) |

## The Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. PULL                    2. EDIT                             │
│  emu-pull ./emus/           vim ./emus/emus.jsonl              │
│       │                           │                             │
│       ▼                           ▼                             │
│  ┌──────────┐              ┌──────────────┐                    │
│  │ Remote   │              │ Local JSONL  │                    │
│  │ EMUs     │◄────────────►│ + Lock File  │                    │
│  └──────────┘              └──────────────┘                    │
│       ▲                           │                             │
│       │                           ▼                             │
│  4. APPLY                   3. PLAN                             │
│  emu-apply ./emus/          emu-plan ./emus/                   │
│  (creates/updates/archives) (shows diff)                        │
└─────────────────────────────────────────────────────────────────┘
```

## Commands Reference

### Pull: Download Remote EMUs

```bash
# Pull all EMUs from a workspace/project
memrail emu-pull ./emus/ -w production -p my-project

# Output files created:
# ./emus/emus.jsonl        - EMU definitions (edit this)
# ./emus/.emu.lock.jsonl   - Lock file (auto-managed, commit to git)
```

### Plan: Preview Changes

```bash
# Show what would change (like terraform plan)
memrail emu-plan ./emus/

# Output example:
# Plan: 2 to add, 1 to change, 1 to archive
#
# + new_vip_escalation (new)
# + premium_onboarding (new)
# ~ existing_feature (modified)
#   trigger: "state.user.tier == 'gold'" -> "state.user.tier IN ['gold', 'platinum']"
# - deprecated_rule (will archive)
```

### Apply: Push Changes

```bash
# Apply changes (interactive confirmation)
memrail emu-apply ./emus/

# Apply changes (skip confirmation - for CI/CD)
memrail emu-apply ./emus/ --yes

# Output example:
# Applying 4 changes...
# [+] Created new_vip_escalation (v1)
# [+] Created premium_onboarding (v1)
# [~] Updated existing_feature (v1 -> v2)
# [-] Archived deprecated_rule
#
# Success: 4/4 changes applied
```

### Diff: Detailed Comparison

```bash
# Show detailed diff for specific EMU
memrail emu-diff ./emus/ vip_escalation

# Output shows field-by-field comparison
```

## API Validation Rules (CRITICAL)

These rules are enforced by the Memrail API at registration time. Violations return HTTP 422 with `"Request validation failed"`. Always follow these exactly:

### 1. `tool.version` is REQUIRED for `tool_call` actions

Every `tool_call` action must include `tool.version`. The API uses a discriminated union — without `version`, it fails to match the `ActionToolCall` schema and rejects the entire payload.

```json
// CORRECT
{"type": "tool_call", "intent": "SEND_EMAIL", "tool": {"tool_id": "mailer", "version": "1.0.0", "args": {...}}}

// WRONG — 422 error
{"type": "tool_call", "intent": "SEND_EMAIL", "tool": {"tool_id": "mailer", "args": {...}}}
```

### 2. `state` must be lowercase

Valid values: `draft`, `shadow`, `canary`, `active`, `inactive`, `archived`. Uppercase values like `ACTIVE` or `SHADOW` cause 422.

### 3. `cooldown` must be a `{seconds, gate}` object

Never use ISO 8601 duration strings. The API expects an integer `seconds` field.

```json
// CORRECT
"cooldown": {"seconds": 172800, "gate": "ack"}

// WRONG — not recognized by API
"cooldown_iso": "PT48H"
"cooldown": "PT48H"
```

Common conversions: PT1H=3600, PT12H=43200, PT24H=86400, PT48H=172800, P7D=604800, P14D=1209600, P30D=2592000.

### 4. `idempotency` must be a structured object

```json
// CORRECT
"idempotency": {"enabled": true, "boundary": "workspace", "roles": "auto", "scope": ["reminder.id"]}

// WRONG — not recognized by API
"idempotency_key": "reminder:{{id}}"
```

### 5. Trigger namespace keys need 2+ dot segments

State keys must have at least two segments matching `^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+$`.

```javascript
// CORRECT
state.user.tier == 'premium'
state.engagement.status == 'pending'

// WRONG — 400 "Invalid namespace key format"
state.test == true
state.active == true
```

### 6. Auth scheme is `AMI-Key`, not `Bearer`

```
Authorization: AMI-Key <your-api-key>
```

## Candidate Validation

Check `memrail emu-plan --help` and `memrail emu-apply --help` for `--strict` before selecting this workflow. A newly merged capability may not yet exist in the published package.

```bash
memrail emu-plan ./emus/ -w staging -p support --strict
memrail emu-apply ./emus/ -w staging -p support --strict --yes
```

Both commands validate proposed definitions against the scoped server registry before writes. Strict mode stops for errors, unavailable validation, or incomplete reports. `--validate` requests diagnostics but does not impose the strict gate; `--validate-only` is local JSONL/DSL validation and cannot be combined with strict mode. `emu-validate` checks already-deployed EMUs, not pending JSONL edits.

The candidate endpoint is `POST /v1/workspaces/{workspace}/projects/{project}/emus/validate-candidates`, with `{"candidates": [...]}` containing 1–100 complete, uniquely keyed EMUs. Validation is read-only. Review business tests as well as static reports. Apply preflights all candidate batches, but the subsequent multi-record writes are not an atomic transaction.

## Lifecycle and Decision-Point Intent

New EMUs default to draft. Set `--target-state shadow` for new shadow records, and make any explicit JSONL state agree with that target. Existing lifecycle changes use an explicit reviewed `memrail change-state` operation; plan/apply rejects conflicting lifecycle intent rather than silently ignoring or applying it. Omitting state preserves the existing lifecycle.

A JSONL `decision_point` binds the EMU to an exact invocation site. Omission preserves an existing binding; explicit null clears it. Keep the calling code and policy binding in the same review.

## JSONL Format

Each line is a complete EMU definition in JSON:

```jsonl
{"emu_key":"vip_escalation","trigger":"state.customer.tier == 'vip' AND state.ticket.priority == 'high'","action":{"type":"tool_call","intent":"ESCALATE_VIP","tool":{"tool_id":"zendesk_escalator","version":"1.0.0","args":{"queue":"vip-support"}}},"policy":{"mode":"auto","priority":9,"cooldown":{"seconds":7200,"gate":"ack"}},"expected_utility":0.95,"confidence":0.88}
{"emu_key":"welcome_premium","trigger":"state.user.tier == 'premium'","action":{"type":"tool_call","intent":"SEND_WELCOME","tool":{"tool_id":"mailer","version":"1.0.0","args":{"template":"premium_welcome"}}},"policy":{"mode":"auto","priority":5,"cooldown":{"seconds":86400,"gate":"ack"}},"expected_utility":0.9,"confidence":0.95}
```

### EMU Fields

| Field | Required | Description |
|-------|----------|-------------|
| `emu_key` | Yes | Unique identifier (e.g., `vip_escalation`, `billing.payment_retry`) |
| `trigger` | Yes | DSL expression that evaluates to boolean |
| `action` | Yes | What to do when triggered |
| `expected_utility` | Yes | Expected value (0.0-1.0) |
| `confidence` | Yes | Confidence in utility estimate (0.0-1.0) |
| `policy` | No | Execution policy (mode, priority, cooldown) |
| `intent` | No | Human-readable description |

### Action Types

**tool_call** (most common):
```json
{
  "type": "tool_call",
  "intent": "ESCALATE_TICKET",
  "tool": {
    "tool_id": "escalate_ticket",
    "version": "1.0.0",
    "args": {"queue": "vip-support", "priority": "critical"}
  }
}
```

**context_directive** (requires an application handler):
```json
{
  "type": "context_directive",
  "directive": "Customer is VIP tier. Follow escalation protocol."
}
```

**route**:
```json
{
  "type": "route",
  "destination": "spanish_support_queue",
  "metadata": {"language": "spanish"}
}
```

**decision_prompt**:
```json
{
  "type": "decision_prompt",
  "message": "High-value transaction detected. Approve?",
  "options": [
    {"id": "approve", "label": "Approve"},
    {"id": "decline", "label": "Decline"}
  ]
}
```

### Policy Configuration

```json
{
  "mode": "auto",
  "priority": 9,
  "cooldown": {"seconds": 7200, "gate": "activation"},
  "idempotency": {"enabled": true, "scope": ["customer.id", "ticket.id"]},
  "exclusion_groups": ["escalation_actions"]
}
```

| Field | Values | Description |
|-------|--------|-------------|
| `mode` | `auto`, `require_human`, `advisory` | Execution mode |
| `priority` | 0-9 | Higher = more important |
| `cooldown.seconds` | integer | Minimum time between activations |
| `cooldown.gate` | `activation`, `ack` | When cooldown starts |
| `exclusion_groups` | string[] | Mutual exclusion with other EMUs |

## Practical Examples

### Adding a New EMU

1. Edit `./emus/emus.jsonl` and add a new line:
```jsonl
{"emu_key":"sla_breach_warning","trigger":"state.ticket.sla_remaining_hours < 4 AND NOT event.agent.warned.sla IN 'PT2H'","action":{"type":"tool_call","intent":"WARN_SLA_BREACH","tool":{"tool_id":"slack_notify","version":"1.0.0","args":{"channel":"#support-alerts","message":"SLA breach imminent"}}},"policy":{"mode":"auto","priority":8,"cooldown":{"seconds":7200,"gate":"ack"}},"expected_utility":0.9,"confidence":0.85}
```

2. Plan:
```bash
memrail emu-plan ./emus/
# + sla_breach_warning (new)
```

3. Apply:
```bash
memrail emu-apply ./emus/ --yes
# [+] Created sla_breach_warning (v1)
```

### Modifying an Existing EMU

1. Edit the line in `./emus/emus.jsonl`:
```jsonl
{"emu_key":"vip_escalation","trigger":"state.customer.tier IN ['vip', 'enterprise'] AND state.ticket.priority == 'high'","action":{"type":"tool_call","intent":"ESCALATE_VIP","tool":{"tool_id":"zendesk_escalator","version":"1.0.0","args":{"queue":"vip-support"}}},"policy":{"mode":"auto","priority":9,"cooldown":{"seconds":3600,"gate":"ack"}},"expected_utility":0.95,"confidence":0.9}
```

2. Plan shows the diff:
```bash
memrail emu-plan ./emus/
# ~ vip_escalation (modified)
#   trigger: "state.customer.tier == 'vip'" -> "state.customer.tier IN ['vip', 'enterprise']"
#   policy.priority: 9 (unchanged)
#   policy.cooldown.seconds: 7200 -> 3600
```

3. Apply:
```bash
memrail emu-apply ./emus/ --yes
# [~] Updated vip_escalation (v1 -> v2)
```

### Archiving an EMU

1. Remove the line from `./emus/emus.jsonl`

2. Plan:
```bash
memrail emu-plan ./emus/
# - old_feature (will archive)
```

3. Apply:
```bash
memrail emu-apply ./emus/ --yes
# [-] Archived old_feature
```

## Lock File

The `.emu.lock.jsonl` file tracks deployed state:

```jsonl
{"emu_key":"vip_escalation","version":2,"content_hash":"a1b2c3d4","deployed_at":"2025-02-15T10:30:00Z"}
{"emu_key":"welcome_premium","version":1,"content_hash":"e5f6g7h8","deployed_at":"2025-02-14T09:00:00Z"}
```

**Important:**
- Auto-generated by `emu-apply`
- Commit to version control
- Enables intelligent diffing (content hash comparison)
- Tracks version history

The lock file is local sync bookkeeping, not a distributed mutex or remote compare-and-swap guarantee. Serialize deployments and compare current remote state before applying. Reverting JSONL requires another reviewed plan/apply; it cannot undo completed business effects.

## CI/CD Integration

### GitHub Actions

Pin the CLI to a tested release exposing the required flags. This workflow skeleton requires repository deployment concurrency and credentials scoped to the intended environment.

```yaml
# .github/workflows/emu-deploy.yml
name: Deploy EMUs

on:
  push:
    branches: [main]
    paths: ['emus/**']
  pull_request:
    paths: ['emus/**']

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Memrail CLI
        run: pip install memrail

      - name: Plan EMU changes
        run: memrail emu-plan ./emus/ --strict --json > plan.json
        env:
          AMI_API_KEY: ${{ secrets.AMI_API_KEY }}
          AMI_WORKSPACE: production
          AMI_PROJECT: my-project

      - name: Comment PR with plan
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const plan = require('./plan.json')
            // Format and post comment...

  apply:
    if: github.ref == 'refs/heads/main'
    needs: plan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Memrail CLI
        run: pip install memrail

      - name: Apply EMU changes
        run: memrail emu-apply ./emus/ --strict --yes
        env:
          AMI_API_KEY: ${{ secrets.AMI_API_KEY }}
          AMI_WORKSPACE: production
          AMI_PROJECT: my-project
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: emu-validate
        name: Validate EMU JSONL
        entry: memrail emu-plan ./emus/ --validate-only
        pass_filenames: false
        language: system
        files: 'emus/.*\.jsonl$'
```

## Project Structure

```
my-project/
├── emus/
│   ├── emus.jsonl           # EMU definitions (edit this)
│   └── .emu.lock.jsonl      # Lock file (auto-managed)
├── src/
│   └── ami/
│       ├── atoms.py         # ATOM builders
│       └── tools.py         # Tool handlers
└── .github/
    └── workflows/
        └── emu-deploy.yml   # CI/CD pipeline
```

## Troubleshooting

### "EMU not found in remote"

```bash
# Pull first to sync state
memrail emu-pull ./emus/ -w production -p my-project
```

### "Lock file out of sync"

```bash
# Pull into a separate directory; compare before replacing local work
memrail emu-pull ./remote-emus/ -w production -p my-project
```

### Remote EMUs changed during editing

```bash
 # Pull into a separate directory to preserve uncommitted edits
memrail emu-pull ./remote-emus/ -w production -p my-project

# Resolve conflicts in emus.jsonl
# Then re-apply
memrail emu-apply ./emus/ --yes
```

### "Invalid JSONL syntax"

```bash
# Validate JSONL format
memrail emu-plan ./emus/ --validate-only

# Common issues:
# - Missing commas
# - Unescaped quotes
# - Trailing commas (not allowed in JSON)
# - Multiple EMUs on same line
```

## Best Practices

1. **One EMU per line** - Makes git diffs readable
2. **Commit lock file** - Enables team coordination
3. **Always plan before apply** - Review changes
4. **Use descriptive emu_keys** - `billing.payment_retry` not `emu1`
5. **Set appropriate cooldowns** - Prevent action spam
6. **Start in shadow mode** - Test before production
7. **CI/CD for production** - Never manual applies

## SDK vs JSONL: The Rule

| Operation Type | Use | Method |
|----------------|-----|--------|
| **Inspect/evaluate** (list, get, decide) | SDK ✓ | `list_emus()`, `get_emu()`, `decide()` |
| **Write** (create, update, archive) | JSONL ✓ | `emu-pull`, `emu-plan`, `emu-apply` |

### SDK Inspection and Evaluation

Invocation can record traces, accounting, and activation controls; it is not a pure read. Use dry-run for diagnostic evaluation.

```python
async with AsyncAMIClient() as client:
    # List EMUs
    emus = await client.list_emus(workspace="production", project="support")

    # Get single EMU
    emu = await client.get_emu(emu_key="vip_escalation", workspace="production", project="support")

    # Invoke decision engine
    response = await client.decide(context=[...])
```

### SDK Write Operations (Testing/Prototyping ONLY)

SDK write methods (`register_emu()`, `update_emu()`, `update_emu_lifecycle()`) exist but should **only** be used for:

- Unit tests with temporary EMUs
- Local development prototyping
- One-time migration scripts

**Never use SDK write operations for production EMUs.**

---

**Version**: AMI v2 (IaC JSONL Sync)
**Last Updated**: 2026-09-10
