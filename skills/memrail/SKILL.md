---
name: ami
description: Expert guidance on Memrail's SOMA AMI including EMU (Executable Memory Unit) design, ATOM (state/tag/event) builders, trigger DSL syntax, event ingestion, Python and TypeScript SDK integration, and trigger reachability analysis. Use when working with Memrail AMI, EMU configurations, deterministic decision systems, event-driven workflows, or when implementing memory-augmented agent systems.
metadata:
  author: memrail
  version: "2.0"
compatibility: Works with Python 3.8+ (ami-sdk) and Node.js 18+ (@memrail/ami-sdk). Designed for Claude Code and similar agents.
---

# Memrail SOMA AMI Expert Skill

A deterministic decision engine for automated systems. The core abstraction is the **EMU (Executable Memory Unit)** — a conditional action that fires deterministically when its trigger expression evaluates to TRUE.

**Three atom types drive all decisions:**
- **State atoms** — Structured facts (`state.user.tier`, `state.ticket.priority`)
- **Tag atoms** — Classifications, often ML-inferred (`tag.sentiment`, `tag.intent`)
- **Event atoms** — Timestamped occurrences (`event.user.login.success IN 'PT24H'`)

## Key Principles

### Determinism
Same inputs => Same outputs. No randomness in decision-making.
- Triggers are boolean expressions that always evaluate the same way
- ML is used ONLY for classification/tagging, not for decisions
- LLM outputs must be constrained to fixed taxonomies (Pydantic Literal types in Python, Zod enums in TypeScript)

### Trigger Reachability
A trigger can only fire if ALL required ATOMs are present at invoke time.
- Missing state/tag atoms => trigger evaluates to FALSE
- No matching events => event queries return FALSE

### Project Coherence (CRITICAL)
**The project is the unit of coherence.** EMUs and their referenced tools MUST be in the same project.
- EMU referencing unavailable tool = connectivity failure (EMU never fires)
- Always validate tool availability before EMU registration

### Event-Driven Architecture
Events are ingested separately and queried during trigger evaluation.
- Events stored for 90 days by default
- Use `event.subject.verb.object IN 'duration'` syntax
- Always emit events after material actions (critical for self-improvement)

## Quick Trigger Syntax

```javascript
state.user.tier == 'premium'                              // State equality
state.user.tier IN ['gold', 'platinum']                    // Set membership
event.agent.sent.email IN 'PT24H'                          // Event recency
COUNT event.user.failed.login IN 'PT10M' >= 5              // Event counting
event.order.shipped WHERE order_id == 'ord-456' IN 'P7D'   // Attribute filter
state.user.email ENDS_WITH '@company.com'                  // String operations
state.code MATCHES '^[A-Z]{3}-\d{4}$'                     // Regex match
```

Operators must be UPPERCASE (`AND`, `OR`, `NOT`, `IN`, `EXISTS`, `CONTAINS`, `MATCHES`).
Keys must be lowercase with 2+ dot segments (`state.user.tier`, not `state.test`).

## Reference Index

Load these files on demand based on the task phase. Organized by typical project lifecycle.

### Phase 1: Bootstrap & Architecture

Read [references/05-sdk-integration-python.md](references/05-sdk-integration-python.md) (Python) or [references/05b-sdk-integration-typescript.md](references/05b-sdk-integration-typescript.md) (TypeScript) when bootstrapping a new project — SDK installation, client configuration, API key setup, environment variables, org/workspace/project hierarchy. Also covers ATOM builders, invocation patterns, event ingestion, workspace purging, and error handling.

Read [references/06-decision-topology.md](references/06-decision-topology.md) when designing integration architecture — identifying decision points in your application, choosing topology patterns (request gate, agent loop, event-driven), or mapping atom contracts across invoke points.

Read [references/07-action-connectivity.md](references/07-action-connectivity.md) when planning which action types to use, performing gap analysis before deployment, or building the action connectivity matrix for your system.

### Phase 2: Design & Write EMUs

Read [references/01-emu-fundamentals.md](references/01-emu-fundamentals.md) when designing EMU structure, choosing action types (tool_call, decision_prompt, route, context_directive), configuring execution policies (mode, priority, cooldown, idempotency), or managing EMU lifecycle states.

