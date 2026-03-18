# SDK Integration (TypeScript)

**Using the TypeScript SDK to Build and Invoke EMUs**

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

- Node.js 18+
- npm, yarn, or pnpm

### Install SDK

```bash
# Using npm
npm install @memrail/ami-sdk

# Using yarn
yarn add @memrail/ami-sdk

# Using pnpm
pnpm add @memrail/ami-sdk
```

### Verify Installation

```typescript
import { AMIClient } from '@memrail/ami-sdk';
console.log('AMI SDK loaded');
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
export AMI_TEAM="your-team-slug"  # Optional - defaults to "default" team
export AMI_WORKSPACE="production"
export AMI_PROJECT="onboarding"
export AMI_BASE_URL="https://api.ami.example.com"  # Optional
```

```typescript
import { AMIClient } from '@memrail/ami-sdk';

// Auto-loads from environment
const client = new AMIClient();
const response = await client.decide({ context: [...] });
```

#### Method 2: Explicit Configuration

```typescript
import { AMIClient } from '@memrail/ami-sdk';

const client = new AMIClient({
    apiKey: "your-api-key",
    org: "your-org-slug",
    team: "your-team-slug",  // Optional - defaults to "default" team
    workspace: "production",
    project: "onboarding",
    baseUrl: "https://api.ami.example.com"
});

const response = await client.decide({ context: [...] });
```

#### Method 3: Configuration Object

```typescript
import { AMIClient, AMIConfig } from '@memrail/ami-sdk';

const config = AMIConfig.create({
    apiKey: "your-api-key",
    org: "your-org",
    team: "your-team",
    workspace: "production",
    project: "onboarding"
});

const client = new AMIClient(config);
const response = await client.decide({ context: [...] });
```

### Default Team Behavior

If you don't specify a team, the API automatically uses the "default" team:

```typescript
// No team specified - uses "default" team automatically
const client = new AMIClient({
    apiKey: "your-api-key",
    org: "your-org-slug"
    // team omitted - defaults to "default"
});
```

### Context Override

Override workspace/project per-call:

```typescript
const client = new AMIClient({ org: "my-org", team: "my-team" });

// Override workspace/project
const response = await client.decide({
    context: [...],
    workspace: "staging",
    project: "test-app"
});
```

## ATOM Builders

ATOMs are typed facts provided to the decision engine.

### State ATOMs

```typescript
import { state } from '@memrail/ami-sdk';

// Simple state
const atoms = [
    state("user.id", "U-123"),
    state("user.tier", "premium"),
    state("user.age", 25),
    state("user.verified", true)
];
```

**Type Support**: `string`, `number`, `boolean`. No complex types — flatten to dot notation.

**Dict Helper** (Recommended for Complex Data):

```typescript
import { atomsFromDict } from '@memrail/ami-sdk';

const user = {
    id: "U-123",
    tier: "premium",
    age: 25,
    verified: true,
    metadata: {
        signup_source: "organic",
        referrer: "google"
    }
};

// Automatically creates: user.id, user.tier, user.age, user.verified, user.metadata.signup_source, etc.
const atoms = atomsFromDict(user, "user");
```

### Tag ATOMs

```typescript
import { tag } from '@memrail/ami-sdk';

const atoms = [
    tag("priority", "high"),
    tag("channel", "email"),
    tag("language", "spanish")
];

// ML-inferred tags
const sentiment = await sentimentClassifier.predict(text);
const atoms = [
    tag("sentiment", sentiment),
    tag("intent", intent),
    tag("category", "billing_issue")
];
```

### Event ATOMs

```typescript
import { event } from '@memrail/ami-sdk';

// Event with timestamp
const atoms = [
    event("agent.sent.email", { ts: new Date() })
];

// Event with attributes
const atoms = [
    event("payment.completed.stripe", {
        ts: new Date(),
        attributes: { amount: 1000, currency: "USD" }
    })
];

// Event with anchors
const atoms = [
    event("agent.contacted.customer", {
        ts: new Date(),
        subjectAnchor: ["agent", "AGT-123"],
        objectAnchor: ["customer", "CUST-456"]
    })
];
```

