# EMU JSONL Sync Workflow

**The ONLY recommended approach for production EMU management.**

## Why JSONL Sync for Write Operations?

| Feature | JSONL Sync | SDK Write Methods |
|---------|------------|-------------------|
| Version control | Git-tracked | Not tracked |
| PR reviews | One EMU per line, diff-friendly | Code changes only |
| Rollback | `git revert` | Manual |
| Team coordination | Lock file prevents conflicts | Race conditions |
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
ami emu-pull ./emus/ -w production -p my-project

# Output files created:
# ./emus/emus.jsonl        - EMU definitions (edit this)
# ./emus/.emu.lock.jsonl   - Lock file (auto-managed, commit to git)
```

### Plan: Preview Changes

```bash
# Show what would change (like terraform plan)
ami emu-plan ./emus/

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
ami emu-apply ./emus/

# Apply changes (skip confirmation - for CI/CD)
ami emu-apply ./emus/ --yes

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
ami emu-diff ./emus/ vip_escalation

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
"idempotency": {"enabled": true, "boundary": "workspace", "roles": "auto", "scope": ["reminder:{{id}}"]}

// WRONG — not recognized by API
"idempotency_key": "reminder:{{id}}"
```

### 5. Trigger namespace keys need 2+ dot segments

State/tag keys must have at least two segments matching `^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+$`.

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

## JSONL Format

Each line is a complete EMU definition in JSON:

```jsonl
{"emu_key":"vip_escalation","trigger":"state.customer.tier == 'vip' AND state.ticket.priority >= 'high'","action":{"type":"tool_call","intent":"ESCALATE_VIP","tool":{"tool_id":"zendesk_escalator","version":"1.0.0","args":{"queue":"vip-support"}}},"policy":{"mode":"auto","priority":9,"cooldown":{"seconds":7200,"gate":"ack"}},"expected_utility":0.95,"confidence":0.88}
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

**context_directive** (always reachable):
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
| `mode` | `auto`, `suggest`, `disabled` | Execution mode |
| `priority` | 1-10 | Higher = more important |
| `cooldown.seconds` | integer | Minimum time between activations |
| `cooldown.gate` | `activation`, `execution` | When cooldown starts |
| `exclusion_groups` | string[] | Mutual exclusion with other EMUs |

## Practical Examples

### Adding a New EMU

1. Edit `./emus/emus.jsonl` and add a new line:
```jsonl
{"emu_key":"sla_breach_warning","trigger":"state.ticket.sla_remaining_hours < 4 AND NOT event.agent.warned.sla IN 'PT2H'","action":{"type":"tool_call","intent":"WARN_SLA_BREACH","tool":{"tool_id":"slack_notify","version":"1.0.0","args":{"channel":"#support-alerts","message":"SLA breach imminent"}}},"policy":{"mode":"auto","priority":8,"cooldown":{"seconds":7200,"gate":"ack"}},"expected_utility":0.9,"confidence":0.85}
```

2. Plan:
```bash
ami emu-plan ./emus/
# + sla_breach_warning (new)
```

3. Apply:
```bash
ami emu-apply ./emus/ --yes
# [+] Created sla_breach_warning (v1)
```

### Modifying an Existing EMU

1. Edit the line in `./emus/emus.jsonl`:
```jsonl
{"emu_key":"vip_escalation","trigger":"state.customer.tier IN ['vip', 'enterprise'] AND state.ticket.priority >= 'high'","action":{"type":"tool_call","intent":"ESCALATE_VIP","tool":{"tool_id":"zendesk_escalator","version":"1.0.0","args":{"queue":"vip-support"}}},"policy":{"mode":"auto","priority":10,"cooldown":{"seconds":3600,"gate":"ack"}},"expected_utility":0.95,"confidence":0.9}
```

2. Plan shows the diff:
```bash
ami emu-plan ./emus/
# ~ vip_escalation (modified)
#   trigger: "state.customer.tier == 'vip'" -> "state.customer.tier IN ['vip', 'enterprise']"
#   policy.priority: 9 -> 10
#   policy.cooldown.seconds: 7200 -> 3600
```

3. Apply:
```bash
ami emu-apply ./emus/ --yes
# [~] Updated vip_escalation (v1 -> v2)
```

### Archiving an EMU

1. Remove the line from `./emus/emus.jsonl`

2. Plan:
```bash
ami emu-plan ./emus/
# - old_feature (will archive)
```

3. Apply:
```bash
ami emu-apply ./emus/ --yes
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

## CI/CD Integration

### GitHub Actions

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
        run: pip install memrail-cli

      - name: Plan EMU changes
        run: ami emu-plan ./emus/ --json > plan.json
        env:
          AMI_API_KEY: ${{ secrets.AMI_API_KEY }}

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

      - name: Apply EMU changes
        run: ami emu-apply ./emus/ --yes
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
        entry: ami emu-validate ./emus/
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
ami emu-pull ./emus/ -w production -p my-project
```

### "Lock file out of sync"

```bash
# Re-pull to refresh lock file
ami emu-pull ./emus/ -w production -p my-project --force
```

### "Conflict: EMU modified remotely"

```bash
# Pull remote changes first
ami emu-pull ./emus/ -w production -p my-project

# Resolve conflicts in emus.jsonl
# Then re-apply
ami emu-apply ./emus/ --yes
```

### "Invalid JSONL syntax"

```bash
# Validate JSONL format
ami emu-validate ./emus/

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
| **Read** (list, get, query) | SDK ✓ | `list_emus()`, `get_emu()`, `invoke()` |
| **Write** (create, update, archive) | JSONL ✓ | `emu-pull`, `emu-plan`, `emu-apply` |

### SDK Read Operations (Always OK)

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
**Last Updated**: 2025-02-16