Read [references/02-dsl-reference.md](references/02-dsl-reference.md) when writing or debugging trigger expressions, using advanced DSL features (WHERE clauses, string operations, cross-project queries), or looking up operator syntax and duration formats.

Read [references/04-emu-cookbook.md](references/04-emu-cookbook.md) when looking for real-world EMU examples, domain-specific patterns (support, sales, operations), or complete automation suite templates.

Read [references/11-emu-design-heuristics.md](references/11-emu-design-heuristics.md) when choosing between state-first vs event-based design, evaluating EMU complexity, or reviewing production-ready checklists and anti-patterns.

### Phase 3: Register & Deploy

Read [references/12-emu-jsonl-workflow.md](references/12-emu-jsonl-workflow.md) when creating, modifying, or deploying production EMUs. **This is the ONLY recommended workflow for production.** Covers `emu-pull/plan/apply` IaC sync, JSONL format, CI/CD integration, and lock file management. Never use SDK `register_emu()` for production EMUs.

Read [references/05-sdk-integration-python.md](references/05-sdk-integration-python.md) (Python) or [references/05b-sdk-integration-typescript.md](references/05b-sdk-integration-typescript.md) (TypeScript) § "Agent Validation Workflow" when deploying EMUs and needing validation feedback. Use `memrail emu-apply --validate` for inline validation or `memrail emu-validate` for on-demand health checks.

Read [references/09-tool-registry-executors.md](references/09-tool-registry-executors.md) when registering tools via CLI, setting up ToolRegistry, ActionExecutor, shadow/canary mode execution, circuit breakers, rate limiting, or metrics collection.

### Phase 4: Test & Debug

Read [references/03-trigger-reachability.md](references/03-trigger-reachability.md) when an EMU isn't firing as expected, debugging missing ATOM dependencies, analyzing ML inference dependencies, or validating that ATOM builders provide all required keys.

Read [references/05-sdk-integration-python.md](references/05-sdk-integration-python.md) (Python) or [references/05b-sdk-integration-typescript.md](references/05b-sdk-integration-typescript.md) (TypeScript) § "Workspace Management" when purging a workspace for dev/testing resets. Use `memrail purge-workspace <workspace> --yes` (or `--targets emus,traces,events` for selective purge). Requires org-level API key.

Read [references/08-static-analysis.md](references/08-static-analysis.md) when validating decision plane completeness, setting up CI/CD integration for completeness checks, or running the automated analysis script.

### Phase 5: LLM-Generated EMUs

Read [references/10-llm-integration-guide.md](references/10-llm-integration-guide.md) when an LLM needs to generate or validate EMUs — covers EMU generation templates, validation checklists, common mistakes, and TypeScript/HTTP API integration.

Read [references/11-emu-design-heuristics.md](references/11-emu-design-heuristics.md) for production-ready checklist, complexity ladder (Level 1-5), and common anti-patterns to avoid in generated EMUs.

## Task Procedures

### Designing an EMU
1. Identify the use case and business rule
2. Determine ATOM dependencies (state/tag/event)
3. Write trigger expression using modern DSL syntax
4. Choose action type and configure policy
5. Validate reachability — ensure all ATOMs will be provided
6. Start in shadow mode, promote after testing

### Deploying EMUs (IaC Workflow)
1. `memrail emu-pull ./emus/ -w production -p my-project`
2. Edit `./emus/emus.jsonl` (one EMU per line)
3. `memrail emu-plan ./emus/ --validate` — preview changes + validation
4. `memrail emu-apply ./emus/ --yes --validate` — sync + validate
5. Fix any validation warnings, re-apply if needed
6. Commit both `emus.jsonl` and `.emu.lock.jsonl` to git

### Debugging an EMU
1. Enable tracing: `trace=TraceOptions(enable=True)`
2. Test with `dry_run=True` to isolate trigger logic
3. Extract ATOM dependencies from trigger DSL
4. Verify all state/tag atoms are provided at invoke time
5. Query event history to confirm events exist with correct names
6. Check event names match ingestion convention: `subject.verb.object`
7. Run `memrail emu-validate -w <ws> -p <proj>` for bulk validation health check
8. Run `memrail emu-apply ./emus/ --validate` to get inline validation after deploy
9. Interpret warning codes and apply remediation suggestions (see references/05-sdk-integration-python.md or references/05b-sdk-integration-typescript.md § "Warning Code Reference")