## EMU Management

### JSONL Sync Workflow (Recommended)

EMUs are managed via JSONL files using the IaC sync workflow:

```bash
# Pull existing EMUs from remote
memrail emu-pull ./emus/ -w production -p my-project

# Edit ./emus/emus.jsonl (one EMU per line)

# Preview changes (like terraform plan)
memrail emu-plan ./emus/

# Apply changes to remote
memrail emu-apply ./emus/ --yes
```

### SDK Registration (Scripting/Testing Only)

```typescript
const response = await client.registerEMU({
    emuKey: "welcome_premium_users",
    trigger: "state.user.tier == 'premium'",
    action: {
        type: "tool_call",
        intent: "SEND_WELCOME_EMAIL",
        tool: {
            tool_id: "mailer",
            version: "1.0.0",
            args: { template: "premium_welcome" }
        }
    },
    expectedUtility: 0.9,
    confidence: 0.95,
    intent: "Welcome new premium users",
    decisionPoint: "onboarding-check",
    workspace: "production",
    project: "onboarding"
});
```

### Updating Existing EMUs

```typescript
const response = await client.updateEMU({
    emuKey: "vip_escalation",
    trigger: "state.customer.tier == 'vip' AND state.ticket.priority >= 'high'",
    expectedUtility: 0.95,
    confidence: 0.90,
    policy: {
        mode: "auto",
        priority: 10,
        cooldown: { seconds: 3600, gate: "activation" }
    },
    workspace: "production",
    project: "support"
});
```

### Changing Lifecycle State

```typescript
await client.updateEMULifecycle({
    emuKey: "vip_escalation",
    state: "active",  // draft, shadow, canary, active, archived
    workspace: "production",
    project: "support"
});
```

### Registration with Full Policy

```typescript
const response = await client.registerEMU({
    emuKey: "vip_escalation",
    trigger: "state.customer.tier == 'vip' AND state.ticket.priority == 'high'",
    action: {
        type: "tool_call",
        intent: "ESCALATE_TO_VIP_TEAM",
        tool: {
            tool_id: "zendesk_escalator",
            version: "2.1.0",
            args: { queue: "vip-support", priority: "critical" }
        }
    },
    policy: {
        mode: "auto",
        priority: 9,
        cooldown: { seconds: 7200, gate: "activation" },
        idempotency: { enabled: true, scope: ["customer.id", "ticket.id"] },
        exclusion_groups: ["escalation_actions"]
    },
    expectedUtility: 0.95,
    confidence: 0.88,
    decisionPoint: "triage",
    workspace: "production",
    project: "support"
});
```

### Action Types

#### tool_call

```typescript
const action = {
    type: "tool_call",
    intent: "SEND_EMAIL",
    tool: {
        tool_id: "mailer",
        version: "1.0.0",
        args: { to: "{{user.email}}", template: "welcome" }
    }
};
```

#### decision_prompt

```typescript
const action = {
    type: "decision_prompt",
    message: "High-risk transaction from {{user.id}}. Approve?",
    options: [
        { id: "approve", label: "Approve Transaction" },
        { id: "decline", label: "Decline Transaction" },
        { id: "review", label: "Manual Review" }
    ]
};
```

#### route

```typescript
const action = {
    type: "route",
    destination: "spanish_support_queue",
    metadata: { language: "spanish", priority: "standard" }
};
```

#### context_directive

```typescript
const action = {
    type: "context_directive",
    directive: "Customer is VIP tier. Follow escalation protocol per KB #4521"
};
```

## Invoking the Engine

### Basic Invocation

