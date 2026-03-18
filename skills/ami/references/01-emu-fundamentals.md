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

1. **Deterministic**: Same inputs → Same outputs (no randomness)
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

An EMU consists of 8 core components:

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

**Format**: Lowercase, alphanumeric, underscores, dots
**Pattern**: `^[a-z0-9_][a-z0-9_.-]*$`

```python
# Valid
"welcome_premium_users"
"emu:support.vip_escalation"
"sales.lead_qualification_v2"

# Invalid
"WelcomeUsers"           # Uppercase
"welcome-users"          # Hyphens not allowed
"_private_emu"           # Cannot start with underscore
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
    "priority": 8,                     # 1-10 (higher = more important)
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

Used to determine when to require human review (low confidence = REQUIRE_HUMAN mode).

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
| `canary` | Testing with subset of traffic | Fires based on canary config |
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

```
┌─────────────────────────────────────────────────────────────┐
│                     EMU Lifecycle                           │
└─────────────────────────────────────────────────────────────┘

    register_emu()
         ↓
    ┌─────────┐
    │ ACTIVE  │ ← Default state, fully operational
    └────┬────┘
         │
         ├→ update_state("canary")  → Test with subset
         ├→ update_state("shadow")  → Evaluate without executing
         ├→ update_state("archived") → Deprecate
         └→ register_emu()          → Create new version
                   ↓
            ┌──────────────┐
            │ New Version  │
            │ (v2, v3...)  │
            └──────────────┘
```

### Version Progression

```python
# v1: Initial EMU
await client.register_emu(
    emu_key="welcome_users",
    trigger="state.user.tier == 'premium'",
    ...
)  # Creates version 1

# v2: Refined trigger
await client.register_emu(
    emu_key="welcome_users",  # Same key
    trigger="state.user.tier == 'premium' AND NOT event.agent.sent.welcome IN 'P7D'",
    ...
)  # Creates version 2, v1 still exists but superseded
```

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

| action.type | mode = auto | mode = require_human | mode = advisory |
|---|---|---|---|
| `tool_call` | Execute immediately | Create approval item | Log suggestion only |
| `decision_prompt` | Emit prompt | *(mode ignored)* | *(mode ignored)* |
| `route` | Apply route | *(normalizes to auto)* | *(normalizes to auto)* |
| `context_directive` | Apply directive | *(normalizes to auto)* | *(normalizes to auto)* |

> `require_human` and `advisory` only affect `tool_call` actions. All other action types execute normally regardless of mode.

### Priority

**Range**: 1-10 (higher = more important)
**Purpose**: Rank EMUs when multiple fire simultaneously

```python
priority=9  # Critical: system alerts, VIP escalations
priority=7  # Important: SLA breaches, high-value customers
priority=5  # Standard: routine workflows, notifications
priority=3  # Optional: suggestions, enhancements
priority=1  # Low: satisfaction surveys, analytics
```

### Cooldown

Rate-limit EMU execution to prevent spam. Cooldowns are deterministic and respect historical timestamps for backfill scenarios.

```python
{
    "cooldown": {
        "seconds": 3600,           # 1 hour (0 = no cooldown)
        "gate": "ack"              # When to start cooldown (default: "ack")
    }
}

# Gates (AMI v2):
# - "ack": Cooldown starts when acknowledgment received (default, recommended)
# - "activation": Cooldown starts immediately when EMU fires (legacy mode)
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

**How cooldowns work with historical data**:

When processing historical invocations (e.g., backfilling data with `context_ts` in the past), cooldowns are calculated relative to the `context_ts`, not the current time. This ensures deterministic behavior:

```python
# Invocation 1: context_ts = 2025-01-01T10:00:00Z → Creates cooldown until 10:01:00Z
# Invocation 2: context_ts = 2025-01-01T10:00:30Z → Suppressed (within cooldown window)
# Invocation 3: context_ts = 2025-01-01T10:01:15Z → Allowed (cooldown expired)
```

This allows you to replay historical data and get the same EMU activation patterns as if they had been processed in real-time.

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

Prevent duplicate executions for same logical operation.

```python
{
    "idempotency": {
        "enabled": true,
        "scope": ["user.id", "order.id"]  # Keys that define uniqueness
    }
}
```

**Example**:

```python
# Two invocations with same user.id and order.id → Only first executes
decide(context=[state("user.id", "U123"), state("order.id", "ORD-456")])
decide(context=[state("user.id", "U123"), state("order.id", "ORD-456")])  # Skipped!
```

### Exclusion Groups

Prevent multiple EMUs in same group from firing simultaneously.

```python
{
    "exclusion_groups": ["escalation_actions"]
}
```

If multiple EMUs in `"escalation_actions"` match, only the highest-priority one fires.

## Versioning

EMUs support semantic versioning at the key level.

### Creating Versions

```python
# Register v1
await client.register_emu(
    emu_key="lead_scorer",
    trigger="state.lead.source == 'website'",
    ...
)
# Response: {"emu_id": "emu_abc123", "version": 1}

# Register v2 (same key, new trigger)
await client.register_emu(
    emu_key="lead_scorer",  # Same key!
    trigger="state.lead.source == 'website' AND state.lead.company_size >= 100",
    ...
)
# Response: {"emu_id": "emu_xyz789", "version": 2}
```

### Version Behavior

- **Latest version is active**: By default, newest version is used
- **Old versions preserved**: All versions remain in database for audit trail
- **Version-specific retrieval**: Can fetch specific versions via API
- **Supersession tracking**: Old versions marked as "superseded_by" new version

### Version Migration Strategy

```
┌────────────────────────────────────────────────────────────┐
│                  Safe Version Migration                    │
└────────────────────────────────────────────────────────────┘

1. v1 ACTIVE        → Production traffic
2. Register v2      → Creates new version
3. v2 CANARY        → Test with 10% traffic
4. Monitor v2       → Check metrics, error rates
5. v2 ACTIVE        → Full rollout
6. v1 ARCHIVED      → Deprecate old version
```

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
Trigger: state.customer.tier == 'vip' AND state.ticket.priority >= 'high' AND NOT event.agent.escalated.ticket IN 'PT2H'

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
    options=InvokeOptions(dry_run=True)  # No side effects
)

# Verify trigger logic
assert len(response.selected) == 1
assert response.selected[0].emu_key == "expected_emu"
```

### 6. Monitor and Iterate

```
1. Deploy as SHADOW → Monitor trigger reach
2. Promote to CANARY → Test with 10% traffic
3. Promote to ACTIVE → Full rollout
4. Monitor metrics → Adjust policy/priority
5. Refine trigger → Create new version if needed
```

---
