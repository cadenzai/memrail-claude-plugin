# Decision Topology

**Understanding the AMI Decision Plane Architecture**

## Table of Contents

- [What is Decision Topology?](#what-is-decision-topology)
- [The Decision Plane](#the-decision-plane)
- [Identifying Decision Points](#identifying-decision-points)
- [Decision Topology Patterns](#decision-topology-patterns)
- [Bounded Complexity](#bounded-complexity)
- [Mapping Your Topology](#mapping-your-topology)

---

## What is Decision Topology?

**AMI is a decision plane, not just a rules engine.**

As systems grow, decisions become scattered across codebases: if-statements in controllers, feature flags in configs, ML models in services, business rules in databases. This creates **decision sprawl** - an untraceable web of conditional logic.

AMI introduces **decision topology**: a structured map of all decision points in your system, centralized through invoke hooks.

### Why This Matters

| Problem | Without AMI | With AMI Decision Plane |
|---------|-------------|------------------------|
| **Decision sprawl** | Logic scattered across files | Centralized in EMU registry |
| **Auditability** | "Why did X happen?" is hard | Full trace of every decision |
| **Complexity growth** | O(n²) interactions | O(n) bounded by invoke points |
| **Change management** | Fear of side effects | Isolated EMU updates with versioning |
| **AI agent control** | Unpredictable behavior | Deterministic guardrails |

---

## The Decision Plane

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         YOUR APPLICATION                                 │
│                                                                          │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐             │
│   │ Request │    │  Agent  │    │  Cron   │    │ Webhook │             │
│   │ Handler │    │  Loop   │    │  Job    │    │ Handler │             │
│   └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘             │
│        │              │              │              │                   │
│        └──────────────┴──────────────┴──────────────┘                   │
│                              │                                          │
│                              ▼                                          │
│                    ┌─────────────────┐                                  │
│                    │  INVOKE HOOK    │  ◄── Decision Point              │
│                    │  (AMI Client)   │                                  │
│                    └────────┬────────┘                                  │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AMI DECISION PLANE                                  │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         EMU REGISTRY                             │   │
│   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │   │
│   │  │ EMU #1  │  │ EMU #2  │  │ EMU #3  │  │ EMU #N  │   ...      │   │
│   │  │ trigger │  │ trigger │  │ trigger │  │ trigger │            │   │
│   │  │ action  │  │ action  │  │ action  │  │ action  │            │   │
│   │  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    ARBITRATION ENGINE                            │   │
│   │  • Evaluate all triggers against context atoms                   │   │
│   │  • Score by expected_utility × confidence                        │   │
│   │  • Apply exclusion groups, cooldowns, idempotency                │   │
│   │  • Return ranked action set                                      │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Identifying Decision Points

A **decision point** is any place in your code where behavior changes based on context.

### Before: Scattered Decisions

```python
class RequestHandler:
    async def handle(self, request):
        user = get_user(request)

        # Decision 1: Feature flag (buried in code)
        if feature_flags.get("new_checkout") and user.tier == "premium":
            return new_checkout_flow(request)

        # Decision 2: A/B test (different system)
        if ab_test.get_variant(user.id, "pricing") == "B":
            prices = experimental_prices

        # Decision 3: Business rule (hard to find)
        if user.failed_payments > 3 and user.tier != "enterprise":
            return PaymentRequiredResponse()

        # Decision 4: ML-driven (opaque)
        if fraud_model.predict(request) > 0.8:
            return FraudBlockResponse()
```

### After: Centralized Decision Plane

```python
class RequestHandler:
    async def handle(self, request):
        user = get_user(request)

        # Single decision point - all logic in EMUs
        response = await ami.decide(context=[
            state("user.id", user.id),
            state("user.tier", user.tier),
            state("user.failed_payments", user.failed_payments),
            state("request.path", request.path),
            tag("fraud_score", fraud_model.predict(request)),
        ])

        # Execute returned actions
        for action in response.selected:
            result = await execute_action(action)
            if result.terminal:
                return result.response

        # Default flow
        return standard_checkout_flow(request)
```

---

## Decision Topology Patterns

### Pattern 1: Request Gate

Every incoming request passes through a decision gate:

```python
@app.middleware("http")
async def ami_decision_gate(request, call_next):
    # Invoke AMI at request boundary
    decisions = await ami.decide(context=extract_request_context(request))

    # Check for blocking decisions
    for d in decisions.selected:
        if d.action.get("type") == "route" and d.action.get("terminal"):
            return create_response(d.action)

    # Attach non-blocking decisions for downstream use
    request.state.ami_context = decisions
    return await call_next(request)
```

**Use cases**: Auth checks, rate limiting, A/B routing, fraud detection

### Pattern 2: Agent Loop Hook

AI agents invoke AMI at each reasoning step:

```python
class AMIGuidedAgent:
    async def step(self, observation):
        # Invoke at each agent step
        guidance = await ami.decide(context=[
            state("agent.step", self.step_count),
            state("agent.task", self.current_task),
            state("observation.type", observation.type),
            tag("intent", self.classify_intent(observation)),
        ])

        # Apply context directives to prompt
        system_additions = [
            d.action["directive"]
            for d in guidance.selected
            if d.action["type"] == "context_directive"
        ]

        # Execute tool_call actions directly (bypass LLM)
        for d in guidance.selected:
            if d.action["type"] == "tool_call":
                await self.execute_tool(d.action["tool"])

        # LLM generates next action with AMI guidance
        return await self.llm.generate(
            system=self.base_prompt + "\n".join(system_additions),
            context=observation
        )
```

**Use cases**: Agent guardrails, context injection, automatic tool execution

### Pattern 3: Event-Driven Decisions

React to events with decision evaluation:

```python
@event_handler("order.placed.*")
async def on_order_placed(event):
    # Invoke with event context
    decisions = await ami.decide(context=[
        state("order.total", event.data["total"]),
        state("customer.tier", event.data["customer_tier"]),
        state("customer.lifetime_value", event.data["ltv"]),
    ])

    # Execute post-order actions
    for d in decisions.selected:
        await execute_action(d)
```

**Use cases**: Post-purchase flows, notification triggers, analytics

### Pattern 4: Scheduled Evaluation

Periodic batch evaluation:

```python
@scheduler.cron("0 9 * * *")  # Daily at 9am
async def daily_customer_health_check():
    customers = await get_active_customers()

    for customer in customers:
        decisions = await ami.decide(context=[
            state("customer.id", customer.id),
            state("customer.last_activity_days", customer.days_since_active),
            state("customer.health_score", customer.health_score),
        ])

        for d in decisions.selected:
            await execute_action(d)
```

**Use cases**: Churn prevention, engagement campaigns, health monitoring

---

## Bounded Complexity

The key insight: **complexity becomes tractable when anchored to decision points**.

```
System Complexity = f(Decision Points × EMUs per Point × Interactions)
```

With AMI:
- **Decision Points**: Explicitly identified via invoke hooks
- **EMUs per Point**: Visible in registry, scoped by project
- **Interactions**: Managed via exclusion groups, priorities, cooldowns

This transforms exponential complexity growth into linear growth bounded by your invoke topology.

---

## Mapping Your Topology

### Step 1: Audit Decision Points

Search for conditionals, feature flags, A/B tests in your codebase.

### Step 2: Categorize by Type

| Type | Examples |
|------|----------|
| Request gates | API handlers, middleware, webhooks |
| Agent loops | AI agent steps, chatbot turns |
| Event handlers | Message queues, webhooks, pub/sub |
| Scheduled jobs | Cron jobs, batch processors |

### Step 3: Document with Template

```yaml
decision_topology:
  request_gates:
    - path: /api/checkout
      invoke_point: checkout_handler.decide()
      atoms_provided: [user.*, cart.*, payment.*]
      emu_count: 12

    - path: /api/support/*
      invoke_point: support_middleware.gate()
      atoms_provided: [ticket.*, customer.*, agent.*]
      emu_count: 8

  agent_loops:
    - agent: customer_service_bot
      invoke_point: agent.step()
      atoms_provided: [conversation.*, intent.*, sentiment.*]
      emu_count: 15

  event_handlers:
    - event: order.placed.*
      invoke_point: order_reactor.decide()
      atoms_provided: [order.*, customer.*]
      emu_count: 6
```

### Step 4: Prioritize by Impact

1. High-traffic paths first
2. Revenue-critical flows
3. Customer-facing decisions
4. Internal operations

### Step 5: Migrate Incrementally

```
Phase 1: Instrument events → Observability
Phase 2: Add state atoms → Richer triggers
Phase 3: Simple EMUs → context_directive first
Phase 4: Full automation → tool_call with executors
```

---

## Best Practices

1. **Start with observability**: Emit events before writing EMUs
2. **One invoke per decision category**: Don't scatter invoke calls
3. **Document atom contracts**: What atoms does each invoke point provide?
4. **Use project scoping**: Group related EMUs in projects
5. **Monitor topology health**: Track EMU coverage per decision point

---

**See Also**:
- [07-action-connectivity.md](07-action-connectivity.md) - Action connectivity stratification
- [08-static-analysis.md](08-static-analysis.md) - Completeness checking