```typescript
import { AMIClient, state, tag } from '@memrail/ami-sdk';

const client = new AMIClient({ /* config */ });

const response = await client.decide({
    context: [
        state("user.id", "U-123"),
        state("user.tier", "premium"),
        tag("intent", "upgrade")
    ],
    decisionPoint: "onboarding-check",
    workspace: "production",
    project: "onboarding"
});

for (const item of response.selected) {
    console.log(`EMU: ${item.emu_key}`);
    console.log(`Action: ${JSON.stringify(item.action)}`);
    console.log(`Priority: ${item.priority}`);
}
```

### Using Dict Helper for Complex Data

```typescript
import { atomsFromDict, tag } from '@memrail/ami-sdk';

const userData = {
    id: "U-123",
    tier: "premium",
    age: 25,
    verified: true,
    preferences: { language: "en", timezone: "America/New_York" }
};

const ticketData = {
    id: "TICKET-456",
    priority: "high",
    sla_remaining_hours: 2,
    status: "open"
};

const response = await client.decide({
    context: [
        ...atomsFromDict(userData, "user"),
        ...atomsFromDict(ticketData, "ticket"),
        tag("intent", "upgrade"),
        tag("channel", "email")
    ],
    workspace: "production",
    project: "onboarding"
});
```

**What `atomsFromDict` does:**
```typescript
// Input
atomsFromDict({ tier: "premium", age: 25, preferences: { language: "en" } }, "user")

// Output (equivalent to)
[
    state("user.tier", "premium"),
    state("user.age", 25),
    state("user.preferences.language", "en")
]
```

### With Options

```typescript
const response = await client.decide({
    context: [...],
    options: {
        dryRun: true,
        topK: 5,
        explain: true
    },
    workspace: "production",
    project: "onboarding"
});
```

### With Tracing

```typescript
const response = await client.decide({
    context: [...],
    trace: { enable: true, includeAllEmus: true },
    workspace: "production",
    project: "onboarding"
});

if (response.trace) {
    console.log(`Evaluated ${response.trace.evaluatedEmus.length} EMUs`);
    for (const emu of response.trace.evaluatedEmus) {
        console.log(`  ${emu.emuKey}: ${emu.triggerResult}`);
    }
}
```

### With Idempotency

```typescript
const response1 = await client.decide({
    context: [state("order.id", "ORDER-123")],
    idempotencyKey: "order-123-payment",
    workspace: "production",
    project: "checkout"
});

// Second request returns cached response
const response2 = await client.decide({
    context: [state("order.id", "ORDER-123")],
    idempotencyKey: "order-123-payment",
    workspace: "production",
    project: "checkout"
});

if (response2.idempotency?.applied) {
    console.log("Returned cached response");
}
```

### Response Handling

```typescript
const response = await client.decide({ context: [...] });

if (response.selected.length > 0) {
    for (const item of response.selected) {
        switch (item.action.type) {
            case "tool_call":
                await executeTool(item.action.tool);
                break;
            case "decision_prompt":
                await presentDecision(item.action.message, item.action.options);
                break;
            case "route":
                await routeToQueue(item.action.destination);
                break;
            case "context_directive":
                await displayContext(item.action.directive);
                break;
        }
    }
} else {
    console.log("No EMUs fired");
}
```

## Event Ingestion

### Single Event Ingestion

```typescript
await client.emitEvent({
    subject: "agent",
    verb: "sent",
    object: "email",
    ts: new Date(),
    attributes: {
        recipient: "customer@example.com",
        template: "welcome_email"
    },
    anchor: {
        subject: { type: "agent", id: "AGT-123" },
        object: { type: "email", id: "EMAIL-456" }
    },
    workspace: "production",
    project: "support"
});
```

### Batch Event Ingestion

```typescript
await client.emitEvents({
    events: [
        {
            subject: "user", verb: "login", object: "app",
            ts: new Date()
        },
        {
            subject: "user", verb: "clicked", object: "button",
            ts: new Date(),
            attributes: { button_id: "checkout" }
        }
    ],
    workspace: "production",
    project: "analytics"
});
```

