# Action Connectivity

**Ensuring Your Actions Can Actually Execute**

## Table of Contents

- [What is Action Connectivity?](#what-is-action-connectivity)
- [The Connectivity Spectrum](#the-connectivity-spectrum)
- [Action Connectivity Matrix](#action-connectivity-matrix)
- [Planning for Greenfield Applications](#planning-for-greenfield-applications)
- [Gap Analysis](#gap-analysis)
- [Visual Topology with Connectivity](#visual-topology-with-connectivity)

---

## What is Action Connectivity?

**Trigger reachability** asks: "Can this EMU fire?" (are the atoms available?)

**Action connectivity** asks: "If this EMU fires, can we execute the action?" (do we have the infrastructure?)

An EMU with a connected trigger but unconnected action is useless - it will fire but nothing will happen.

---

## The Connectivity Spectrum

Actions exist on a spectrum from "always connected" to "requires infrastructure":

```
REACHABILITY SPECTRUM

Always Reachable                                    Requires Infrastructure
      │                                                        │
      ▼                                                        ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  context_   │    │  decision_  │    │    route    │    │  tool_call  │
│  directive  │    │   prompt    │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
  "Inject into      "Present to       "Route to          "Execute
   LLM prompt"       human via UI"     queue/handler"     external API"
      │                  │                  │                  │
  Requires:          Requires:          Requires:          Requires:
  - LLM integration  - UI component     - Queue system     - Executor mapping
  - Prompt template  - Handler logic    - Handler registry - API clients
                                                           - Error handling
                                                           - Retry logic
```

### Action Type Requirements

| Action Type | Minimum Requirements | Complexity |
|-------------|---------------------|------------|
| `context_directive` | LLM integration, prompt builder | Low |
| `decision_prompt` | UI/Slack handler, human workflow | Medium |
| `route` | Queue system, destination handlers | Medium |
| `tool_call` | Tool registry, executors, API clients | High |

---

## Action Connectivity Matrix

Document your action connectivity before implementation:

```yaml
action_connectivity:
  # Tier 1: Always available (start here)
  context_directive:
    status: connected
    integration_point: system_prompt_builder
    implementation: |
      for item in response.selected:
          if item.action["type"] == "context_directive":
              system_prompt += f"\n[AMI]: {item.action['directive']}"
    gaps: none

  # Tier 2: Requires UI/handler
  decision_prompt:
    status: partially_connected
    integration_point: operator_dashboard
    implementation: slack_interactive_message OR web_modal
    gaps:
      - No mobile app support yet
      - Async decisions not handled

  # Tier 3: Requires routing infrastructure
  route:
    status: connected
    integration_point: message_queue
    implementation: |
      ROUTE_HANDLERS = {
          "queue.vip": vip_queue.enqueue,
          "queue.spanish": spanish_queue.enqueue,
          "escalation.tier2": tier2_handler.escalate,
      }
    gaps:
      - queue.billing not implemented
      - No dead-letter handling

  # Tier 4: Requires full executor ecosystem
  tool_call:
    status: partially_connected
    integration_point: tool_executor_registry
    tools:
      mailer:
        status: connected
        executor: sendgrid_client.send
        rate_limit: 100/min
      slack:
        status: connected
        executor: slack_sdk.post_message
        rate_limit: 50/min
      zendesk:
        status: planned
        executor: null
        blocked_by: "API credentials pending"
      escalator:
        status: connected
        executor: internal_escalation_service.escalate
    gaps:
      - zendesk integration blocked
      - No unified error reporting
```

---

## Planning for Greenfield Applications

When designing a new application with AMI, plan your action connectivity upfront:

### Phase 1: Observability Foundation
```
├── Instrument events at key points
├── Add state atoms to invoke calls
└── Deploy with context_directive EMUs only
    └── Action Connectivity: context_directive ✓
```

**Example EMUs**:
```python
# Safe to deploy immediately - just injects context into LLM
{
    "emu_key": "vip-context",
    "trigger": "state.customer.tier == 'vip'",
    "action": {
        "type": "context_directive",
        "directive": "This is a VIP customer. Prioritize their request."
    }
}
```

### Phase 2: Human-in-the-Loop
```
├── Add decision_prompt handler (Slack/UI)
├── Create require_human EMUs for complex decisions
└── Build operator dashboard
    └── Action Connectivity: context_directive ✓, decision_prompt ✓
```

**Example EMUs**:
```python
{
    "emu_key": "complex-triage",
    "trigger": "tag.complexity == 'high' AND state.ticket.value > 10000",
    "action": {
        "type": "decision_prompt",
        "message": "High-value complex ticket. How to proceed?",
        "options": [
            {"id": "escalate", "label": "Escalate to Senior"},
            {"id": "discount", "label": "Offer 20% Discount"},
            {"id": "standard", "label": "Standard Process"}
        ]
    }
}
```

### Phase 3: Routing Infrastructure
```
├── Implement queue handlers
├── Add route EMUs for ticket/request routing
└── Build routing observability
    └── Action Connectivity: context_directive ✓, decision_prompt ✓, route ✓
```

**Example EMUs**:
```python
{
    "emu_key": "spanish-routing",
    "trigger": "tag.language == 'spanish'",
    "action": {
        "type": "route",
        "destination": "queue.spanish-support",
        "metadata": {"reason": "language_detected"}
    }
}
```

### Phase 4: Full Automation
```
├── Build tool executor registry
├── Implement API clients with retry/circuit-breaker
├── Add tool_call EMUs with proper safeguards
└── Monitor and tune
    └── Action Connectivity: ALL ✓
```

**Example EMUs**:
```python
{
    "emu_key": "auto-escalation",
    "trigger": "state.customer.tier == 'vip' AND state.ticket.priority == 'high'",
    "action": {
        "type": "tool_call",
        "intent": "ESCALATE_TICKET",
        "tool": {
            "tool_id": "zendesk_escalator",
            "args": {"queue": "vip-support", "priority": "urgent"}
        }
    },
    "policy": {
        "cooldown": {"seconds": 3600, "gate": "ack"},
        "idempotency": {"enabled": True, "scope": ["ticket.id"]}
    }
}
```

---

## Gap Analysis

### Identifying Unconnected Actions

```python
def analyze_emu_connectivity(emus: list, reachability: dict) -> dict:
    """
    Analyze which EMUs are blocked by action connectivity gaps.
    """
    analysis = {
        "connected": [],
        "blocked": [],
        "partially_blocked": []
    }

    for emu in emus:
        action_type = emu["action"]["type"]
        action_status = reachability.get(action_type, {})

        if action_status.get("status") == "connected":
            # For tool_call, also check specific tool
            if action_type == "tool_call":
                tool_id = emu["action"]["tool"]["tool_id"]
                tool_status = action_status.get("tools", {}).get(tool_id, {})
                if tool_status.get("status") != "connected":
                    analysis["blocked"].append({
                        "emu_key": emu["emu_key"],
                        "reason": f"tool '{tool_id}' not implemented",
                        "blocked_by": tool_status.get("blocked_by")
                    })
                    continue

            analysis["connected"].append(emu["emu_key"])
        else:
            analysis["blocked"].append({
                "emu_key": emu["emu_key"],
                "reason": f"action type '{action_type}' not connected",
                "gaps": action_status.get("gaps", [])
            })

    return analysis
```

### Common Gap Patterns

| Gap | Symptom | Fix |
|-----|---------|-----|
| Missing executor | `tool_call` EMU fires, nothing happens | Register tool in ToolRegistry |
| Missing route handler | `route` EMU fires, message lost | Implement destination handler |
| No UI for decision_prompt | Human decisions pile up | Build Slack/web handler |
| API credentials missing | Executor throws auth error | Configure credentials |
| Rate limit exceeded | Actions fail intermittently | Add rate limiting config |

---

## Visual Topology with Connectivity

Combine decision topology with action connectivity:

```
DECISION PLANE TOPOLOGY WITH REACHABILITY

┌─────────────────────────────────────────────────────────────────────────────┐
│  INVOKE POINT: /api/support/tickets                                          │
│  Atoms: [ticket.*, customer.*, agent.*]                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  EMUs at this decision point:                                                │
│                                                                              │
│  ┌─────────────────────┬────────────────────┬─────────────────────────────┐ │
│  │ EMU Key             │ Action Type        │ Connectivity                │ │
│  ├─────────────────────┼────────────────────┼─────────────────────────────┤ │
│  │ vip-context         │ context_directive  │ ✓ REACHABLE                 │ │
│  │ spanish-routing     │ route              │ ✓ REACHABLE                 │ │
│  │ sla-escalation      │ tool_call:escalator│ ✓ REACHABLE                 │ │
│  │ survey-trigger      │ tool_call:surveyor │ ✗ BLOCKED (API pending)     │ │
│  │ complex-triage      │ decision_prompt    │ ⚠ PARTIAL (no mobile)       │ │
│  └─────────────────────┴────────────────────┴─────────────────────────────┘ │
│                                                                              │
│  Coverage: 3/5 EMUs fully connected (60%)                                    │
│  Blocked by: surveyor API, mobile decision_prompt                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Integration Examples

### context_directive Integration

```python
# Always connected if using LLM
system_prompt = "You are a helpful assistant."

for item in response.selected:
    if item.action["type"] == "context_directive":
        system_prompt += f"\n\n[AMI Guidance]: {item.action['directive']}"

# Pass to LLM
llm_response = await llm.generate(system_prompt=system_prompt, ...)
```

### tool_call Integration

```python
from memrail.tools import ToolRegistry, ActionExecutor

# Register executors
registry = ToolRegistry()

@registry.tool(name="mailer", description="Send emails", schema={...})
async def send_email(to: str, subject: str, body: str):
    await sendgrid.send(to=to, subject=subject, body=body)
    return {"sent": True}

@registry.tool(name="slack", description="Post to Slack", schema={...})
async def post_slack(channel: str, message: str):
    await slack_client.post(channel=channel, text=message)
    return {"posted": True}

# Execute actions
executor = ActionExecutor(registry=registry)

for item in response.selected:
    if item.action["type"] == "tool_call":
        result = await executor.execute(item)
        if result.success:
            await client.ack(item.activation_id, "acknowledged")
```

### route Integration

```python
ROUTE_HANDLERS = {
    "queue.vip": lambda item: vip_queue.enqueue(item),
    "queue.spanish": lambda item: spanish_queue.enqueue(item),
    "escalation.tier2": lambda item: escalate_to_tier2(item),
}

for item in response.selected:
    if item.action["type"] == "route":
        destination = item.action["destination"]
        handler = ROUTE_HANDLERS.get(destination)

        if handler:
            await handler(item)
        else:
            logger.warning(f"No handler for route: {destination}")
```

### decision_prompt Integration

```python
# Slack integration example
for item in response.selected:
    if item.action["type"] == "decision_prompt":
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": item.action["message"]}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": opt["label"]},
                 "action_id": f"ami_decision_{item.activation_id}_{opt['id']}"}
                for opt in item.action["options"]
            ]}
        ]
        await slack.post_message(channel="#decisions", blocks=blocks)
```

---

## Best Practices

1. **Start with context_directive**: Always connected, immediate value
2. **Document tool requirements**: API keys, rate limits, schemas
3. **Plan before building**: Map action connectivity matrix first
4. **Monitor blocked EMUs**: Alert when EMUs fire but can't execute
5. **Version executors**: Match tool versions in EMU actions

---

**See Also**:
- [06-decision-topology.md](06-decision-topology.md) - Decision plane architecture
- [09-tool-registry-executors.md](09-tool-registry-executors.md) - Full executor ecosystem