### SDK Quick Start

**Python:**
```python
from ami import AsyncAMIClient
from ami.atoms import state, tag, atoms_from_dict

async with AsyncAMIClient(
    api_key="your-api-key", org="your-org",
    workspace="production", project="support"
) as client:
    response = await client.decide(context=[
        state("customer.tier", "vip"),
        state("ticket.priority", "high"),
        tag("category", "billing")
    ])
    for item in response.selected:
        await execute_tool(item.action.tool)
```

**TypeScript:**
```typescript
import { AMIClient, state, tag, atomsFromDict } from '@memrail/ami-sdk';

const client = new AMIClient({
    apiKey: "your-api-key", org: "your-org",
    workspace: "production", project: "support"
});

const response = await client.decide({
    context: [
        state("customer.tier", "vip"),
        state("ticket.priority", "high"),
        tag("category", "billing")
    ]
});
for (const item of response.selected) {
    await executeTool(item.action.tool);
}
```

Use `decide(context=...)` (Python) or `decide({ context: [...] })` (TypeScript). Use `atoms_from_dict(data, prefix="user")` / `atomsFromDict(data, "user")` for complex nested data.

## Gotchas

### EMU Registration Rules (API returns 422 if violated)
1. **`tool.version` is REQUIRED** — every `tool_call` must include `"version": "1.0.0"` in the `tool` object
2. **`state` must be lowercase** — `active`, `shadow`, `canary`, `draft`, `inactive`, `archived`
3. **`cooldown` is `{seconds: N, gate: "ack"}`** — never ISO strings. Convert: PT1H=3600, PT48H=172800, P7D=604800
4. **`idempotency` is structured** — `{enabled: true, boundary: "workspace", roles: "auto", scope: [...]}`
5. **Trigger keys need 2+ dot segments** — `state.user.tier` valid, `state.test` invalid
6. **Auth scheme is `AMI-Key`** — not `Bearer`. Header: `Authorization: AMI-Key <key>`
7. **Use `memrail emu-apply` for bulk** — not `memrail register-emu` (single EMUs only)

### Tool Registration Rules (CLI `memrail tool-register`)
1. **`ToolRegistry` must be at module level** — CLI imports module looking for global `registry`
2. **Use `@registry.tool(...)` decorators** — not `@client.tool(...)`
3. **Keep file dependency-free** — no app imports; CLI must import standalone
4. **Tool bodies can be stubs** — use `...` (ellipsis); CLI uploads schema only

### Common Anti-Patterns
- **Random logic in triggers** — use deterministic conditions; ML for classification only
- **Free-form ML tags** — always constrain to fixed taxonomy (`Literal["positive", "negative"]`)
- **Missing ATOM builders** — validate reachability before designing triggers
- **Event name mismatch** — trigger says `event.agent.sent.email` but ingestion uses `event.email.sent.agent`. Convention: `subject.verb.object`
- **No event emission after actions** — breaks self-improvement; always emit events
- **WHERE with state references** — `WHERE attr == state.x` is invalid; use template literals `WHERE attr == '{{state.x}}'`
- **Events beyond retention** — 90-day max; `event.X IN 'P180D'` will never match

## Agent Instructions

### SDK Detection
When starting work on a project, detect which SDK is in use:
- Check `package.json` for `@memrail/ami-sdk` → TypeScript SDK
- Check `pyproject.toml` or `requirements.txt` for `ami-sdk` → Python SDK
- Reference the appropriate SDK documentation accordingly

- Always use modern DSL syntax with dot notation
- Use `decide(context=...)` — the only supported calling convention
- Use `context` (not `context_atoms`) in API request bodies
- Prefer ergonomic event counting: `COUNT event.X IN 'PT1H' > 5`
- Use `decision_point` parameter to name invoke sites for analytics
- Always check trigger reachability before suggesting EMU designs
- Suggest shadow mode testing before production deployment
- Validate project coherence — EMUs and their tools must be in the same project
- Reference specific files from the Reference Index above when detailed guidance is needed

---

**Version**: AMI v2 (Modern DSL with dot notation, IaC Sync)
**Last Updated**: 2026-03-18