## Complete Workflows

### Workflow 1: Support Ticket Automation

```typescript
import { AMIClient, atomsFromDict, tag } from '@memrail/ami-sdk';

async function handleTicketCreated(ticket: any) {
    const client = new AMIClient({ /* config */ });

    // 1. Ingest event
    await client.emitEvent({
        subject: "ticket", verb: "created", object: "zendesk",
        ts: new Date(),
        workspace: "production", project: "support"
    });

    // 2. Build atoms
    const atoms = [
        ...atomsFromDict({
            id: ticket.id, priority: ticket.priority,
            sla_remaining_hours: ticket.slaRemainingHours,
            status: ticket.status
        }, "ticket"),
        ...atomsFromDict({
            id: ticket.customer.id, tier: ticket.customer.tier,
            lifetime_value: ticket.customer.lifetimeValue
        }, "customer"),
        tag("category", ticket.category),
        tag("language", ticket.language)
    ];

    // 3. Invoke decision engine
    const response = await client.decide({
        context: atoms,
        workspace: "production", project: "support"
    });

    // 4. Execute selected actions
    for (const item of response.selected) {
        if (item.action.type === "tool_call") {
            await executeTool(item.action.tool);
        } else if (item.action.type === "route") {
            await routeTicket(ticket.id, item.action.destination);
        }
    }
}
```

## Testing & Debugging

### Dry Run Mode

```typescript
const response = await client.decide({
    context: [...],
    options: { dryRun: true },
    workspace: "production", project: "support"
});

console.log(`Would execute ${response.selected.length} EMUs:`);
for (const item of response.selected) {
    console.log(`  - ${item.emu_key} (priority: ${item.priority})`);
}
```

### Unit Testing (Jest)

```typescript
import { AMIClient, state, tag } from '@memrail/ami-sdk';

describe('VIP Escalation EMU', () => {
    let client: AMIClient;

    beforeAll(() => {
        client = new AMIClient({
            apiKey: process.env.AMI_API_KEY,
            org: "test-org",
            workspace: "test",
            project: "support"
        });
    });

    test('fires for VIP + high priority', async () => {
        const response = await client.decide({
            context: [
                state("customer.tier", "vip"),
                state("ticket.priority", "high")
            ],
            options: { dryRun: true }
        });

        const emuKeys = response.selected.map(item => item.emu_key);
        expect(emuKeys).toContain("support.vip_escalation");
    });

    test('does not fire for standard tier', async () => {
        const response = await client.decide({
            context: [
                state("customer.tier", "standard"),
                state("ticket.priority", "high")
            ],
            options: { dryRun: true }
        });

        const emuKeys = response.selected.map(item => item.emu_key);
        expect(emuKeys).not.toContain("support.vip_escalation");
    });
});
```

## Error Handling

### Common Errors

```typescript
import {
    AMIBadRequest,
    AMINotFound,
    AMIUnauthorized,
    AMIForbidden,
    AMIUnprocessable,
    AMIServerError,
    AMIError
} from '@memrail/ami-sdk';

try {
    await client.registerEMU({
        emuKey: "test_emu",
        trigger: "INVALID DSL SYNTAX",
        // ...
    });
} catch (error) {
    if (error instanceof AMIBadRequest) {
        console.error(`Bad request: ${error.message}`);
    } else if (error instanceof AMINotFound) {
        console.error(`Not found: ${error.message}`);
    } else if (error instanceof AMIUnauthorized) {
        console.error(`Unauthorized: ${error.message}`);
    } else if (error instanceof AMIError) {
        console.error(`AMI error: ${error.message}`);
    }
}
```

### Retry Logic

