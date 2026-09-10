# Trigger Reachability

**Understanding ATOM Dependencies and When Triggers Can Fire**

## Table of Contents

- [What is Trigger Reachability?](#what-is-trigger-reachability)
- [ATOM Dependencies](#atom-dependencies)
- [Event Ingestion](#event-ingestion)
- [ML Inference Dependencies](#ml-inference-dependencies)
- [Reachability Analysis](#reachability-analysis)
- [Common Unreachability Patterns](#common-unreachability-patterns)
- [Debugging Unreachable Triggers](#debugging-unreachable-triggers)

## What is Trigger Reachability?

**Trigger reachability** asks whether the facts available at an invocation site can satisfy an expression. Analyze each Boolean branch: missing positive comparisons may fail while NOT, OR, or zero-event counts still allow a match.

### The Core Problem

```javascript
// EMU trigger
trigger = "state.user.tier == 'premium' AND tag.intent == 'upgrade'"

// Invoke with partial atoms
decide(context=[
    state("user.id", "U123"),
    state("user.name", "Alice")
    // ⚠️ Missing: user.tier and intent tag!
])

// Result: Trigger evaluates to FALSE (unreachable)
```

### Why This Matters

1. **Missing inputs**: Positive predicates may evaluate to `FALSE`; malformed DSL is a separate validation error
2. **False negatives**: EMU should fire but doesn't due to missing data
3. **Debugging complexity**: Hard to distinguish "trigger didn't match" from "atoms missing"
4. **Design implications**: Must consider data pipeline when writing triggers

## ATOM Dependencies

Every DSL function has ATOM dependencies:

### State Atom Dependencies

Requires state ATOM with exact key match:

```javascript
// Trigger
state.user.tier == 'premium'

// Required ATOM
state("user.tier", "premium")  // ✅ Matches

// Missing/wrong atoms
state("user.tier_id", 1)       // ❌ Different key
state("user", {"tier": "premium"})  // ❌ Not dot-notation
```

**Dependency**: Must have ATOM builder that provides `user.tier`

### Tag Atom Dependencies

Requires tag ATOM with matching kind:

```javascript
// Trigger
tag.priority == 'high'

// Required ATOM
tag("priority", "high")        // ✅ Matches

// Missing/wrong atoms
tag("priority_level", "high")  // ❌ Different kind
state("priority", "high")      // ❌ Wrong ATOM type (state, not tag)
```

**Dependency**: Must have ATOM builder or ML classifier that provides `priority` tag

### Event Dependencies

Requires event ingestion:

```javascript
// Trigger
event.agent.sent.email IN 'PT24H'

// Required: Event must be ingested
event("agent.sent.email", ts=datetime.now(timezone.utc))

// With anchors (AMI v2)
event("agent.sent.email", ts=..., anchor={
    "subject": {"type": "agent", "id": "AGT-123"},
    "object": {"type": "email", "id": "EMAIL-456"}
})
```

**Dependencies**:
1. Event ingestion pipeline must capture `agent.sent.email` events
2. Events must be ingested with timestamps
3. (Optional) Anchor data for role binding

## Event Ingestion

Persist events after the application completes the corresponding action. An ATOM builder alone does not store an event.

```python
from datetime import datetime, timezone
from memrail.atoms import event

async def record_email_sent(client, email_id, user_id):
    return await client.emit_event(event(
        "agent.sent.email",
        ts=datetime.now(timezone.utc),
        subject_anchor=("agent", "A-123"),
        object_anchor=("email", email_id),
        attributes={"user_id": user_id},
    ))
```

Call `emit_events` with a list of EventAtom instances for batches. For an event-bus integration, map topic, timestamp, attributes, and anchors consistently in the consumer. Avoid blind retries that double-count events.

Events are retained for 90 days by default, subject to effective organization/workspace configuration. A longer query can still match recent retained events; it cannot recover expired history. Scope event queries to the intended entity with WHERE attributes or supported role binding.


## ML Inference Dependencies

Some triggers require ML model inference.

### Common ML Dependencies

#### 1. Intent Classification

```javascript
// Trigger
tag.intent == 'upgrade_request'

// Dependency: ML classifier
user_message = "I want to upgrade my plan"
intent = intent_classifier.predict(user_message)  // → "upgrade_request"

// Provide as tag
tag("intent", intent)
```

**Models needed**:
- Intent classifier (NLP model)
- Training data for intents

#### 2. Sentiment Analysis

```javascript
// Trigger
tag.sentiment == 'negative'

// Dependency: Sentiment classifier
review_text = "This product is terrible"
sentiment = sentiment_classifier.predict(review_text)  // → "negative"

// Provide as tag
tag("sentiment", sentiment)
```

**Models needed**:
- Sentiment classifier
- Training data (positive/negative/neutral)

#### 3. Topic Classification

```javascript
// Trigger
tag.category == 'billing_issue'

// Dependency: Topic classifier
ticket_text = "I was charged twice for my subscription"
category = topic_classifier.predict(ticket_text)  // → "billing_issue"

// Provide as tag
tag("category", category)
```

**Models needed**:
- Multi-class topic classifier
- Training data for categories

#### 4. Tool Usage Detection

```javascript
// Trigger
tag.tool_used == 'knowledge_base_search'

// Dependency: Tool usage tracker
agent_actions = get_agent_actions(session)
if "search_kb" in agent_actions:
    tag("tool_used", "knowledge_base_search")
```

**Infrastructure needed**:
- Tool usage tracking
- Action logging

### ML Pipeline Integration

```
┌──────────────────────────────────────────────────────────────┐
│                    ML-Augmented Pipeline                     │
└──────────────────────────────────────────────────────────────┘

1. User Input
      ↓
2. ML Inference (Intent, Sentiment, etc.)
      ↓
3. ATOM Builder
      ├→ State ATOMs (structured data)
      ├→ Tag ATOMs (ML classifications)
      └→ Event ATOMs (user actions)
      ↓
4. AMI Invoke
      ↓
5. Trigger Evaluation (now has all required atoms!)
      ↓
6. Action Selection
```

### When ML is NOT Required

Some tags don't need ML:

```javascript
// Simple metadata tags (no ML needed)
tag.channel == 'email'         // From request context
tag.language == 'spanish'      // From user profile
tag.region == 'us-east'        // From IP geolocation
tag.device_type == 'mobile'    // From user agent
```

## Reachability Analysis

### Static Analysis

Compare each trigger dependency with the builders actually called at that decision point. Distinguish state keys, tag kinds, event topics, entity filters, and temporal windows. Check local DSL syntax with `memrail emu-plan ./emus/ --validate-only`; use `--strict` candidate validation for server registry checks before writes. Do not assume a `memrail.analysis.extract_dependencies` public helper exists.

### Runtime Monitoring

```python
from memrail.models import InvokeOptions, TraceOptions

async def inspect_reachability(client, atoms):
    response = await client.decide(
        context=atoms,
        options=InvokeOptions(dry_run=True),
        trace=TraceOptions(enable=True),
    )
    for item in (response.trace or {}).get("candidates", []):
        print(item["emu_key"], item["passed"], item["reasons"], item["suppressed_by"])
    return response
```

A passed trigger may still lose arbitration or be suppressed by execution controls. Check selection separately. Missing positive predicates generally fail, but NOT, OR, and zero COUNT conditions can be true with absent data.


### Reachability Checklist

Before deploying an EMU, verify:

- [ ] All `state.X` references have ATOM builders providing those keys
- [ ] All `tag.X` references have ATOM builders or ML classifiers
- [ ] All `event.X` references have event ingestion configured
- [ ] Event ingestion includes required anchors (if using binding)
- [ ] ML models are trained and deployed (if using ML tags)
- [ ] Time windows are within event storage duration (90 days default)

## Common Unreachability Patterns

### Pattern 1: Typo in Key Name

```javascript
// EMU trigger
trigger = "state.user.teir == 'premium'"  // ❌ Typo: "teir"

// ATOM builder
state("user.tier", "premium")  // Provides "tier", not "teir"

// Result: Trigger unreachable (key mismatch)
```

**Fix**: Use consistent naming, validate keys at registration time.

### Pattern 2: Missing ATOM Builder

```javascript
// EMU trigger
trigger = "state.customer.lifetime_value > 10000"

// ATOM builders
state("customer.id", "CUST-123")
state("customer.tier", "premium")
// ❌ Missing: customer.lifetime_value

// Result: Trigger unreachable (atom never provided)
```

**Fix**: Add ATOM builder for `customer.lifetime_value`.

### Pattern 3: Event Never Ingested

```javascript
// EMU trigger
trigger = "event.agent.escalated.ticket IN 'PT24H'"

// Event ingestion
event("ticket.created.zendesk")
event("agent.assigned.ticket")
// ❌ Missing: agent.escalated.ticket

// Result: Trigger unreachable (event never ingested)
```

**Fix**: Add event ingestion when escalation occurs.

### Pattern 4: Wrong ATOM Type

```javascript
// EMU trigger
trigger = "tag.priority == 'high'"

// ATOM provided
state("priority", "high")  // ❌ Wrong type (state, not tag)

// Result: Trigger unreachable (type mismatch)
```

**Fix**: Use `tag("priority", "high")` instead.

### Pattern 5: ML Model Not Deployed

```javascript
// EMU trigger
trigger = "tag.sentiment == 'negative'"

// No ML model deployed for sentiment analysis!
// Tag never provided

// Result: Trigger unreachable (ML dependency missing)
```

**Fix**: Deploy sentiment classifier, integrate with ATOM builder.

### Pattern 6: Binding Context Missing

Entity-scoped event filters need both an attribute on the stored event and the corresponding invocation fact:

```javascript
state.user.id EXISTS AND event.agent.sent.email WHERE user_id == '{{user.id}}' IN 'PT24H'
```

Provide `state("user.id", user_id)` and ingest the same `user_id` attribute. A WHERE comparison to a literal `state.user.id` expression is not supported; use the template shown above.


## Value Reachability (Beyond Presence)

Atom **presence** reachability checks whether the key exists. **Value** reachability checks whether the emitted value can actually satisfy the trigger condition. Evaluate both against each Boolean branch; presence alone does not establish that the intended positive condition is reachable.

### Value Reachability Checklist

For every trigger condition, verify:

1. **Is the atom always emitted, or only conditionally?** — Check conditional builders and test the full expression when each input is absent, not just individual positive predicates.
2. **When conditionally omitted, does the missing key make the trigger silently FALSE?** — `null > 60` is FALSE, `null == false` is FALSE. This is especially dangerous when the omitted case is the exact scenario the trigger should catch.
3. **Do value types match the comparison operators?** — Int vs string, Python bool vs DSL `true`/`false` literal.
4. **Are referenced events actually ingested?** — Cross-reference every `event.X.Y.Z` in triggers against the event emission map. `NOT event.X IN 'duration'` on a never-ingested event is always TRUE — the guard does nothing.

### Pattern 7: Sentinel Omission (Conditional Key Skipped)

```python
# ATOM builder — BROKEN
def entity_enriched_atoms(db, entity):
    days = _days_since(entity.last_upload_at)  # Returns None if never uploaded
    if days is not None:
        enriched["days_since_last_upload"] = days  # Key OMITTED when None

# EMU trigger
trigger = "state.entity.days_since_last_upload > 60"
# Entity that NEVER uploaded → key missing → > 60 is FALSE → EMU doesn't fire
# But "never uploaded" is the MOST inactive case!
```

**Possible fix**, only if the business contract defines “never uploaded” as maximally inactive: use a documented sentinel. Otherwise expose a separate presence/history fact and define the rule explicitly:
```python
enriched["days_since_last_upload"] = days if days is not None else 9999
```

### Pattern 8: Ghost Event Guard

```python
# Event emission map
_AUDIT_TO_EVENT = {
    ("login", "user"): "client.logged.in",
    # ❌ No entry for "client.accessed.vault"!
}

# EMU trigger
trigger = "NOT event.client.accessed.vault IN 'P5D' AND state.engagement.status == 'pending'"
# "client.accessed.vault" is never ingested → NOT (no match) → NOT FALSE → TRUE
# The guard is ALWAYS true — EMU fires even if the client HAS accessed the vault
```

**Fix**: Add event ingestion for vault access, or use a state atom instead.

### Pattern 9: Unguarded Conditional Key

```javascript
// checklist_complete is only emitted when has_checklist is true AND template exists
// BROKEN: no guard — for engagements without checklists, checklist_complete is missing
trigger = "state.engagement.days_until_due_date <= 14 AND state.engagement.checklist_complete == false"

// FIXED: add explicit guard so intent is clear
trigger = "... AND state.engagement.has_checklist == true AND state.engagement.checklist_complete == false"
```

### Pattern 10: Orphaned Atom Scope

```python
# Builder exists but is never called in any decision path
def document_atoms(doc: Document) -> list:
    return StateObject("document", {"is_classified": ...}).to_atoms()

# Neither decision function calls it
async def decide_for_engagement(db, eng):
    atoms = engagement_enriched_atoms(db, eng)  # ← no document_atoms()

# EMU referencing state.document.* is completely unreachable
trigger = "state.document.is_classified == false"
```

**Fix**: Add a per-document evaluation pass or fold the needed metrics into the parent scope (e.g., `state.engagement.unclassified_doc_count`).

---

## Debugging Unreachable Triggers

### Step 1: Enable Tracing

Use the runtime monitoring example above. Inspect candidate reasons and suppression, not an invented `evaluated_emus` response field.

### Step 2: Analyze Dependencies

Compare the named decision point's actual atoms with the trigger and action-template contracts. Verify missing/null behavior for each Boolean branch. Use candidate validation reports to check observed registry names and types.

### Step 3: Test in Isolation

Use an isolated project or dedicated named decision point with known policy bindings. The SDK does not accept an `emus=[...]` filter on decide. Use dry-run and assert both expected selections and unexpected non-selections.

### Step 4: Check Event History

Inspect stored events in the console or the project's event API. Verify tenant/project scope, topic order, timestamps, attributes, anchors, effective retention, and the query's evaluation time. Do not assume an SDK `list_events` method exists.


### Step 5: Validate ATOM Builders

Document and validate ATOM builders:

```python
# atoms_spec.yaml
atoms:
  state:
    - key: user.tier
      source: crm_integration
      description: "User subscription tier"
      values: ["free", "premium", "enterprise"]
    - key: user.lifetime_value
      source: analytics_pipeline
      description: "Calculated LTV"
      type: float

  tag:
    - kind: intent
      source: intent_classifier_v2
      description: "User intent from NLP"
      values: ["upgrade", "support", "billing", "cancel"]

  event:
    - topic: agent.sent.email
      source: email_service_webhook
      description: "Email sent by agent"
      anchor_roles: ["agent", "customer"]
```

### Debugging Checklist

When trigger doesn't fire:

1. [ ] Check trace output for failure reason
2. [ ] Extract and verify ATOM dependencies
3. [ ] Test trigger in isolation with dry_run
4. [ ] Query event history for event-based triggers
5. [ ] Verify ML models are deployed (for ML tags)
6. [ ] Check ATOM builder implementation
7. [ ] Verify binding context (for binding triggers)
8. [ ] Check event storage duration (for old events)

## Best Practices

### 1. Document ATOM Dependencies

```python
"""
EMU: vip_escalation
Trigger: state.customer.tier == 'vip' AND state.ticket.priority == 'high'

ATOM Dependencies:
- state("customer.tier", ...) - From CRM integration
- state("ticket.priority", ...) - From ticket system API

ML Dependencies: None

Event Dependencies: None
"""
```

### 2. Validate Before Deployment

Run local JSONL/DSL validation and `emu-plan --strict`, then review the proposed diff and policy tests before `emu-apply --strict`. Keep observed-ATOM health checks separate from business correctness.


### 3. Monitor Trigger Reach Rate

```python
# Track how often trigger evaluates to TRUE
metrics.gauge("emu.trigger.reach_rate", {
    "emu_key": emu_key,
    "rate": true_evaluations / total_evaluations
})

# Alert on low reach rate
if reach_rate < 0.01:  # < 1%
    alert("Low trigger reach rate", emu_key=emu_key)
```

### 4. Use Shadow Mode

Apply a new candidate with a matching shadow target, or use an explicit lifecycle transition for an existing record. Review its trace candidates; it must not enter executable selections. Promote only after the relevant tests and observed behavior meet the rollout criteria.


### 5. Build Incrementally

Start with simple, reachable triggers:

```python
# Phase 1: Simple state check
trigger_v1 = "state.user.tier == 'premium'"

# Phase 2: Add event check
trigger_v2 = "state.user.tier == 'premium' AND NOT event.agent.sent.email IN 'P7D'"

# Phase 3: Add ML tag
trigger_v3 = "state.user.tier == 'premium' AND NOT event.agent.sent.email IN 'P7D' AND tag.intent == 'upgrade'"
```
