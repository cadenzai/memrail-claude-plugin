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

**Trigger reachability** is the concept that a trigger can only fire if all required ATOMs are available at invoke time.

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

1. **Silent failures**: Triggers don't error, they just evaluate to `FALSE`
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

Event-based triggers require proper event ingestion.

### Event Ingestion Workflow

```python
# 1. System event occurs (external to AMI)
# Example: Agent sends email via email service

# 2. Your application captures event
async def on_email_sent(agent_id, email_id, recipient):
    # Capture event details
    ...

    # 3. Ingest event to AMI
    await ami_client.ingest_event(
        subject="agent",
        verb="sent",
        object="email",
        ts=datetime.now(timezone.utc),
        attributes={
            "recipient": recipient,
            "template": "welcome_email"
        },
        anchor={
            "subject": {"type": "agent", "id": agent_id},
            "object": {"type": "email", "id": email_id}
        }
    )

# 4. Event is now available for event queries
# event.agent.sent.email IN 'PT24H' can now match
```

### Event Storage Duration

Events are stored for **90 days** by default. Triggers with windows > 90 days may not reach all events.

```javascript
// ✅ Safe: Within storage window
event.user.login.success IN 'P30D'  // Last 30 days

// ⚠️ Risky: Beyond storage window
event.user.created.account IN 'P180D'  // Last 180 days (may miss events)
```

### Event Ingestion Patterns

#### Pattern 1: Inline Ingestion

Ingest events immediately after they occur:

```python
async def handle_ticket_created(ticket):
    # 1. Create ticket in system
    ticket_id = await ticket_system.create(ticket)

    # 2. Immediately ingest event
    await ami_client.ingest_event(
        subject="ticket",
        verb="created",
        object="zendesk",
        ts=datetime.now(timezone.utc)
    )
```

**Pros**: Simple, low latency
**Cons**: Couples AMI to business logic

#### Pattern 2: Event Bus

Use event bus/queue for decoupled ingestion:

```python
# Publisher
async def handle_ticket_created(ticket):
    await event_bus.publish("ticket.created", ticket)

# Subscriber (separate service)
async def ingest_to_ami(event):
    if event.type == "ticket.created":
        await ami_client.ingest_event(
            subject="ticket",
            verb="created",
            object="zendesk",
            ts=event.timestamp
        )
```

**Pros**: Decoupled, resilient, scalable
**Cons**: Increased complexity

#### Pattern 3: Batch Ingestion

Ingest events in batches:

```python
# Collect events
events = [
    {"subject": "user", "verb": "login", "object": "app", "ts": ...},
    {"subject": "user", "verb": "clicked", "object": "button", "ts": ...},
    ...
]

# Batch ingest
await ami_client.batch_ingest_events(events)
```

**Pros**: Efficient, reduced API calls
**Cons**: Increased latency

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

Analyze trigger to determine ATOM dependencies:

```python
from ami.analysis import extract_dependencies

trigger = "state.user.tier == 'premium' AND tag.intent == 'upgrade'"
deps = extract_dependencies(trigger)

# Result:
{
    "state_keys": ["user.tier"],
    "tag_kinds": ["intent"],
    "event_topics": []
}

# Check if ATOM builders exist
for key in deps["state_keys"]:
    assert has_atom_builder(key), f"Missing ATOM builder for {key}"

for kind in deps["tag_kinds"]:
    assert has_ml_classifier(kind), f"Missing ML classifier for {kind}"
```

### Runtime Monitoring

Track trigger evaluation results:

```python
response = await ami_client.decide(
    context=[...],
    trace=True  # Enable tracing
)

# Check trace for reachability issues
for item in response.trace.evaluated_emus:
    if not item.trigger_result:
        print(f"EMU {item.emu_key} did not fire")
        print(f"  Reason: {item.failure_reason}")
        # Example reasons:
        # - "Missing state atom: user.tier"
        # - "Missing tag: intent"
        # - "No matching events: agent.sent.email"
```

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

```javascript
// EMU trigger (with event binding - advanced feature)
// Note: Event binding may not be available in all DSL versions
trigger = "event.agent.sent.email IN 'PT24H' WITH bind(subject='same')  // Advanced: bind events to specific entities"

// Invoke without agent.id
decide(context=[
    state("ticket.id", "TICKET-123")
    // ❌ Missing: agent.id for binding
])

// Result: Trigger unreachable (strict reachability failure)
```

**Fix**: Provide role IDs in context:

```python
decide(context=[
    state("agent.id", "AGT-123"),  # Required for binding
    state("ticket.id", "TICKET-123")
])
```

## Value Reachability (Beyond Presence)

Atom **presence** reachability checks whether the key exists. **Value** reachability checks whether the emitted value can actually satisfy the trigger condition. Both must pass for an EMU to fire.

### Value Reachability Checklist

For every trigger condition, verify:

1. **Is the atom always emitted, or only conditionally?** — Check the builder for `if` guards that skip key emission when a value is None. A missing key silently evaluates to FALSE.
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

**Fix**: Emit a sentinel value instead of omitting:
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

```python
response = await ami_client.decide(
    context=[...],
    trace=True
)

# Check trace
for emu in response.trace.evaluated_emus:
    if not emu.trigger_result:
        print(f"EMU {emu.emu_key} unreachable")
        print(f"  Trigger: {emu.trigger}")
        print(f"  Reason: {emu.failure_reason}")
```

### Step 2: Analyze Dependencies

```python
# Extract dependencies
deps = extract_dependencies(trigger)

# Check each dependency
print("Required state keys:", deps["state_keys"])
print("Required tag kinds:", deps["tag_kinds"])
print("Required event topics:", deps["event_topics"])

# Verify atoms provided
provided_states = [atom.key for atom in atoms if atom.type == "state"]
provided_tags = [atom.kind for atom in atoms if atom.type == "tag"]

missing_states = set(deps["state_keys"]) - set(provided_states)
missing_tags = set(deps["tag_kinds"]) - set(provided_tags)

print("Missing states:", missing_states)
print("Missing tags:", missing_tags)
```

### Step 3: Test in Isolation

Test trigger with minimal atoms:

```python
# Test state function in isolation
response = await ami_client.decide(
    context=[state("user.tier", "premium")],
    emus=["test_emu"],  # Only evaluate this EMU
    options=InvokeOptions(dry_run=True)
)

# Should fire if state check is only dependency
assert len(response.selected) == 1, "State check failed"
```

### Step 4: Check Event History

```python
# Query events
events = await ami_client.list_events(
    subject="agent",
    verb="sent",
    object="email",
    start_time=datetime.now(timezone.utc) - timedelta(days=1)
)

print(f"Found {len(events)} events")
for event in events:
    print(f"  {event.ts}: {event.subject}.{event.verb}.{event.object}")
```

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

### 2. Validate at Registration

```python
async def register_emu_with_validation(emu_spec):
    # Extract dependencies
    deps = extract_dependencies(emu_spec["trigger"])

    # Validate
    for key in deps["state_keys"]:
        if not atom_registry.has_builder(key):
            raise ValueError(f"No ATOM builder for {key}")

    # Register
    await ami_client.register_emu(**emu_spec)
```

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

Test new EMUs in shadow mode first:

```python
# Register as shadow
await ami_client.register_emu(
    emu_key="new_emu",
    trigger="...",
    state="shadow"  # Evaluate but don't execute
)

# Monitor evaluation
# Once satisfied, promote to active
await ami_client.update_emu_state("new_emu", "active")
```

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