```typescript
async function decideWithRetry(
    client: AMIClient,
    context: any[],
    maxRetries = 3
): Promise<any> {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            return await client.decide({ context });
        } catch (error) {
            if (error instanceof AMIServerError && attempt < maxRetries - 1) {
                const waitTime = Math.pow(2, attempt) * 1000;
                await new Promise(resolve => setTimeout(resolve, waitTime));
            } else {
                throw error;
            }
        }
    }
}
```

## CLI Commands

The `ami` CLI is shared between both SDKs. See the [Python SDK reference](05-sdk-integration-python.md#cli-commands) for the complete CLI command reference — all commands work identically regardless of which SDK you use.

Key commands:
```bash
memrail emu-pull ./emus/ -w production -p my-project    # Export EMUs
memrail emu-plan ./emus/                                  # Preview changes
memrail emu-apply ./emus/ --yes                           # Apply changes
memrail emu-validate -w prod -p api                       # Validate EMUs
memrail purge-workspace staging --yes                     # Reset workspace
memrail tool-register                                     # Upload tool definitions
```

## Workspace Management

### Purging a Workspace

```bash
# Purge everything
memrail purge-workspace production

# Skip confirmation
memrail purge-workspace staging --yes

# Selective purge
memrail purge-workspace development --targets emus,traces,events --yes
```

**Available targets:** `emus`, `traces`, `events`, `asr`, `tools`, `cooldowns`, `prompts`, `hindsight`, `decision_points`

## EMU Validation Reports

### Single EMU Validation

```typescript
const report = await client.getEMUValidator("welcome-email", {
    workspace: "production"
});

if (!report.passed) {
    for (const w of report.warnings) {
        console.log(`[${w.severity}] ${w.code}: ${w.message}`);
        if (w.remediation) {
            console.log(`  Fix: ${w.remediation}`);
        }
    }
}
```

### Workspace Bulk Validation

```typescript
const result = await client.validateWorkspaceEMUs({
    workspace: "production"
});

console.log(`Validated ${result.total} EMUs`);
for (const item of result.reports) {
    const status = item.report.passed ? "PASS" : "FAIL";
    console.log(`  [${status}] ${item.emu_key} (${item.state})`);
}
```

### Warning Code Reference

| Code | Meaning | Agent Action |
|------|---------|-------------|
| `WARN-NEVER-SEEN` | Atom not observed in ASR | Ensure ingestion pipeline emits this atom |
| `WARN-SCHEMA-MISMATCH` | Type/operator incompatibility | Fix trigger operator or atom type |
| `WARN-LOW-REACH` | Atom stale (>7 days) | Verify pipeline is running |
| `WARN-SEMANTIC-EQUIVALENT` | Wrong event name, similar exists | Use suggested correct name |
| `WARN-ACTION-TOOL-NOT-FOUND` | Tool not in executor registry | Register via `memrail tool-register` |
| `WARN-ACTION-PLACEHOLDER-NEVER-SEEN` | Action template refs unobserved atom | Ensure atom is emitted |
| `WARN-POLICY-GAP` | Missing cooldown/idempotency | Add policy fields for auto-mode EMUs |

---

## Best Practices

1. **No context manager needed**: Unlike Python, TypeScript client doesn't require `async with` — just construct and use
2. **Enable tracing in development**: Use `trace: { enable: true }` to debug trigger evaluation
3. **Test with dryRun**: Test triggers without side effects using `options: { dryRun: true }`
4. **Handle errors with instanceof**: Use specific error classes for targeted error handling
5. **Document ATOM dependencies**: Clearly document what atoms each EMU needs
6. **Use IaC sync workflow**: Prefer `emu-pull/plan/apply` for production deployments
7. **Commit lock files**: Track `.emu.lock.jsonl` in version control
8. **Use atomsFromDict**: Cleaner than manual state() calls for complex objects
9. **Test in shadow mode**: Evaluate new EMUs without executing actions
10. **Monitor performance**: Track `processing_time_ms` in responses

---
