# EMU Design Heuristics

**Practical Patterns for Production-Ready EMUs**

## Table of Contents

- [State-First vs Event-Based](#state-first-vs-event-based)
- [EMU Complexity Ladder](#emu-complexity-ladder)
- [Production-Ready Checklist](#production-ready-checklist)
- [Time Window Guidance](#time-window-guidance)
- [Policy Best Practices](#policy-best-practices)
- [Common Patterns](#common-patterns)
- [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## State-First vs Event-Based

**Start with state-based EMUs** - they're simpler to reason about and don't require event history.

### Complexity Comparison

| EMU Type | Trigger Pattern | Complexity | Use When |
|----------|-----------------|------------|----------|
| **State-only** | `state.x == 'y'` | Simplest | Current context is sufficient |
| **State + Tag** | `state.x == 'y' AND tag.z == 'w'` | Simple | Need ML/classification context |
| **State + Event** | `state.x == 'y' AND event.a.b.c IN 'PT1H'` | Moderate | Need temporal context |
| **Event-only** | `event.a.b.c IN 'PT1H'` | Complex | Pure event-driven automation |
| **Event + COUNT** | `COUNT event.a.b.c IN 'P7D' >= 5` | Most Complex | Pattern detection |

### Why State-First is Easier

```python
# STATE-ONLY: Fires immediately when context matches
# No event history required, no time windows to tune
trigger = 'state.customer.tier == "enterprise" AND state.ticket.priority == "high"'

# EVENT-BASED: Requires event ingestion pipeline working
# Time windows need tuning, event naming conventions matter
trigger = 'event.customer.created.ticket IN "PT15M" AND tag.priority == "high"'
```

### Decision Tree: Which Type to Use?

```
Is current state sufficient to make the decision?
├── YES → Use state-based EMU
│   └── Need ML classification? → Add tag atoms
└── NO → Need event context
    ├── "Did X happen recently?" → event.X IN 'duration'
    ├── "How many times did X happen?" → COUNT event.X IN 'duration'
    └── "Did X happen but not Y?" → event.X AND NOT event.Y
```

---

## EMU Complexity Ladder

Progress through these levels as you gain confidence:

### Level 1: State-only context_directive

**Complexity**: Lowest
**Risk**: Minimal
**Start here for**: First AMI integration

```python
{
    "emu_key": "support.vip_context",
    "trigger": "state.customer.tier == 'vip'",
    "action": {
        "type": "context_directive",
        "directive": "This is a VIP customer. Prioritize their request."
    },
    "policy": {"mode": "auto", "priority": 7}
}
```

### Level 2: State + tag context_directive

**Complexity**: Low
**Risk**: Low
**Use when**: Need ML classification in decision

```python
{
    "emu_key": "support.sentiment_guidance",
    "trigger": "state.conversation.active AND tag.sentiment == 'negative'",
    "action": {
        "type": "context_directive",
        "directive": "Customer is frustrated. Use empathetic language."
    },
    "policy": {"mode": "auto", "priority": 8}
}
```

### Level 3: State-only tool_call

**Complexity**: Medium
**Risk**: Medium (has side effects)
**Use when**: Ready for automation

```python
{
    "emu_key": "support.auto_escalate",
    "trigger": "state.customer.tier == 'enterprise' AND state.ticket.priority == 'critical'",
    "action": {
        "type": "tool_call",
        "intent": "ESCALATE_TICKET",
        "tool": {"tool_id": "escalator", "args": {"level": "tier2"}}
    },
    "policy": {
        "mode": "auto",
        "priority": 9,
        "cooldown": {"seconds": 3600, "gate": "ack"}
    }
}
```

### Level 4: State + event tool_call

**Complexity**: High
**Risk**: Medium
**Use when**: Need temporal context

```python
{
    "emu_key": "support.sla_escalation",
    "trigger": (
        "state.ticket.status == 'open' AND "
        "state.ticket.priority == 'high' AND "
        "NOT event.agent.responded.ticket IN 'PT2H'"
    ),
    "action": {
        "type": "tool_call",
        "intent": "ESCALATE_FOR_SLA",
        "tool": {"tool_id": "escalator", "args": {"reason": "sla_breach"}}
    },
    "policy": {"mode": "auto", "priority": 9}
}
```

### Level 5: Event-based with COUNT

**Complexity**: Highest
**Risk**: Higher (depends on event pipeline)
**Use when**: Pattern detection required

```python
{
    "emu_key": "security.account_lockout",
    "trigger": (
        "state.user.status == 'active' AND "
        "COUNT event.user.failed.login WHERE user_id == '{{user.id}}' IN 'PT15M' >= 5"
    ),
    "action": {
        "type": "tool_call",
        "intent": "LOCK_ACCOUNT",
        "tool": {"tool_id": "account_manager", "args": {"action": "lock"}}
    },
    "policy": {"mode": "auto", "priority": 10}
}
```

---

## Production-Ready Checklist

Every EMU should pass this checklist before going active:

### 1. Trigger Hygiene

```python
# GOOD: Specific, uses EXISTS for template vars
trigger = '''
    state.customer.tier == 'enterprise' AND
    state.ticket.id EXISTS AND
    NOT event.system.routed.ticket IN 'PT1H'
'''

# BAD: Missing guard, template var not guaranteed
trigger = 'state.customer.tier == "enterprise"'
# If action uses {{state.ticket.id}}, this will fail!
```

**Rules**:
- If action uses `{{state.X.Y}}`, trigger MUST include `state.X.Y EXISTS`
- Add duplicate guards: `NOT event.system.did.action IN 'PT1H'`
- Be specific: `state.customer.tier == 'enterprise'` not just `state.customer.tier EXISTS`

### 2. Action Configuration

For `tool_call` with side effects:

```python
{
    "action": {
        "type": "tool_call",
        "tool": {
            "tool_id": "mailer",
            "side_effect": True,  # Mark as having side effects
            "timeout_ms": 8000    # Set reasonable timeout
        }
    },
    "policy": {
        "cooldown": {"seconds": 3600, "gate": "ack"},     # REQUIRED
        "idempotency": {"enabled": True, "scope": [...]}, # REQUIRED
    }
}
```

### 3. Policy Requirements

| Field | When Required |
|-------|---------------|
| `mode` | Always |
| `priority` | Always |
| `cooldown` | For any action with side effects |
| `idempotency` | For tool_call with side_effect: true |
| `exclusion_groups` | When EMUs might conflict |

### 4. Scoring Sanity

| Scenario | expected_utility | confidence |
|----------|-----------------|------------|
| High-value automation | 0.85-0.95 | 0.85-0.95 |
| Standard automation | 0.70-0.85 | 0.70-0.85 |
| Advisory/guidance | 0.50-0.70 | 0.80-0.95 |
| Experimental | 0.40-0.60 | 0.50-0.70 |

---

## Time Window Guidance

| Scenario | Recommended Window | Example |
|----------|-------------------|---------|
| Immediate routing | `PT5M` - `PT15M` | Route ticket created in last 5 min |
| Response SLA | `PT1H` - `PT2H` | Escalate if no response in 2 hours |
| Daily patterns | `P1D` | User actions today |
| Survey follow-up | `P3D` - `P7D` | Send survey 3 days after resolution |
| Behavioral patterns | `P7D` - `P30D` | User engagement over past month |
| Churn prediction | `P30D` - `P90D` | Declining activity patterns |

### Window Selection Tips

1. **Start wide, narrow down**: Begin with `P7D`, tune based on data
2. **Consider event volume**: High-volume events need shorter windows
3. **Match business SLA**: Window should align with business expectations
4. **Account for retention**: Events stored 90 days by default

---

## Policy Best Practices

### Mode Selection

| Mode | Use When | Example |
|------|----------|---------|
| `auto` | High confidence, reversible, time-sensitive | Auto-escalation |
| `require_human` | Irreversible, high-risk, legal implications | Contract approval |
| `advisory` | Guidance only, no direct action | Context injection |

### Priority Guidelines

| Priority | Description | Examples |
|----------|-------------|----------|
| 9-10 | Critical, safety/security | Account lockout, fraud alert |
| 7-8 | High business impact | VIP escalation, SLA breach |
| 5-6 | Standard operations | Routing, notifications |
| 3-4 | Nice-to-have | Analytics, insights |
| 1-2 | Optional, low impact | A/B tests, experiments |

### Cooldown Configuration

```python
# Short cooldown: Frequent, low-risk actions
"cooldown": {"seconds": 300, "gate": "activation"}  # 5 minutes

# Medium cooldown: Standard operations
"cooldown": {"seconds": 3600, "gate": "ack"}  # 1 hour, wait for ack

# Long cooldown: Sensitive actions
"cooldown": {"seconds": 86400, "gate": "ack"}  # 24 hours
```

### Exclusion Groups

Prevent conflicting EMUs from firing together:

```python
# Only one escalation type should fire
{
    "emu_key": "support.tier2_escalation",
    "policy": {
        "exclusion_groups": ["escalation"]
    }
}

{
    "emu_key": "support.manager_escalation",
    "policy": {
        "exclusion_groups": ["escalation"]
    }
}

# Highest priority in group wins
```

---

## Common Patterns

### Pattern 1: Tier-Based Context (State-Only)

```python
{
    "emu_key": "support.enterprise_context",
    "trigger": "state.customer.tier == 'enterprise'",
    "action": {
        "type": "context_directive",
        "directive": "Enterprise customer with dedicated support. Check their CSM notes before responding."
    },
    "policy": {"mode": "auto", "priority": 8}
}
```

### Pattern 2: Sentiment-Based Guidance (State + Tag)

```python
{
    "emu_key": "agent.negative_sentiment",
    "trigger": "tag.sentiment == 'negative' AND state.conversation.turn_count >= 2",
    "action": {
        "type": "context_directive",
        "directive": "Customer frustration detected. Acknowledge their feelings, apologize for inconvenience, and focus on resolution."
    },
    "policy": {"mode": "auto", "priority": 8}
}
```

### Pattern 3: SLA Prevention (State + Event)

```python
{
    "emu_key": "support.sla_warning",
    "trigger": (
        "state.ticket.sla_remaining_hours <= 2 AND "
        "state.ticket.status IN ['open', 'pending'] AND "
        "NOT event.system.sent.sla_warning IN 'PT4H'"
    ),
    "action": {
        "type": "tool_call",
        "intent": "SEND_SLA_WARNING",
        "tool": {
            "tool_id": "slack",
            "args": {
                "channel": "#support-urgent",
                "message": "SLA warning: Ticket {{ticket.id}} has {{ticket.sla_remaining_hours}}h remaining"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 9,
        "cooldown": {"seconds": 14400, "gate": "activation"}  # 4 hours
    }
}
```

### Pattern 4: Rate Limiting (Event COUNT)

```python
{
    "emu_key": "api.rate_limit_warning",
    "trigger": (
        "state.user.id EXISTS AND "
        "COUNT event.user.called.api WHERE user_id == '{{user.id}}' IN 'PT1M' >= 80"
    ),
    "action": {
        "type": "context_directive",
        "directive": "User approaching rate limit (80/100 in last minute). Warn about throttling."
    },
    "policy": {"mode": "auto", "priority": 7}
}
```

### Pattern 5: Follow-up Automation (Event + NOT Event)

```python
{
    "emu_key": "sales.followup_reminder",
    "trigger": (
        "event.sales.sent.proposal IN 'P3D' AND "
        "NOT event.customer.responded.proposal IN 'P3D' AND "
        "NOT event.sales.sent.followup IN 'P2D'"
    ),
    "action": {
        "type": "tool_call",
        "intent": "SEND_FOLLOWUP",
        "tool": {
            "tool_id": "mailer",
            "args": {
                "template": "proposal_followup",
                "to": "{{customer.email}}"
            }
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 5,
        "cooldown": {"seconds": 172800, "gate": "ack"}  # 48 hours
    }
}
```

---

## Anti-Patterns to Avoid

### 1. Overly Broad Triggers

```python
# BAD: Fires for every premium user
trigger = 'state.user.tier == "premium"'
action = {"type": "tool_call", ...}  # Sends email to ALL premium users!

# GOOD: Specific conditions
trigger = (
    'state.user.tier == "premium" AND '
    'state.user.signup_days <= 7 AND '
    'NOT event.system.sent.welcome_email IN "P7D"'
)
```

### 2. Missing Duplicate Guards

```python
# BAD: Will fire repeatedly
trigger = 'state.ticket.priority == "high"'
action = {"type": "tool_call", "tool": {"tool_id": "escalator"}}

# GOOD: Prevent duplicates
trigger = (
    'state.ticket.priority == "high" AND '
    'NOT event.system.escalated.ticket IN "PT4H"'
)
```

### 3. No Cooldown on Side Effects

```python
# BAD: Can spam users
{
    "action": {"type": "tool_call", "tool": {"tool_id": "mailer"}},
    "policy": {"mode": "auto"}  # Missing cooldown!
}

# GOOD: Has cooldown
{
    "action": {"type": "tool_call", "tool": {"tool_id": "mailer"}},
    "policy": {
        "mode": "auto",
        "cooldown": {"seconds": 86400, "gate": "ack"}
    }
}
```

### 4. Missing EXISTS Guard for Interpolation

```python
# BAD: {{user.email}} might not exist
trigger = 'state.user.tier == "premium"'
action = {"tool": {"args": {"to": "{{user.email}}"}}}

# GOOD: Guard with EXISTS
trigger = 'state.user.tier == "premium" AND state.user.email EXISTS'
action = {"tool": {"args": {"to": "{{user.email}}"}}}
```

### 5. Unrealistic Time Windows

```python
# BAD: 180 days exceeds 90-day retention
trigger = 'event.user.purchased.item IN "P180D"'

# GOOD: Within retention
trigger = 'event.user.purchased.item IN "P90D"'
```

### 6. Conflicting EMUs Without Exclusion Groups

```python
# BAD: Both might fire
{"emu_key": "route.spanish", "trigger": "tag.language == 'spanish'", ...}
{"emu_key": "route.vip", "trigger": "state.customer.tier == 'vip'", ...}

# GOOD: Mutual exclusion
{"emu_key": "route.spanish", "policy": {"exclusion_groups": ["routing"]}}
{"emu_key": "route.vip", "policy": {"exclusion_groups": ["routing"]}}
```

### 7. Globally Scoped Event Matching (Unscoped WHERE Clauses)

When an EMU trigger references events without a WHERE clause scoping them to the
current entity/object, the event matches **globally** — ANY matching event from
ANY entity satisfies the condition. This causes false triggers when multiple
entities exist in the same workspace.

```python
# BAD: Matches if ANY entity was invited in the last 3 days
trigger = 'event.staff.sent.invite IN "P3D" AND state.engagement.status == "pending"'
# Entity A gets invited → Entity B's EMU fires because the event is global!

# GOOD: Scoped to the current entity via WHERE clause with template literal
trigger = (
    'event.staff.sent.invite WHERE entity_id == \'{{entity.id}}\' IN "P3D" AND '
    'state.engagement.status == "pending"'
)
# Only fires if THIS entity was invited
```

**CRITICAL: WHERE clause values must be literals or template literals.**
The API does NOT support state references (`state.entity.id`) in WHERE values.
Use template literals (`'{{entity.id}}'`) which are resolved at evaluation time.

```python
# BAD: State reference in WHERE value — API rejects with "Invalid trigger DSL syntax"
'event.staff.sent.invite WHERE entity_id == state.entity.id IN "P3D"'

# GOOD: Template literal in WHERE value — resolves at evaluation time
'event.staff.sent.invite WHERE entity_id == \'{{entity.id}}\' IN "P3D"'
```

**When to scope events:**
- Always scope `event.*` clauses when the EMU runs in a **multi-entity context**
  (e.g., per-entity or per-engagement decision points)
- The scoping attribute (e.g., `entity_id`) must be present in the event's
  details/attributes — ensure `log_action` and `emit_event` calls include it
- Common scoping patterns:
  - `WHERE entity_id == '{{entity.id}}'` — scope to current entity
  - `WHERE engagement_id == '{{engagement.id}}'` — scope to current engagement
  - `WHERE user_id == '{{user.id}}'` — scope to current user

**Event emission prerequisite:**
For WHERE clauses to work, the scoping field must exist in event details.
Audit all `log_action()` and `emit_event()` calls to ensure they include
the scoping attribute (e.g., `entity_id`) in their details dict.

```python
# BAD: Event emitted without entity_id — WHERE clause can't match
await log_action(db, "invite_client", "invitation", inv.id, user.id, firm_id,
                 {"email": body.email})

# GOOD: entity_id included — WHERE clause works
await log_action(db, "invite_client", "invitation", inv.id, user.id, firm_id,
                 {"email": body.email, "entity_id": str(entity.id)})
```

---

## Testing Strategy

### 1. Start in Draft

```python
await client.register_emu(
    emu_key="new-automation",
    state="draft",  # Not evaluated yet
    ...
)
```

### 2. Promote to Shadow

```python
await client.update_emu_lifecycle("new-automation", "shadow")
# EMU is evaluated, results returned, but no execution
```

### 3. Monitor Shadow Results

```python
response = await client.decide(context=[...], trace=True)

for item in response.trace.evaluated_emus:
    if item.emu_key == "new-automation":
        print(f"Would fire: {item.trigger_result}")
```

### 4. Promote to Canary (10% traffic)

```python
await client.register_emu(
    emu_key="new-automation",
    state="canary",
    policy={
        "canary": {
            "percentage": 10,
            "sticky_field": "user.id",
            "salt": "v1-rollout"
        }
    }
)
```

### 5. Promote to Active

```python
await client.update_emu_lifecycle("new-automation", "active")
```

---

**See Also**:
- [04-emu-cookbook.md](04-emu-cookbook.md) - Real-world examples
- [10-llm-integration-guide.md](10-llm-integration-guide.md) - EMU generation
- [03-trigger-reachability.md](03-trigger-reachability.md) - Debugging triggers
