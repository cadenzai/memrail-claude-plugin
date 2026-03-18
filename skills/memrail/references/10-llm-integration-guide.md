# LLM Integration Guide

**Helping LLMs Generate Valid EMUs**

## Table of Contents

- [Overview](#overview)
- [Concept Relationships](#concept-relationships)
- [EMU Generation Template](#emu-generation-template)
- [Validation Checklist](#validation-checklist)
- [Common Mistakes](#common-mistakes)
- [Examples](#examples)
- [TypeScript SDK](#typescript-sdk)
- [HTTP API Direct](#http-api-direct)

---

## Overview

This guide helps LLMs (like Claude) understand AMI concepts for generating valid EMUs. When building agentic applications that create or modify EMUs, use this reference to ensure correctness.

---

## Concept Relationships

```
ATOMS (data) ──────────────────────┐
   ├─ State Atoms (key=value)      │
   ├─ Tag Atoms (kind=value)       ├──▶ INVOKE ──▶ EMU Evaluation ──▶ ACTIONS
   └─ Event Atoms (S.V.O @ time)   │
                                   │
EMUs (rules) ──────────────────────┘
   ├─ Trigger (DSL expression)
   ├─ Action (what to do)
   └─ Policy (how to execute)
```

### Key Concepts

| Concept | Purpose | Example |
|---------|---------|---------|
| **State Atom** | Current system facts | `state("user.tier", "premium")` |
| **Tag Atom** | Classifications/metadata | `tag("sentiment", "negative")` |
| **Event Atom** | Timestamped occurrences | `event("user.logged.in", ts=now)` |
| **Trigger** | When to fire | `state.user.tier == 'premium'` |
| **Action** | What to do | `{"type": "tool_call", ...}` |
| **Policy** | How to execute | `{"mode": "auto", "priority": 5}` |

---

## EMU Generation Template

When generating an EMU, use this structure:

```python
emu = {
    # REQUIRED
    "emu_key": "<lowercase-slug-with-dots-or-underscores>",
    "trigger": "<valid-dsl-expression>",
    "policy": {
        "mode": "<auto|require_human|advisory>",
        "priority": <0-9>,  # Higher = more important
    },
    "expected_utility": <0.0-1.0>,  # Expected value
    "confidence": <0.0-1.0>,        # Confidence level

    # OPTIONAL but recommended
    "intent": "<human-readable description of what this EMU does>",
    "action": {
        "type": "<context_directive|tool_call|decision_prompt|route>",
        # type-specific fields...
    },

    # OPTIONAL
    "state": "draft",  # Start in draft, promote later
    "metadata": {}     # Custom metadata
}
```

### Action Type Templates

#### context_directive

```python
"action": {
    "type": "context_directive",
    "directive": "Customer is a VIP. Prioritize their request and offer premium support."
}
```

#### tool_call

```python
"action": {
    "type": "tool_call",
    "intent": "SEND_WELCOME_EMAIL",
    "tool": {
        "tool_id": "mailer",
        "version": "1.0.0",
        "args": {
            "to": "{{user.email}}",      # Payload interpolation
            "template": "welcome_premium"
        },
        "timeout_ms": 8000,
        "side_effect": True
    }
}
```

#### decision_prompt

```python
"action": {
    "type": "decision_prompt",
    "message": "High-risk transaction from {{user.id}}. Approve?",
    "options": [
        {"id": "approve", "label": "Approve Transaction"},
        {"id": "decline", "label": "Decline Transaction"},
        {"id": "review", "label": "Request Manual Review"}
    ]
}
```

#### route

```python
"action": {
    "type": "route",
    "destination": "queue.spanish-support",
    "metadata": {
        "reason": "language_detected",
        "language": "spanish"
    }
}
```

---

## Validation Checklist

When generating or reviewing an EMU, verify:

### 1. Trigger Syntax

- [ ] Operators are UPPERCASE (`AND`, `OR`, `NOT`)
- [ ] State keys have 2-7 dot-separated parts
- [ ] State keys are lowercase with underscores
- [ ] Durations are ISO 8601 format in single quotes (`'PT1H'`, `'P7D'`)
- [ ] String literals use single quotes
- [ ] Event topics follow subject.verb.object pattern

### 2. Trigger Reachability

- [ ] All `state.*` keys are provided in invoke calls
- [ ] All `tag.*` kinds are provided (often from ML classifiers)
- [ ] All `event.*` topics are being emitted
- [ ] WHERE clause attributes exist in event attributes
- [ ] Time windows are within event retention (90 days default)

### 3. Action Connectivity

- [ ] `context_directive`: Application uses LLM
- [ ] `tool_call`: Executor exists for `tool_id`
- [ ] `decision_prompt`: UI/Slack handler exists
- [ ] `route`: Routing handler for destination exists

### 4. Policy Configuration

- [ ] `mode`: One of "auto", "require_human", "advisory"
- [ ] `priority`: Integer 0-9 (9 = critical, 5 = standard, 1 = optional)
- [ ] `cooldown.gate`: Either "ack" or "activation"
- [ ] `cooldown.seconds`: Reasonable value for use case

### 5. Payload Interpolation

If using `{{state.X.Y}}` in action args:
- [ ] Trigger MUST include `state.X.Y EXISTS` guard

---

## Common Mistakes

| Mistake | Example | Fix |
|---------|---------|-----|
| Lowercase operators | `state.x == 'y' and ...` | `state.x == 'y' AND ...` |
| Wrong quotes | `state.x == "y"` | `state.x == 'y'` |
| Double quotes for duration | `IN "PT1H"` | `IN 'PT1H'` |
| Single-part key | `state.tier == 'x'` | `state.user.tier == 'x'` |
| Missing duration quotes | `IN PT1H` | `IN 'PT1H'` |
| Uppercase keys | `state.User.Tier` | `state.user.tier` |
| Hyphens in keys | `state.user-tier` | `state.user_tier` |
| Missing S.V.O in event | `event.login IN 'PT1H'` | `event.user.logged.in IN 'PT1H'` |
| Unreachable trigger | Referencing non-existent atoms | Verify atoms are provided |
| Missing EXISTS guard | Using `{{user.email}}` without check | Add `state.user.email EXISTS` |

### Valid vs Invalid Examples

```javascript
// ❌ INVALID: lowercase AND
state.user.tier == 'premium' and state.account.active

// ✅ VALID: uppercase AND
state.user.tier == 'premium' AND state.account.active

// ❌ INVALID: double quotes
state.user.tier == "premium"

// ✅ VALID: single quotes
state.user.tier == 'premium'

// ❌ INVALID: single-part state key
state.tier == 'premium'

// ✅ VALID: multi-part state key
state.user.tier == 'premium'

// ❌ INVALID: missing quotes on duration
event.user.logged.in IN PT1H

// ✅ VALID: quoted duration
event.user.logged.in IN 'PT1H'

// ❌ INVALID: event without S.V.O pattern
event.login IN 'PT1H'

// ✅ VALID: event with subject.verb.object
event.user.logged.in IN 'PT1H'
```

---

## Examples

### Example 1: Premium Customer Context

**User Request**: "Create an EMU that tells the agent when they're talking to a premium customer"

```python
{
    "emu_key": "support.premium_context",
    "intent": "Inform agent about premium customer status",
    "trigger": "state.customer.tier == 'premium'",
    "action": {
        "type": "context_directive",
        "directive": "This is a premium customer. Provide priority support and be prepared to offer exclusive benefits."
    },
    "policy": {
        "mode": "auto",
        "priority": 7
    },
    "expected_utility": 0.8,
    "confidence": 0.95,
    "state": "active"
}
```

**Verification**:
- [x] Trigger syntax valid (uppercase not needed for single condition)
- [x] `state.customer.tier` must be provided in invoke
- [x] `context_directive` is always reachable with LLM

### Example 2: Cart Abandonment Discount

**User Request**: "Create an EMU that sends a discount code when a premium customer has items in their cart for over an hour without checking out"

```python
{
    "emu_key": "ecommerce.cart_abandonment_discount",
    "intent": "Send discount code to premium customers with abandoned carts",
    "trigger": (
        "state.user.tier == 'premium' AND "
        "state.cart.item_count > 0 AND "
        "state.user.email EXISTS AND "  # Guard for template
        "event.user.added.cart_item IN 'PT1H' AND "
        "NOT event.user.started.checkout IN 'PT1H'"
    ),
    "action": {
        "type": "tool_call",
        "intent": "SEND_DISCOUNT_EMAIL",
        "tool": {
            "tool_id": "mailer",
            "version": "1.0.0",
            "args": {
                "to": "{{user.email}}",
                "template": "cart_abandonment_discount",
                "discount_code": "COMEBACK10"
            },
            "side_effect": True
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 6,
        "cooldown": {
            "seconds": 86400,  # 24 hours - don't spam
            "gate": "ack"
        },
        "idempotency": {
            "enabled": True,
            "scope": ["user.id"]
        }
    },
    "expected_utility": 0.75,
    "confidence": 0.85,
    "state": "draft"  # Start in draft for review
}
```

**Verification**:
- [x] Trigger syntax valid
- [ ] Verify: Is `state.cart.item_count` provided in invoke?
- [ ] Verify: Is `event.user.added.cart_item` being emitted?
- [ ] Verify: Is `event.user.started.checkout` being emitted?
- [ ] Verify: Does executor exist for `mailer` tool?
- [x] `state.user.email EXISTS` guard for `{{user.email}}`

### Example 3: SLA Breach Prevention

**User Request**: "Create an EMU that escalates tickets when they're about to breach SLA"

```python
{
    "emu_key": "support.sla_breach_prevention",
    "intent": "Escalate tickets approaching SLA breach",
    "trigger": (
        "state.ticket.sla_remaining_hours <= 2 AND "
        "state.ticket.status != 'resolved' AND "
        "state.ticket.id EXISTS AND "
        "NOT event.system.escalated.ticket IN 'PT2H'"  # Prevent duplicate escalations
    ),
    "action": {
        "type": "tool_call",
        "intent": "ESCALATE_FOR_SLA",
        "tool": {
            "tool_id": "ticket_escalator",
            "version": "1.4.0",
            "args": {
                "ticket_id": "{{ticket.id}}",
                "escalation_level": "supervisor",
                "reason": "sla_breach_imminent",
                "notify_channels": ["#support-escalations"]
            },
            "side_effect": True
        }
    },
    "policy": {
        "mode": "auto",
        "priority": 9,  # High priority - SLA is critical
        "cooldown": {
            "seconds": 7200,  # 2 hours
            "gate": "activation"
        }
    },
    "expected_utility": 0.95,
    "confidence": 0.88,
    "state": "active"
}
```

---

## TypeScript SDK

For TypeScript/JavaScript applications:

### Installation

```bash
npm install @memrail/sdk
# or
yarn add @memrail/sdk
```

### Basic Usage

```typescript
import { AMIClient, state, tag, event, StateObject } from '@memrail/sdk';

const client = new AMIClient({
  apiKey: 'ami_...',
  org: 'your-org',
  workspace: 'production',
  project: 'your-app'
});

// Invoke
const response = await client.invoke({
  atoms: [
    state('user.id', 'U-123'),
    state('user.tier', 'premium'),
    tag('intent', 'checkout'),
  ],
  trace: true
});

// Process response
for (const item of response.selected) {
  console.log(`EMU: ${item.emu_key}`);
  console.log(`Lifecycle: ${item.lifecycle_state}`);
  console.log(`Action: ${JSON.stringify(item.action)}`);
}

// Emit events
await client.emitEvent(
  event('user.logged.in', {
    ts: new Date(),
    subjectAnchor: { type: 'user', id: 'U-123' }
  })
);
```

### StateObject Builder

```typescript
import { StateObject } from '@memrail/sdk';

// Convert object to state atoms
const userAtoms = new StateObject('user', {
  id: 'U-123',
  tier: 'premium',
  account: {
    balance: 150.00,
    currency: 'USD'
  }
}).toAtoms();

// Use in invoke
const response = await client.invoke({
  atoms: [...userAtoms, tag('intent', 'checkout')]
});
```

---

## HTTP API Direct

For direct HTTP integration without SDK:

### Headers

```
Authorization: AMI-Key ami_...
X-AMI-Org: your-org
X-AMI-Team: default
Content-Type: application/json
```

### Invoke

```bash
POST /v1/workspaces/{workspace}/projects/{project}/ami/invoke

{
    "context_atoms": [
        {"type": "state", "key": "user.id", "value": "U-123"},
        {"type": "state", "key": "user.tier", "value": "premium"},
        {"type": "tag", "kind": "intent", "value": "checkout"}
    ],
    "options": {"top_k": 5},
    "trace": {"enable": true}
}
```

### Ingest Events

```bash
POST /v1/workspaces/{workspace}/projects/{project}/events

{
    "events": [
        {
            "subject": "user",
            "verb": "logged",
            "object": "in",
            "ts": "2026-01-25T10:00:00Z",
            "anchor": {
                "subject": {"type": "user", "id": "U-123"}
            },
            "attributes": {"method": "oauth"}
        }
    ]
}
```

### Register EMU

```bash
POST /v1/workspaces/{workspace}/projects/{project}/emus

{
    "emu_key": "my-emu",
    "trigger": "state.user.tier == 'premium'",
    "action": {
        "type": "context_directive",
        "directive": "Premium customer - prioritize quality"
    },
    "policy": {
        "mode": "auto",
        "priority": 5,
        "cooldown": {"seconds": 3600, "gate": "ack"}
    },
    "expected_utility": 0.8,
    "confidence": 0.9,
    "state": "active"
}
```

### Acknowledge Activation

```bash
POST /v1/workspaces/{workspace}/projects/{project}/activations/{activation_id}/ack

{
    "status": "acknowledged",
    "message": "Action completed successfully"
}
```

---

**See Also**:
- [02-dsl-reference.md](02-dsl-reference.md) - Complete DSL syntax
- [05-sdk-integration-python.md](05-sdk-integration-python.md) - Python SDK
- [05b-sdk-integration-typescript.md](05b-sdk-integration-typescript.md) - TypeScript SDK
- [11-emu-design-heuristics.md](11-emu-design-heuristics.md) - Design patterns
