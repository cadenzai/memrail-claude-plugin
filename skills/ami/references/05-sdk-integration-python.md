# SDK Integration (Python)

**Using the Python SDK to Build and Invoke EMUs**

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [ATOM Builders](#atom-builders)
- [EMU Management](#emu-management)
- [Invoking the Engine](#invoking-the-engine)
- [Event Ingestion](#event-ingestion)
- [Complete Workflows](#complete-workflows)
- [Testing & Debugging](#testing--debugging)
- [Error Handling](#error-handling)
- [CLI Commands](#cli-commands)
- [Workspace Management](#workspace-management)
- [EMU Validation Reports](#emu-validation-reports)
- [Best Practices](#best-practices)

## Installation

### Requirements

- Python 3.8+
- pip or uv (recommended)

### Install SDK

```bash
# Using pip
pip install ami-sdk

# Using uv (faster)
uv pip install ami-sdk
```

### Verify Installation

```python
import ami
print(ami.__version__)  # e.g., "2.0.0"
```

## Configuration

### API Key Setup

Obtain API key from AMI dashboard or bootstrap script:

```bash
# Bootstrap creates org + keys
uv run python scripts/bootstrap_org.py --name "My Org" --region us-miami-1
```

### Configuration Methods

#### Method 1: Environment Variables (Recommended)

```bash
export AMI_API_KEY="your-api-key"
export AMI_ORG="your-org-slug"
export AMI_TEAM="your-team-slug"  # Optional - defaults to "default" team if not specified
export AMI_WORKSPACE="production"
export AMI_PROJECT="onboarding"
export AMI_BASE_URL="https://api.ami.example.com"  # Optional, defaults to production
```

```python
from ami import AsyncAMIClient

# Auto-loads from environment
async with AsyncAMIClient() as client:
    response = await client.decide(context=[...])
```

#### Method 2: Explicit Configuration

```python
from ami import AsyncAMIClient

async with AsyncAMIClient(
    api_key="your-api-key",
    org="your-org-slug",
    team="your-team-slug",  # Optional - defaults to "default" team if not specified
    workspace="production",
    project="onboarding",
    base_url="https://api.ami.example.com"
) as client:
    response = await client.decide(context=[...])
```

#### Method 3: Configuration Object

```python
from ami import AsyncAMIClient
from ami.config import AMIConfig

config = AMIConfig.create(
    api_key="your-api-key",
    org="your-org-slug",
    team="your-team-slug",  # Optional - defaults to "default" team if not specified
    workspace="production",
    project="onboarding"
)

async with AsyncAMIClient.from_config(config) as client:
    response = await client.decide(context=[...])
```

### Default Team Behavior

If you don't specify a team, the API will automatically use the "default" team for your organization:

```python
# No team specified - uses "default" team automatically
async with AsyncAMIClient(
    api_key="your-api-key",
    org="your-org-slug"
    # team parameter omitted - defaults to "default"
) as client:
    response = await client.decide(context=[...])
```

This is particularly useful for single-tenant use cases where you only have one team.

### Context Override

Override workspace/project per-call:

```python
async with AsyncAMIClient(org="my-org", team="my-team") as client:
    # Override workspace/project
    response = await client.decide(
        context=[...],
        workspace="staging",  # Override
        project="test-app"     # Override
    )
```

## ATOM Builders

ATOMs are typed facts provided to the decision engine.

### State ATOMs

State ATOMs represent structured data from your system.

```python
from ami.atoms import state

# Simple state
atoms = [
    state("user.id", "U-123"),
    state("user.tier", "premium"),
    state("user.age", 25),
    state("user.verified", True)
]

# Nested state (use dot notation)
atoms = [
    state("ticket.id", "TICKET-456"),
    state("ticket.priority", "high"),
    state("ticket.sla_remaining_hours", 2),
    state("customer.tier", "vip"),
    state("customer.lifetime_value", 50000)
]
```

**Type Support**:
- `str`: String values
- `int`, `float`: Numeric values
- `bool`: Boolean values
- No complex types (dict, list) - flatten to dot notation

**Dict Helper** (Recommended for Complex Data):

For complex nested objects, use `atoms_from_dict` to automatically flatten:

```python
from ami.atoms import atoms_from_dict

# Complex object from your application
user = {
    "id": "U-123",
    "tier": "premium",
    "age": 25,
    "verified": True,
    "metadata": {
        "signup_source": "organic",
        "referrer": "google"
    }
}

# Automatically creates: user.id, user.tier, user.age, user.verified, user.metadata.signup_source, etc.
atoms = atoms_from_dict(user, prefix="user")
```

### Tag ATOMs

Tag ATOMs represent categorizations and metadata.

```python
from ami.atoms import tag

# Simple tags
atoms = [
    tag("priority", "high"),
    tag("channel", "email"),
    tag("language", "spanish")
]

# ML-inferred tags
sentiment = sentiment_classifier.predict(text)
intent = intent_classifier.predict(message)

atoms = [
    tag("sentiment", sentiment),  # "positive", "negative", "neutral"
    tag("intent", intent),         # "upgrade", "cancel", "support"
    tag("category", "billing_issue")
]
```

**Naming conventions**:
- Lowercase
- Underscores for multi-word (e.g., `user_segment`)
- Semantic names (e.g., `sentiment`, not `ml_output_1`)

### Event ATOMs

Event ATOMs represent timestamped occurrences.

```python
from ami.atoms import event
from datetime import datetime, timezone

# Simple event (timestamp = now)
atoms = [
    event("user.login.success")
]

# Event with explicit timestamp
atoms = [
    event("agent.sent.email", ts=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc))
]

# Event with attributes
atoms = [
    event("payment.completed.stripe",
          ts=datetime.now(timezone.utc),
          attributes={"amount": 1000, "currency": "USD"})
]

# Event with anchors (AMI v2 - role binding)
atoms = [
    event("agent.contacted.customer",
          ts=datetime.now(timezone.utc),
          anchor={
              "subject": {"type": "agent", "id": "AGT-123"},
              "object": {"type": "customer", "id": "CUST-456"}
          })
]
```

## EMU Management

### JSONL Sync Workflow (Recommended)

EMUs are managed via JSONL files using the IaC sync workflow:

```bash
# Pull existing EMUs from remote
ami emu-pull ./emus/ -w production -p my-project

# Edit ./emus/emus.jsonl (one EMU per line)
# Add, modify, or delete EMUs

# Preview changes (like terraform plan)
ami emu-plan ./emus/

# Apply changes to remote
ami emu-apply ./emus/ --yes
```

**JSONL format:**
```jsonl
{"emu_key":"vip_escalation","trigger":"state.customer.tier == 'vip' AND state.ticket.priority == 'high'","action":{"type":"tool_call","intent":"ESCALATE_VIP","tool":{"tool_id":"zendesk_escalator","version":"1.0.0","args":{"queue":"vip-support"}}},"policy":{"mode":"auto","priority":9,"cooldown":{"seconds":7200,"gate":"ack"}},"expected_utility":0.95,"confidence":0.88,"intent":"Escalate VIP customer tickets to specialist queue"}
{"emu_key":"welcome_premium","trigger":"state.user.tier == 'premium'","action":{"type":"tool_call","intent":"SEND_WELCOME_EMAIL","tool":{"tool_id":"mailer","version":"1.0.0","args":{"template":"premium_welcome"}}},"expected_utility":0.9,"confidence":0.95,"intent":"Welcome new premium users with onboarding email"}
```

**Why JSONL:**
- Git-diff friendly (one EMU per line)
- PR-reviewable
- No code execution required
- CI/CD integration via pipeline
- Lock file tracks deployed state

### SDK Registration (Scripting/Testing Only)

For quick prototyping or scripted migrations, use the SDK directly:

```python
async with AsyncAMIClient() as client:
    response = await client.register_emu(
        emu_key="welcome_premium_users",
        trigger="state.user.tier == 'premium'",
        action={
            "type": "tool_call",
            "intent": "SEND_WELCOME_EMAIL",
            "tool": {
                "tool_id": "mailer",
                "version": "1.0.0",
                "args": {"template": "premium_welcome"}
            }
        },
        expected_utility=0.9,
        confidence=0.95,
        intent="Welcome new premium users",
        decision_point="onboarding-check",  # Optional: scope to invocation site
        workspace="production",
        project="onboarding"
    )

    print(f"Registered EMU: {response['emu_id']} (v{response['version']})")
```

### Updating Existing EMUs

Use `update_emu()` to modify an existing EMU without archiving. This preserves version history and activation data.

```python
# Update trigger and policy for an existing EMU
response = await client.update_emu(
    emu_key="vip_escalation",
    trigger="state.customer.tier == 'vip' AND state.ticket.priority >= 'high'",  # Modified trigger
    expected_utility=0.95,
    confidence=0.90,
    policy={
        "mode": "auto",
        "priority": 10,  # Increased priority
        "cooldown": {"seconds": 3600, "gate": "activation"}
    },
    action={
        "type": "tool_call",
        "intent": "ESCALATE_TO_VIP_TEAM",
        "tool": {"tool_id": "zendesk_escalator", "version": "2.2.0"}
    },
    workspace="production",
    project="support"
)

print(f"Updated EMU: {response['emu_key']} - {response.get('message', 'success')}")
```

**API Endpoint**: `PUT /v1/workspaces/{workspace}/projects/{project}/emus/{emu_key}`

**When to use `update_emu()` vs `register_emu()`**:

| Scenario | Method |
|----------|--------|
| Creating a new EMU | `register_emu()` |
| Modifying trigger/action/policy | `update_emu()` |
| EMU doesn't exist yet | `register_emu()` |
| Preserving version history | `update_emu()` |

### Changing Lifecycle State

Use `update_emu_lifecycle()` to transition an EMU between states:

```python
# Promote EMU from shadow to active
response = await client.update_emu_lifecycle(
    emu_key="vip_escalation",
    state="active",  # draft, shadow, canary, active, archived
    workspace="production",
    project="support"
)
```

**Lifecycle progression**: `draft` -> `shadow` -> `canary` -> `active` -> `archived`

### Registration with Full Policy

```python
response = await client.register_emu(
    emu_key="vip_escalation",
    trigger="state.customer.tier == 'vip' AND state.ticket.priority == 'high'",
    action={
        "type": "tool_call",
        "intent": "ESCALATE_TO_VIP_TEAM",
        "tool": {
            "tool_id": "zendesk_escalator",
            "version": "2.1.0",
            "args": {
                "queue": "vip-support",
                "priority": "critical"
            }
        }
    },
    policy={
        "mode": "auto",
        "priority": 9,
        "cooldown": {
            "seconds": 7200,
            "gate": "activation"
        },
        "idempotency": {
            "enabled": True,
            "scope": ["customer.id", "ticket.id"]
        },
        "exclusion_groups": ["escalation_actions"]
    },
    expected_utility=0.95,
    confidence=0.88,
    decision_point="triage",  # Scope to triage decision point
    workspace="production",
    project="support"
)
```

### Action Types

#### tool_call

```python
action={
    "type": "tool_call",
    "intent": "SEND_EMAIL",
    "tool": {
        "tool_id": "mailer",
        "version": "1.0.0",
        "args": {
            "to": "{{user.email}}",
            "template": "welcome"
        }
    }
}
```

#### decision_prompt

```python
action={
    "type": "decision_prompt",
    "message": "High-risk transaction from {{user.id}}. Approve?",
    "options": [
        {"id": "approve", "label": "Approve Transaction"},
        {"id": "decline", "label": "Decline Transaction"},
        {"id": "review", "label": "Manual Review"}
    ]
}
```

#### route

```python
action={
    "type": "route",
    "destination": "spanish_support_queue",
    "metadata": {
        "language": "spanish",
        "priority": "standard"
    }
}
```

#### context_directive

```python
action={
    "type": "context_directive",
    "directive": "Customer is VIP tier. Follow escalation protocol per KB #4521"
}
```

### Versioning

```python
# Register v1
response_v1 = await client.register_emu(
    emu_key="lead_scorer",
    trigger="state.lead.source == 'website'",
    ...
)
print(f"Version: {response_v1['version']}")  # 1

# Register v2 (same key, new trigger)
response_v2 = await client.register_emu(
    emu_key="lead_scorer",  # Same key!
    trigger="state.lead.source == 'website' AND state.lead.company_size >= 100",
    ...
)
print(f"Version: {response_v2['version']}")  # 2
```

## Invoking the Engine

### Basic Invocation

```python
from ami.atoms import state, tag

async with AsyncAMIClient() as client:
    response = await client.decide(
        context=[
            state("user.id", "U-123"),
            state("user.tier", "premium"),
            tag("intent", "upgrade")
        ],
        decision_point="onboarding-check",
        workspace="production",
        project="onboarding"
    )

    # Process selected actions
    for item in response.selected:
        print(f"EMU: {item.emu_key}")
        print(f"Action: {item.action}")
        print(f"Priority: {item.priority}")
```

### Using Dict Helper for Complex Data

When you have complex nested data structures, use the `atoms_from_dict` helper to automatically flatten them:

```python
from ami.atoms import state, tag, atoms_from_dict

# Complex nested data from your application
user_data = {
    "id": "U-123",
    "tier": "premium",
    "age": 25,
    "verified": True,
    "preferences": {
        "language": "en",
        "timezone": "America/New_York"
    }
}

ticket_data = {
    "id": "TICKET-456",
    "priority": "high",
    "sla_remaining_hours": 2,
    "status": "open"
}

# Convert dicts to state atoms automatically
async with AsyncAMIClient() as client:
    response = await client.decide(
        context=[
            # Dict helper flattens nested structures to dot notation
            *atoms_from_dict(user_data, prefix="user"),      # Creates: user.id, user.tier, user.preferences.language, etc.
            *atoms_from_dict(ticket_data, prefix="ticket"),  # Creates: ticket.id, ticket.priority, etc.

            # Add tags manually
            tag("intent", "upgrade"),
            tag("channel", "email")
        ],
        workspace="production",
        project="onboarding"
    )
```

**What `atoms_from_dict` does:**
```python
# Input
atoms_from_dict(
    {"tier": "premium", "age": 25, "preferences": {"language": "en"}},
    prefix="user"
)

# Output (equivalent to)
[
    state("user.tier", "premium"),
    state("user.age", 25),
    state("user.preferences.language", "en")
]
```

**Benefits:**
- Automatically flattens nested dicts to dot notation
- Handles all supported types (str, int, float, bool)
- Skips unsupported types (lists, dicts without flattening)
- Cleaner code when working with existing data structures

### With Options

```python
from ami.models import InvokeOptions

response = await client.decide(
    context=[...],
    options=InvokeOptions(
        dry_run=True,      # Don't actually execute, just evaluate
        top_k=5,           # Return top 5 matches (default: None - no limit)
        explain=True       # Include explanation of why EMUs matched
    ),
    workspace="production",
    project="onboarding"
)
```

### With Tracing

```python
from ami.models import TraceOptions

response = await client.decide(
    context=[...],
    trace=TraceOptions(
        enable=True,
        include_all_emus=True  # Show all evaluated EMUs, not just selected
    ),
    workspace="production",
    project="onboarding"
)

# Examine trace
if response.trace:
    print(f"Evaluated {len(response.trace.evaluated_emus)} EMUs")
    for emu in response.trace.evaluated_emus:
        print(f"  {emu.emu_key}: {emu.trigger_result}")
```

### With Context Timestamp

Provide custom timestamp for time-based queries:

```python
from datetime import datetime, timezone

# Test with historical timestamp
response = await client.decide(
    context=[...],
    context_ts=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    workspace="production",
    project="onboarding"
)
```

### With Idempotency

```python
# First request
response1 = await client.decide(
    context=[state("order.id", "ORDER-123")],
    idempotency_key="order-123-payment",
    workspace="production",
    project="checkout"
)

# Second request (returns cached response)
response2 = await client.decide(
    context=[state("order.id", "ORDER-123")],
    idempotency_key="order-123-payment",  # Same key
    workspace="production",
    project="checkout"
)

# Check if cached
if response2.idempotency and response2.idempotency.applied:
    print("Returned cached response")
```

### Response Handling

```python
from ami.models import InvokeResponse, SelectedItem

response: InvokeResponse = await client.decide(context=[...])

# Check if any EMUs fired
if response.selected:
    for item in response.selected:
        # Execute action based on type
        if item.action.type == "tool_call":
            await execute_tool(item.action.tool)
        elif item.action.type == "decision_prompt":
            await present_decision(item.action.message, item.action.options)
        elif item.action.type == "route":
            await route_to_queue(item.action.destination)
        elif item.action.type == "context_directive":
            await display_context(item.action.directive)
else:
    print("No EMUs fired")

# Check invocation metadata
print(f"Invocation ID: {response.invocation_id}")
print(f"Processed in: {response.processing_time_ms}ms")
```

## Event Ingestion

Events must be ingested separately (not via invoke).

### Single Event Ingestion

```python
from datetime import datetime, timezone

async with AsyncAMIClient() as client:
    await client.ingest_event(
        subject="agent",
        verb="sent",
        object="email",
        ts=datetime.now(timezone.utc),
        attributes={
            "recipient": "customer@example.com",
            "template": "welcome_email"
        },
        anchor={
            "subject": {"type": "agent", "id": "AGT-123"},
            "object": {"type": "email", "id": "EMAIL-456"}
        },
        workspace="production",
        project="support"
    )
```

### Batch Event Ingestion

```python
from ami.models import EventInput

events = [
    EventInput(
        subject="user",
        verb="login",
        object="app",
        ts=datetime.now(timezone.utc)
    ),
    EventInput(
        subject="user",
        verb="clicked",
        object="button",
        ts=datetime.now(timezone.utc),
        attributes={"button_id": "checkout"}
    ),
]

await client.batch_ingest_events(
    events=events,
    workspace="production",
    project="analytics"
)
```

### Event Ingestion Patterns

#### Pattern 1: Inline with Business Logic

```python
async def handle_ticket_created(ticket_data):
    # 1. Create ticket
    ticket = await ticket_system.create(ticket_data)

    # 2. Ingest event
    await ami_client.ingest_event(
        subject="ticket",
        verb="created",
        object="zendesk",
        ts=datetime.now(timezone.utc),
        attributes={"ticket_id": ticket.id}
    )

    # 3. Decide
    response = await ami_client.decide(
        context=[
            state("ticket.id", ticket.id),
            state("ticket.priority", ticket.priority),
            state("customer.tier", ticket.customer.tier)
        ]
    )

    # 4. Execute actions
    for item in response.selected:
        await execute_action(item.action)
```

#### Pattern 2: Async Event Bus

```python
# Publisher
async def on_user_login(user_id):
    await event_bus.publish("user.login.success", {"user_id": user_id})

# Consumer (separate service)
async def consume_events():
    async for event in event_bus.subscribe("user.login.success"):
        await ami_client.ingest_event(
            subject="user",
            verb="login",
            object="app",
            ts=event.timestamp,
            attributes={"user_id": event.data["user_id"]}
        )
```

## Complete Workflows

### Workflow 1: Support Ticket Automation

```python
from ami import AsyncAMIClient
from ami.atoms import atoms_from_dict, tag, event
from datetime import datetime, timezone

async def handle_ticket_created(ticket):
    async with AsyncAMIClient() as client:
        # 1. Ingest event
        await client.ingest_event(
            subject="ticket",
            verb="created",
            object="zendesk",
            ts=datetime.now(timezone.utc),
            workspace="production",
            project="support"
        )

        # 2. Build atoms using dict helper (cleaner for complex objects)
        ticket_data = {
            "id": ticket.id,
            "priority": ticket.priority,
            "sla_remaining_hours": ticket.sla_remaining_hours,
            "status": ticket.status
        }

        customer_data = {
            "id": ticket.customer.id,
            "tier": ticket.customer.tier,
            "lifetime_value": ticket.customer.lifetime_value
        }

        atoms = [
            # Use dict helper to flatten nested data
            *atoms_from_dict(ticket_data, prefix="ticket"),
            *atoms_from_dict(customer_data, prefix="customer"),

            # Add ML tags manually
            tag("category", ticket.category),
            tag("language", ticket.language)
        ]

        # 3. Invoke decision engine
        response = await client.decide(
            context=atoms,
            workspace="production",
            project="support"
        )

        # 4. Execute selected actions
        for item in response.selected:
            if item.action.type == "tool_call":
                await execute_tool(item.action.tool)
            elif item.action.type == "route":
                await route_ticket(ticket.id, item.action.destination)
            elif item.action.type == "decision_prompt":
                await notify_agent(item.action.message, item.action.options)

async def execute_tool(tool_spec):
    """Execute tool based on tool_id."""
    if tool_spec.tool_id == "zendesk_escalator":
        await escalate_ticket(**tool_spec.args)
    elif tool_spec.tool_id == "email_service":
        await send_email(**tool_spec.args)
    # ... more tools
```

### Workflow 2: User Onboarding

```python
from ami.atoms import atoms_from_dict, tag

async def check_user_onboarding(user_id):
    # Fetch user data
    user = await user_service.get_user(user_id)

    async with AsyncAMIClient() as client:
        # Build user state from dict
        user_data = {
            "id": user.id,
            "tier": user.subscription_tier,
            "onboarding_step": user.onboarding_step,
            "signup_hours_ago": (datetime.now(timezone.utc) - user.signup_at).total_seconds() / 3600,
            "verified": user.email_verified,
            "signup_completed": True
        }

        atoms = [
            *atoms_from_dict(user_data, prefix="user")
        ]

        # Check if ML tags needed
        if user.last_message:
            intent = intent_classifier.predict(user.last_message)
            atoms.append(tag("intent", intent))

        # Decide
        response = await client.decide(
            context=atoms,
            workspace="production",
            project="onboarding"
        )

        # Process actions
        for item in response.selected:
            if item.action.type == "tool_call":
                await execute_onboarding_action(item.action)
```

### Workflow 3: ML-Augmented Support

```python
async def handle_support_message(message_data):
    # 1. Run ML inference
    sentiment = sentiment_classifier.predict(message_data.text)
    intent = intent_classifier.predict(message_data.text)
    category = topic_classifier.predict(message_data.text)

    async with AsyncAMIClient() as client:
        # 2. Build atoms with ML tags
        atoms = [
            state("ticket.id", message_data.ticket_id),
            state("customer.tier", message_data.customer_tier),
            tag("sentiment", sentiment),      # ML-inferred
            tag("intent", intent),             # ML-inferred
            tag("category", category),         # ML-inferred
            tag("channel", message_data.channel)
        ]

        # 3. Decide
        response = await client.decide(
            context=atoms,
            workspace="production",
            project="support"
        )

        # 4. Execute actions
        for item in response.selected:
            await execute_action(item)
```

## Testing & Debugging

### Dry Run Mode

Test triggers without executing actions:

```python
response = await client.decide(
    context=[...],
    options=InvokeOptions(dry_run=True),
    workspace="production",
    project="support"
)

# Examine what would fire
print(f"Would execute {len(response.selected)} EMUs:")
for item in response.selected:
    print(f"  - {item.emu_key} (priority: {item.priority})")
```

### Tracing

Debug trigger evaluation:

```python
response = await client.decide(
    context=[...],
    trace=TraceOptions(enable=True, include_all_emus=True),
    workspace="production",
    project="support"
)

# Examine all evaluated EMUs
if response.trace:
    for emu in response.trace.evaluated_emus:
        print(f"EMU: {emu.emu_key}")
        print(f"  Trigger: {emu.trigger}")
        print(f"  Result: {emu.trigger_result}")
        if not emu.trigger_result and emu.failure_reason:
            print(f"  Reason: {emu.failure_reason}")
```

### Shadow Mode Testing

Register EMU in shadow mode for evaluation without execution:

```python
# Register in shadow mode
await client.register_emu(
    emu_key="new_feature",
    trigger="...",
    state="shadow",  # Evaluate but don't execute
    workspace="production",
    project="support"
)

# Monitor evaluation (via tracing)
response = await client.decide(
    context=[...],
    trace=TraceOptions(enable=True),
    workspace="production",
    project="support"
)

# Check if shadow EMU matched
for emu in response.trace.evaluated_emus:
    if emu.emu_key == "new_feature":
        print(f"Shadow EMU matched: {emu.trigger_result}")
```

### Unit Testing

```python
import pytest
from ami import AsyncAMIClient
from ami.atoms import state, tag

@pytest.mark.asyncio
async def test_vip_escalation_fires():
    """Test VIP escalation EMU fires for VIP + high priority."""
    async with AsyncAMIClient() as client:
        response = await client.decide(
            context=[
                state("customer.tier", "vip"),
                state("ticket.priority", "high")
            ],
            options=InvokeOptions(dry_run=True),
            workspace="test",
            project="support"
        )

        # Assert EMU fired
        assert len(response.selected) >= 1
        emu_keys = [item.emu_key for item in response.selected]
        assert "support.vip_escalation" in emu_keys

@pytest.mark.asyncio
async def test_vip_escalation_does_not_fire_for_standard():
    """Test VIP escalation does NOT fire for standard tier."""
    async with AsyncAMIClient() as client:
        response = await client.decide(
            context=[
                state("customer.tier", "standard"),  # Not VIP
                state("ticket.priority", "high")
            ],
            options=InvokeOptions(dry_run=True),
            workspace="test",
            project="support"
        )

        # Assert EMU did NOT fire
        emu_keys = [item.emu_key for item in response.selected]
        assert "support.vip_escalation" not in emu_keys
```

## Error Handling

### Common Errors

```python
from ami.errors import (
    AMIBadRequest,       # Invalid request (e.g., bad DSL syntax)
    AMINotFound,         # Resource not found (workspace, project, EMU)
    AMIUnauthorized,     # Invalid API key
    AMIForbidden,        # Insufficient permissions
    AMIUnprocessable,    # Validation failed
    AMIServerError,      # Server error
    AMIError             # Base error class
)

try:
    response = await client.register_emu(
        emu_key="test_emu",
        trigger="INVALID DSL SYNTAX",
        ...
    )
except AMIBadRequest as e:
    print(f"Bad request: {e}")
    # Handle invalid DSL
except AMINotFound as e:
    print(f"Not found: {e}")
    # Handle missing workspace/project
except AMIUnauthorized as e:
    print(f"Unauthorized: {e}")
    # Check API key
except AMIError as e:
    print(f"AMI error: {e}")
    # Generic error handling
```

### Retry Logic

```python
from ami.errors import AMIServerError
import asyncio

async def decide_with_retry(client, context, max_retries=3):
    """Decide with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            return await client.decide(context=context)
        except AMIServerError as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s...")
            await asyncio.sleep(wait_time)
```

### Validation Before Registration

```python
from ami.validation import validate_trigger_dsl

try:
    # Validate DSL before registering
    validate_trigger_dsl("state.user.tier == 'premium' AND event.user.login.success IN 'PT24H'")

    # DSL is valid, proceed with registration
    await client.register_emu(...)
except Exception as e:
    print(f"Invalid DSL: {e}")
```

## CLI Commands

The `ami` CLI provides commands for EMU and tool management.

### Complete Command Reference

| Command | Description |
|---------|-------------|
| **IaC Sync** | |
| `ami emu-pull` | Export remote EMUs to local JSONL files |
| `ami emu-plan` | Show diff between local and remote (like `terraform plan`) |
| `ami emu-apply` | Push local changes to remote (like `terraform apply`) |
| `ami emu-diff` | Show detailed diff for a specific EMU |
| `ami emu-validate` | Validate local JSONL files against API rules |
| **EMU Management** | |
| `ami list-emus` | List EMUs in workspace/project |
| `ami change-state` | Change EMU lifecycle state (draft/shadow/canary/active/archived) |
| `ami archive` | Archive one or all EMUs |
| `ami register-emu` | Register a single EMU (prefer `emu-apply` for production) |
| **Tool Management** | |
| `ami tool-register` | Upload tool definitions from a Python file |
| `ami tool-list` | List registered tools |
| **Passthrough** | |
| `ami exec <cmd>` | Run any `ami` CLI command directly |

### IaC-Style EMU Sync (Primary Workflow)

#### Workflow Example

```bash
# 1. Pull existing EMUs from remote to local JSONL
ami emu-pull ./emus/ -w production -p my-project

# 2. Edit local JSONL files (add, modify, delete EMUs)
# Creates: ./emus/emus.jsonl and ./emus/.emu.lock.jsonl

# 3. See what would change (dry-run)
ami emu-plan ./emus/

# 4. Apply changes (register new, update modified, archive deleted)
ami emu-apply ./emus/ --yes
```

#### JSONL File Format

```jsonl
{"emu_key":"vip_escalation","trigger":"state.customer.tier == 'vip'","action":{"type":"tool_call","intent":"ESCALATE_VIP","tool":{"tool_id":"escalate","version":"1.0.0"}},"policy":{"cooldown":{"seconds":3600,"gate":"ack"}},"expected_utility":0.9,"confidence":0.85,"intent":"Escalate VIP customer issues"}
{"emu_key":"welcome_user","trigger":"state.user.is_new == true","action":{"type":"tool_call","intent":"SEND_WELCOME","tool":{"tool_id":"mailer","version":"1.0.0"}},"expected_utility":0.8,"confidence":0.9,"intent":"Send welcome email to new users"}
```

#### Lock File

The `.emu.lock.jsonl` file tracks deployed state with content hashes for intelligent diffing:
- **New EMUs**: Local file has EMU not in remote -> `register_emu()`
- **Modified EMUs**: Content hash differs -> `update_emu()`
- **Deleted EMUs**: In lock file but removed locally -> `update_emu_lifecycle(state="archived")`

### Basic EMU Commands

```bash
# List EMUs
ami list-emus -w production -p my-project

# Change lifecycle state
ami change-state my.emu.key active -w production -p my-project
ami change-state my.emu.key shadow  # For testing
ami change-state my.emu.key archived  # Retire

# Archive EMUs
ami archive my.emu.key  # Archive specific EMU
ami archive             # Archive all EMUs in project (with confirmation)
ami archive --force     # Skip confirmation
```

### Passthrough to AMI CLI

For less common operations, use the `exec` passthrough:

```bash
# Run any ami CLI command
ami exec list-workspaces
ami exec get-workspace production
ami exec tool-list
ami exec validate --project my_project
```

---

## Workspace Management

### Purging a Workspace

Reset all data in a workspace without deleting the workspace itself. Useful for dev/testing resets.

**Requires org-level API key.**

```bash
# Purge everything (interactive confirmation)
ami purge-workspace production

# Skip confirmation (CI/CD)
ami purge-workspace staging --yes

# Selective purge
ami purge-workspace development --targets emus,traces,events --yes

# JSON output
ami purge-workspace development --yes --json
```

**Available targets:** `emus`, `traces`, `events`, `asr`, `tools`, `cooldowns`, `prompts`, `hindsight`, `decision_points`

## EMU Validation Reports

Validate EMUs to check trigger reachability, action variable placeholders, and get remediation suggestions. This is the primary debugging tool for identifying what needs to be fixed in your EMUs or registered tools.

### Single EMU Validation

```python
# Validate a single EMU
report = client.get_emu_validator("welcome-email", workspace="production")
if not report["passed"]:
    for w in report["warnings"]:
        print(f"[{w['severity']}] {w['code']}: {w['message']}")
        if w.get("remediation"):
            print(f"  Fix: {w['remediation']}")
```

### Workspace Bulk Validation

```python
# Validate ALL EMUs in a workspace
result = client.validate_workspace_emus(workspace="production")
print(f"Validated {result['total']} EMUs")

for item in result["reports"]:
    report = item["report"]
    status = "PASS" if report["passed"] else "FAIL"
    print(f"  [{status}] {item['emu_key']} ({item['state']})")
    for w in report.get("warnings", []):
        if w["severity"] == "error":
            print(f"    ERROR: {w['message']}")
```

### Validation Report Fields

- `passed`: True if no errors (warnings are OK)
- `warnings`: List with `code`, `severity`, `message`, `remediation`
  - Warning codes: `WARN-NEVER-SEEN`, `WARN-SCHEMA-MISMATCH`, `WARN-LOW-REACH`, etc.
- `reachability`: `{total_dependencies, reachable_dependencies, unreachable_dependencies}`
- `action_variables`: Per-variable validation (whether action placeholders reference observed atoms)
- `alias_suggestions`: Suggested fixes for unrecognized atom names (typo detection)

### HTTP API

```
GET /v1/emus/{emu_key}/validator    # Single EMU validation
GET /v1/emus/validator              # All EMUs in workspace (bulk)
POST /v1/.../emus?validate=true     # Inline validation on register
PUT  /v1/.../emus/{key}?validate=true  # Inline validation on update
```

Both GET endpoints accept `X-AMI-Workspace` header to scope validation.
The `?validate=true` query param on POST/PUT returns a `validation` field in the response.

### Agent Validation Workflow

The recommended way for AI agents to get validation feedback during EMU deployment:

#### 1. IaC with Validation (Primary Workflow)

```bash
# Edit EMUs in JSONL
ami emu-plan ./emus/ --validate    # Preview changes + validation status for existing EMUs
ami emu-apply ./emus/ --validate   # Apply + get server-side ASR validation feedback
ami emu-validate -w prod -p api    # On-demand health audit for all workspace EMUs
```

#### 2. SDK with Inline Validation

```python
# Register with inline validation
result = client.register_emu(
    emu_key="welcome-email",
    trigger='state("user.status", "verified")',
    action={"type": "tool_call", "tool": {"tool_id": "mailer"}},
    validate=True,  # Returns validation report in response
)
if result.get("validation"):
    report = result["validation"]
    if not report["passed"]:
        for w in report["warnings"]:
            print(f"  {w['code']}: {w['message']}")
```

#### 3. Warning Code Reference

| Code | Meaning | Agent Action |
|------|---------|-------------|
| `WARN-NEVER-SEEN` | Atom not observed in ASR | Ensure ingestion pipeline emits this atom |
| `WARN-SCHEMA-MISMATCH` | Type/operator incompatibility | Fix trigger operator or atom type |
| `WARN-LOW-REACH` | Atom stale (>7 days) | Verify pipeline is running |
| `WARN-SEMANTIC-EQUIVALENT` | Wrong event name, similar exists | Use suggested correct name |
| `WARN-ACTION-TOOL-NOT-FOUND` | Tool not in executor registry | Register via `ami tool-register` |
| `WARN-ACTION-PLACEHOLDER-NEVER-SEEN` | Action template refs unobserved atom | Ensure atom is emitted |
| `WARN-POLICY-GAP` | Missing cooldown/idempotency | Add policy fields for auto-mode EMUs |

#### 4. Iterative Fix Loop

```
Edit JSONL → ami emu-apply --validate → read warnings → fix JSONL → repeat until clean
```

#### 5. Bulk Health Check

```bash
# Filter failing EMUs in CI/CD
ami emu-validate -w production -p api --json | jq '.reports[] | select(.passed == false)'

# Exit code 1 if any EMU has severity=error (useful for CI gates)
ami emu-validate -w production -p api || echo "Validation errors found"
```

---

## Best Practices

1. **Use context manager**: Always use `async with` for automatic resource cleanup
2. **Enable tracing in development**: Use `trace=True` to debug trigger evaluation
3. **Test with dry_run**: Test triggers without side effects using `dry_run=True`
4. **Handle errors gracefully**: Catch specific exception types
5. **Document ATOM dependencies**: Clearly document what atoms each EMU needs
6. **Validate DSL early**: Validate triggers before registration
7. **Monitor invocation performance**: Track `processing_time_ms` in responses
8. **Use idempotency for critical operations**: Prevent duplicate actions with idempotency keys
9. **Test in shadow mode**: Evaluate new EMUs without executing actions
10. **Version incrementally**: Start with simple triggers, refine iteratively
11. **Use IaC sync workflow**: Prefer `emu-pull/plan/apply` for production deployments
12. **Commit lock files**: Track `.emu.lock.jsonl` in version control for team coordination

---
