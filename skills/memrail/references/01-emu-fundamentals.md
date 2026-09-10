# EMU Fundamentals

**Understanding Executable Memory Units**

## Table of Contents

- [What is an EMU?](#what-is-an-emu)
- [EMU Structure](#emu-structure)
- [EMU Lifecycle](#emu-lifecycle)
- [Action Types](#action-types)
- [Policy Configuration](#policy-configuration)
- [Versioning](#versioning)
- [Best Practices](#best-practices)

## What is an EMU?

An **Executable Memory Unit (EMU)** is a conditional action definition that fires deterministically based on system state. Think of it as an "if-then" rule with sophisticated triggering logic and execution policies.

### Core Characteristics

1. **Deterministic**: Same policy, context, time, retained history, and control state → same decision
2. **Conditional**: Fires only when trigger evaluates to TRUE
3. **Typed**: Uses strongly-typed ATOMs (facts) for decision-making
4. **Versioned**: Supports iterative refinement with version tracking
5. **Project-scoped**: Each EMU belongs to a specific project

### When to Use EMUs

EMUs are ideal for:

- **Workflow automation**: Route tickets, escalate issues, send notifications
- **Business rules**: Apply policies based on customer tier, urgency, SLA
- **Operational intelligence**: Alert on system health, compliance triggers
- **Customer engagement**: Personalized outreach based on behavior patterns
- **Decision support**: Present options to humans when confidence is low

### When NOT to Use EMUs

Avoid EMUs for:

- **Random/probabilistic logic**: EMUs are deterministic
- **Stateless operations**: If no state/context needed, use simpler webhooks
- **Real-time streaming**: EMUs are pull-based (invoke), not push-based
- **Complex ML inference**: Use ML services, expose results as ATOMs

## EMU Structure

An EMU definition contains these fields:

```python
{
    "emu_key": str,              # Unique identifier
    "trigger": str,              # DSL expression (when to fire)
    "action": dict,              # What to execute
    "policy": dict,              # How to execute
    "expected_utility": float,   # Expected value (0.0-1.0)
    "confidence": float,         # Confidence level (0.0-1.0)
    "intent": str,               # Human-readable description (optional)
    "state": str,                # Lifecycle state
    "metadata": dict,            # Custom metadata (optional)
    "decision_point": str        # Named invocation site (optional)
}
```

### 1. emu_key

**Format**: 3–128 lowercase letters, digits, colons, underscores, dots, or hyphens
**Pattern**: `^[a-z0-9:_.-]{3,128}$`

```python
# Valid
"welcome_premium_users"
"emu:support.vip_escalation"
"sales.lead_qualification_v2"

# Invalid
"WelcomeUsers"           # Uppercase
"welcome users"          # Spaces not allowed
"ab"                     # Too short
```

**Best practices**:
- Use semantic naming: `support.vip_escalation` not `emu_12345`
- Include category prefix: `support.*`, `sales.*`, `ops.*`
- Avoid version suffixes (versioning is automatic): Use `lead_qualification`, not `lead_qualification_v2`

### 2. trigger

A DSL expression that evaluates to boolean (TRUE/FALSE).

```javascript
// Simple
state.user.tier == 'premium'

// Temporal
event.user.login.success IN 'PT24H'

// Complex
(state.ticket.priority == 'high' OR state.ticket.priority == 'critical') AND NOT event.agent.responded.ticket IN 'PT1H'

// With IN operator (cleaner)
state.ticket.priority IN ['high', 'critical'] AND NOT event.agent.responded.ticket IN 'PT1H'
```

See [DSL Reference](02-dsl-reference.md) for complete syntax.

### 3. action

Defines what to execute when trigger fires. Four types supported:

| Type | Purpose | Use Case |
|------|---------|----------|
| `tool_call` | Execute external tool/API | Send email, create ticket, call webhook |
| `decision_prompt` | Present options to human | Approval workflows, ambiguous situations |
| `route` | Route to destination/queue | Language routing, skill-based assignment |
| `context_directive` | Provide guidance/context | Suggest KB articles, display warnings |

See [Action Types](#action-types) section below for details.

### 4. policy

Controls execution behavior:

```python
{
    "mode": "auto",                    # auto | require_human | advisory
    "priority": 8,                     # 0-9 (higher = more important)
    "cooldown": {                      # Rate limiting
        "seconds": 3600,
        "gate": "activation"
    },
    "idempotency": {                   # Deduplication
        "enabled": true,
        "scope": ["user.id", "ticket.id"]
    },
    "exclusion_groups": ["escalations"] # Mutual exclusion
}
```

See [Policy Configuration](#policy-configuration) section below.

### 5. expected_utility

**Type**: `float` (0.0 to 1.0)
**Purpose**: Expected value/benefit of executing this action

Higher utility = higher priority in arbitration. Use for ranking EMUs when multiple match.

```python
# High-value actions
expected_utility=0.95  # Critical system alert
expected_utility=0.90  # VIP customer escalation

# Medium-value actions
expected_utility=0.75  # Routine follow-up email
expected_utility=0.70  # Onboarding nudge

# Low-value actions
expected_utility=0.50  # Satisfaction survey
expected_utility=0.30  # Optional KB suggestion
```

### 6. confidence

**Type**: `float` (0.0 to 1.0)
**Purpose**: Confidence that trigger+action are correct

Participates in scoring. It does not automatically change execution mode; set `policy.mode="require_human"` explicitly when approval is required.

```python
# High confidence
confidence=0.95  # Well-tested rule, clear conditions
confidence=0.90  # Mature EMU with good track record

# Medium confidence
confidence=0.75  # New EMU, still learning
confidence=0.70  # Ambiguous trigger conditions

# Low confidence
confidence=0.50  # Experimental EMU
confidence=0.40  # Requires human judgment
```

### 7. intent (optional)

Human-readable description of the EMU's purpose.

```python
intent="Escalate high-priority VIP tickets to specialist team within 1 hour"
intent="Send onboarding email to users who haven't completed setup after 24 hours"
intent="Alert on-call engineer when system error rate exceeds threshold"
```

### 8. state

Lifecycle state of the EMU:

| State | Description | Behavior |
|-------|-------------|----------|
| `active` | Production-ready, fully active | Fires normally |
| `canary` | Testing with an application-owned cohort | Executor requires an affirmative cohort decision |
| `draft` | New definition, not live | Not selected |
| `inactive` | Temporarily disabled | Not selected |
| `shadow` | Evaluation mode only | Trigger evaluated but action NOT executed |
| `archived` | Deprecated, inactive | Not evaluated |

### 9. decision_point (optional)

Named invocation site this EMU belongs to (e.g., `"triage"`, `"post-checkout"`). Scopes the EMU to a specific `decision_point` value passed in `decide()` calls, enabling per-point analytics and topology mapping.

**Pattern**: `^[a-z][a-z0-9._-]*$` (1-128 chars, lowercase, dots/hyphens/underscores)

```python
# EMU scoped to "triage" decision point
client.register_emu(
    emu_key="vip_escalation",
    trigger="state.ticket.priority >= 4",
    decision_point="triage",  # Associates EMU with this invocation site
    ...
)
```

## EMU Lifecycle

New records default to draft. A typical reviewed progression is draft → shadow → canary → active; inactive pauses a policy and archived retires it. Shadow evaluations remain diagnostic, while canary execution requires a configured application cohort.

### Version Progression

Manage definitions through [JSONL sync](12-emu-jsonl-workflow.md). Creating a new key creates version 1; updating that key creates the next integer version. Registering the same key again is a conflict, not the update workflow. Updating a definition does not implicitly promote its lifecycle.

Use `--target-state` for new records and an explicit lifecycle transition for existing records. Conflicting lifecycle intent in JSONL must be resolved before apply.

## Action Types

### 1. tool_call

Execute an external tool, API, or service.

```python
{
    "type": "tool_call",
    "intent": "SEND_WELCOME_EMAIL",  # Intent identifier
    "tool": {
        "tool_id": "mailer",         # Tool identifier
        "version": "1.0.0",           # Tool version
        "args": {                     # Tool-specific arguments
            "template": "premium_welcome",
            "recipient": "{{user.email}}",
            "priority": "high"
        }
    }
}
```

**Template variables**: Use `{{key}}` to inject ATOM values into args.

**Use cases**:
- Send email/SMS/Slack message
- Create ticket/task
- Call webhook
- Update database
- Trigger workflow

### 2. decision_prompt

Present options to a human for decision.

```python
{
    "type": "decision_prompt",
    "message": "High-risk transaction from {{user.id}}. Approve?",
    "options": [
        {"id": "approve", "label": "Approve Transaction"},
        {"id": "decline", "label": "Decline Transaction"},
        {"id": "review", "label": "Request Manual Review"}
    ]
}
```

**Use cases**:
- Approval workflows
- Ambiguous situations
- High-stakes decisions
- Compliance reviews

### 3. route

Route request to a destination, queue, or agent.

```python
{
    "type": "route",
    "destination": "spanish_support_queue",
    "metadata": {
        "priority": "high",
        "skill_required": "spanish"
    }
}
```

**Use cases**:
- Language-based routing
- Skill-based assignment
- Priority queue selection
- Geographic routing

### 4. context_directive

Provide context, guidance, or suggestions (no execution).

```python
{
    "type": "context_directive",
    "directive": "Customer is VIP tier. Follow escalation protocol per KB article #4521"
}
```

**Use cases**:
- KB article suggestions
- Policy reminders
- Warnings/alerts
- Context enrichment

## Policy Configuration

### Mode

Three execution modes:

```python
# AUTO: Execute automatically without human review
policy={"mode": "auto"}
# Use when: High confidence, low risk, routine operations

# REQUIRE_HUMAN: Present to human, require approval before execution
policy={"mode": "require_human"}
# Use when: Low confidence, high risk, compliance requirements

# ADVISORY: Show to human as suggestion, no execution
policy={"mode": "advisory"}
# Use when: Informational only, optional guidance
```

**Mode × Action Type behavior:**

| action.type | auto | require_human | advisory |
|---|---|---|---|
| `tool_call` | Eligible for dispatch | Explicit verified consent required | Not dispatched |
| `decision_prompt` | Eligible for dispatch | Explicit verified consent required | Advisory handler may run |
| `route` | Eligible for dispatch | Explicit verified consent required | Not dispatched |
| `context_directive` | Eligible for dispatch | Explicit verified consent required | Advisory handler may run |

The application owns approval collection and business authorization. A policy does not create an approval UI automatically. Preserve the returned policy when using the [executor](09-tool-registry-executors.md).

### Priority

**Range**: 0-9 (higher = more important)
**Purpose**: Rank EMUs when multiple fire simultaneously

```python
priority=9  # 8-9 Critical: system alerts, VIP escalations
priority=7  # 6-7 Important: SLA breaches, high-value customers
priority=5  # 4-5 Standard: routine workflows, notifications
priority=3  # 2-3 Optional: suggestions, enhancements
priority=1  # 0-1 Low: satisfaction surveys, analytics
```

### Cooldown

Suppress repeated activations for a chosen interval. Specify the gate explicitly: activation is based on evaluation context time; ACK starts after acknowledgment.

```python
{
    "cooldown": {
        "seconds": 3600,           # 1 hour (0 = no cooldown)
        "gate": "ack"              # When to start cooldown (default: "ack")
    }
}

# Gates (AMI v2):
# - "ack": Cooldown starts when acknowledgment received (choose when suppression should follow acknowledgment)
# - "activation": Cooldown starts immediately when EMU fires (choose when suppression should follow selection)
```

**Common patterns**:

```python
# Prevent duplicate emails (use ACK gate for deferred cooldown)
cooldown={"seconds": 86400, "gate": "ack"}  # 24 hours after ACK

# Rate-limit alerts (use activation gate for immediate cooldown)
cooldown={"seconds": 1800, "gate": "activation"}   # 30 minutes immediately

# Daily digest (30 days)
cooldown={"seconds": 2592000, "gate": "ack"}  # 30 days after ACK

# Hourly system checks
cooldown={"seconds": 3600, "gate": "activation"}  # 1 hour immediately
```

**Historical evaluation**: `context_ts` controls event-window evaluation; it does not reconstruct previous registry, cooldown, idempotency, or ACK state. Freeze the relevant inputs in an isolated replay test before claiming reproducible historical execution.

For a canary, successful execution ACK starts its controls; an unexecuted cohort selection must not consume them.

**Viewing cooldowns in the Customer Portal**:

The EMU detail modal in the customer portal displays cooldown information:
- **Duration**: Formatted as seconds (s), minutes (m), hours (h), or days (d)
- **Gate**: Shows "On ACK" or "On Activation"
- **Analytics**: "Cooldown Hits" metric shows how many times the EMU was suppressed due to active cooldowns

Example display:
```
Cooldown: 1h
Gate: On Activation
```

### Idempotency

Define structural suppression for a logical operation:

```json
{
  "idempotency": {
    "enabled": true,
    "boundary": "workspace",
    "roles": "auto",
    "scope": ["user.id", "order.id"],
    "ttl_sec": 7200
  }
}
```

Scope entries are literal state keys, not templates. Supply non-null values for every explicitly declared scope key or role; absent required inputs suppress selection. Zero and false are valid values. Choose a positive TTL for an effective suppression interval.

This is separate from the invocation request's idempotency key. Neither replaces transactional operation-level deduplication before a business side effect, especially with concurrent invocations or retries after an uncertain outcome.

### Exclusion Groups

Prevent multiple EMUs in same group from firing simultaneously.

```python
{
    "exclusion_groups": ["escalation_actions"]
}
```

If multiple eligible EMUs in `"escalation_actions"` match, arbitration selects a winner by score and configured tie-break order. A high priority alone is not a universal winning guarantee. Shadow arbitration is separate from live arbitration.

## Versioning

EMU versions are increasing integers per key, separate from the tool's version string. JSONL updates preserve history and the intended lifecycle. A newer version is not automatically active.

To test a candidate alongside a live policy, use a distinct reviewed candidate key and explicit rollout plan; do not assume registering the live key creates an independently selectable canary. Observe shadow matches, use an application cohort for canary execution, review outcome quality and negative tests, then promote deliberately.

## Best Practices

### 1. Start Simple

```javascript
// ✅ Good: Simple, testable
trigger="state.user.tier == 'premium'"

// Even better: Use IN operator for multiple values
trigger="state.user.tier IN ['premium', 'enterprise']"

// ❌ Bad: Too complex initially
trigger="(state.user.tier IN ['premium', 'enterprise']) AND (event.user.login.success IN 'PT24H' OR event.user.purchase.complete IN 'P7D') AND NOT (event.agent.sent.email IN 'PT48H' OR tag.unsubscribed == 'true')"
```

### 2. Use Semantic Naming

```python
# ✅ Good
emu_key="support.vip_escalation"
emu_key="sales.lead_qualification"

# ❌ Bad
emu_key="emu_42"
emu_key="my_test_rule"
```

### 3. Set Appropriate Policies

```python
# ✅ Good: High-value, tested EMU
{
    "mode": "auto",
    "priority": 8,
    "cooldown": {"seconds": 3600, "gate": "activation"}
}

# ❌ Bad: New, untested EMU with auto mode
{
    "mode": "auto",           # Should be "require_human" initially!
    "priority": 10,           # Too high for untested EMU
    "cooldown": {"seconds": 0}  # No rate limiting!
}
```

### 4. Document Dependencies

```python
# ✅ Good: Document ATOM dependencies
"""
EMU: vip_escalation
Trigger: state.customer.tier == 'vip' AND state.ticket.priority == 'high' AND NOT event.agent.escalated.ticket IN 'PT2H'

ATOMs required:
- state.customer.tier - From CRM integration
- state.ticket.priority - From ticket system
- event.agent.escalated.ticket - Ingested on escalation

ML dependencies: None
"""

# ❌ Bad: No documentation
# (No one knows what ATOMs are needed!)
```

### 5. Test Thoroughly

```python
# Test with dry_run
response = await client.decide(
    context=[...],
    options=InvokeOptions(dry_run=True)  # No business execution or activation locks
)

# Verify trigger logic
assert len(response.selected) == 1
assert response.selected[0].emu_key == "expected_emu"
```

### 6. Monitor and Iterate

```
1. Deploy as SHADOW → Monitor trigger reach
2. Promote to CANARY → Test with an explicit application cohort
3. Promote to ACTIVE → Full rollout
4. Monitor metrics → Adjust policy/priority
5. Refine trigger → Create new version if needed
```

---
