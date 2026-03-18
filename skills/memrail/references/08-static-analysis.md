# Static Analysis & Completeness

**Verifying Decision Plane Integration Before Deployment**

## Table of Contents

- [Overview](#overview)
- [The Completeness Model](#the-completeness-model)
- [Analysis Layers](#analysis-layers)
- [Static Analyzer Script](#static-analyzer-script)
- [CI/CD Integration](#cicd-integration)
- [Completeness Dashboard](#completeness-dashboard)
- [Troubleshooting](#troubleshooting)

---

## Overview

A well-integrated decision plane can be **statically analyzed** to verify completeness before deployment. This analysis maps connections between:

1. **Invoke points** in your codebase
2. **Atom emissions** (state, tag, event)
3. **EMU triggers** and their dependencies
4. **Action handlers** (executors, routes, prompts)

**Goal**: Ensure every EMU can fire (trigger atoms exist) and every action can execute (handlers exist).

---

## The Completeness Model

```
DECISION PLANE INTEGRATION COMPLETENESS MODEL

┌─────────────────────────────────────────────────────────────────────────────┐
│                        STATIC ANALYSIS LAYERS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Layer 1: INVOKE TOPOLOGY                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Where are invoke() calls in the codebase?                        │    │
│  │  • What atoms are provided at each invoke point?                    │    │
│  │  • Which projects/workspaces are targeted?                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              ▼                                               │
│  Layer 2: ATOM EMISSION                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • What state atoms are constructed in code?                        │    │
│  │  • What events are emitted via emit_event()?                        │    │
│  │  • What tags are produced by classifiers?                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              ▼                                               │
│  Layer 3: TRIGGER REACHABILITY                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Do EMU triggers reference atoms that are actually emitted?       │    │
│  │  • Are time windows feasible given event retention?                 │    │
│  │  • Are there unreachable triggers (dead EMUs)?                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              ▼                                               │
│  Layer 4: ACTION CONNECTIVITY                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Are executors defined for all tool_call actions?                 │    │
│  │  • Are route destinations handled?                                  │    │
│  │  • Are decision_prompt handlers in place?                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  COMPLETE SYSTEM: All layers fully connected                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Completeness Equation

A decision plane integration is **complete** when:

```
For every EMU E in the registry:
  1. TRIGGER_REACHABLE(E): All atoms in E.trigger are emitted by the application
  2. ACTION_CONNECTED(E): E.action has a corresponding executor
  3. INVOKE_COVERED(E): At least one invoke point provides E's required atoms
```

---

## Analysis Layers

### Layer 1: Invoke Topology

Scan codebase for `invoke()` calls:

```yaml
invoke_points:
  - id: "checkout_handler"
    file: "src/handlers/checkout.py:45"
    atoms_provided:
      state: [user.id, user.tier, cart.total, cart.item_count]
      tags: [intent, fraud_score]
      events: []
    target_project: "ecommerce"
    call_frequency: "~10k/day"

  - id: "support_agent_loop"
    file: "src/agents/support.py:112"
    atoms_provided:
      state: [ticket.id, ticket.priority, customer.tier, agent.id]
      tags: [sentiment, intent, language]
      events: []
    target_project: "support"
    call_frequency: "~5k/day"
```

### Layer 2: Atom Emission

Track what atoms your code produces:

```yaml
emitted_atoms:
  state_atoms:
    - key: "user.id"
      emitted_at: ["checkout_handler", "auth_middleware"]
      type: "string"

    - key: "user.tier"
      emitted_at: ["checkout_handler", "user_service"]
      type: "string"
      values: ["free", "premium", "enterprise"]

  events:
    - topic: "user.logged.in"
      emitted_at: ["auth_service.py:78"]
      frequency: "~2k/day"

    - topic: "order.placed.successfully"
      emitted_at: ["checkout_handler.py:234"]
      frequency: "~500/day"

  tags:
    - kind: "sentiment"
      produced_by: "sentiment_classifier"
      values: ["positive", "neutral", "negative"]

    - kind: "intent"
      produced_by: "intent_classifier"
      values: ["purchase", "support", "upgrade", "cancel"]
```

### Layer 3: Trigger Reachability Analysis

```yaml
trigger_analysis:
  total_emus: 25
  fully_reachable: 21
  partially_reachable: 3
  unreachable: 1

  issues:
    - emu_key: "legacy.old_escalation"
      issue: "UNREACHABLE"
      reason: "Trigger references state.ticket.legacy_id which is never emitted"
      recommendation: "Archive EMU or update trigger to use state.ticket.id"

    - emu_key: "analytics.heavy_user"
      issue: "PARTIALLY_REACHABLE"
      reason: "event.user.viewed.page only emitted in web app, not mobile"
      recommendation: "Add event emission to mobile app or scope EMU to web"
```

### Layer 4: Action Connectivity Analysis

```yaml
action_analysis:
  total_actions: 25
  fully_reachable: 20
  blocked: 5

  by_type:
    context_directive:
      count: 10
      reachable: 10
      blocked: 0

    tool_call:
      count: 7
      reachable: 4
      blocked: 3
      blocked_items:
        - emu_key: "support.survey_trigger"
          tool_id: "survey_sender"
          reason: "SurveyMonkey API integration pending"

        - emu_key: "sales.crm_update"
          tool_id: "salesforce"
          reason: "Salesforce credentials not configured"
```

---

## Static Analyzer Script

AMI provides a ready-to-use static analyzer that requires **no LLM** - pure deterministic analysis.

### Installation

```bash
pip install pyyaml httpx  # Optional dependencies
```

### Usage

```bash
# Analyze with EMUs from YAML file
python scripts/analyze_decision_plane.py /path/to/your/project --emus emus.yaml

# Analyze with EMUs from API
python scripts/analyze_decision_plane.py /path/to/your/project \
    --api-url http://localhost:8000 \
    --api-key ami_... \
    --org acme \
    --workspace production \
    --project main

# Output formats
python scripts/analyze_decision_plane.py /path/to/project --emus emus.yaml --format json
python scripts/analyze_decision_plane.py /path/to/project --emus emus.yaml --format yaml
python scripts/analyze_decision_plane.py /path/to/project --emus emus.yaml --format markdown -o report.md
```

### What It Analyzes

1. **Invoke Topology**: Finds all AMI invoke calls via AST parsing (Python) or regex (TypeScript/JavaScript)
2. **Atom Emissions**: Detects all `emit_event()`, `state()`, `tag()` calls and atom constructions
3. **Trigger Reachability**: Parses EMU triggers and checks if all referenced atoms are emitted
4. **Action Connectivity**: Identifies executor patterns (tool registries, HTTP clients) to verify action handlers

### Exit Codes

- `0`: 100% completeness
- `2`: Incomplete integration (gaps detected)

### Implementation

```python
from dataclasses import dataclass
from typing import List, Dict, Set
import re

@dataclass
class CompletenessReport:
    invoke_points: List[dict]
    emitted_atoms: Dict[str, Set[str]]
    registered_emus: List[dict]
    trigger_issues: List[dict]
    action_issues: List[dict]
    completeness_score: float

def analyze_decision_plane_completeness(
    codebase_path: str,
    ami_client
) -> CompletenessReport:
    """
    Static analysis of decision plane integration completeness.
    """

    # 1. Scan codebase for invoke() calls and atom construction
    invoke_points = scan_invoke_points(codebase_path)
    emitted_atoms = scan_emitted_atoms(codebase_path)
    emitted_events = scan_emitted_events(codebase_path)

    # 2. Fetch registered EMUs from API
    registered_emus = ami_client.list_emus(state="active")

    # 3. Analyze trigger reachability
    trigger_issues = []
    for emu in registered_emus:
        referenced_atoms = extract_atoms_from_trigger(emu.trigger)

        for atom in referenced_atoms:
            if atom.startswith("state."):
                if atom not in emitted_atoms["state"]:
                    trigger_issues.append({
                        "emu_key": emu.emu_key,
                        "issue": "UNREACHABLE_ATOM",
                        "atom": atom,
                        "reason": f"State atom '{atom}' never emitted in codebase"
                    })

            elif atom.startswith("event."):
                topic = atom.replace("event.", "").replace(".", "/")
                if topic not in emitted_events:
                    trigger_issues.append({
                        "emu_key": emu.emu_key,
                        "issue": "UNREACHABLE_EVENT",
                        "atom": atom,
                        "reason": f"Event '{topic}' never emitted in codebase"
                    })

    # 4. Analyze action connectivity
    action_issues = []
    executor_registry = load_executor_registry(codebase_path)

    for emu in registered_emus:
        if emu.action.get("type") == "tool_call":
            tool_id = emu.action.get("tool", {}).get("tool_id")
            if tool_id not in executor_registry:
                action_issues.append({
                    "emu_key": emu.emu_key,
                    "issue": "MISSING_EXECUTOR",
                    "tool_id": tool_id,
                    "reason": f"No executor registered for tool '{tool_id}'"
                })

    # 5. Calculate completeness score
    total_emus = len(registered_emus)
    trigger_ok = total_emus - len(set(i["emu_key"] for i in trigger_issues))
    action_ok = total_emus - len(set(i["emu_key"] for i in action_issues))

    trigger_score = trigger_ok / total_emus if total_emus > 0 else 1.0
    action_score = action_ok / total_emus if total_emus > 0 else 1.0
    completeness_score = (trigger_score + action_score) / 2

    return CompletenessReport(
        invoke_points=invoke_points,
        emitted_atoms=emitted_atoms,
        registered_emus=registered_emus,
        trigger_issues=trigger_issues,
        action_issues=action_issues,
        completeness_score=completeness_score
    )


def extract_atoms_from_trigger(trigger: str) -> Set[str]:
    """Extract all atom references from a trigger DSL expression."""
    atoms = set()

    # Match state.x.y patterns
    atoms.update(re.findall(r'state\.[a-z][a-z0-9_.]*', trigger))

    # Match tag.x patterns
    atoms.update(re.findall(r'tag\.[a-z][a-z0-9_]*', trigger))

    # Match event.x.y.z patterns
    atoms.update(re.findall(r'event\.[a-z][a-z0-9_.]*', trigger))

    return atoms
```

---

## CI/CD Integration

Add completeness checks to your deployment pipeline:

### GitHub Actions

```yaml
# .github/workflows/ami-completeness.yml
name: AMI Decision Plane Completeness

on:
  pull_request:
    paths:
      - 'src/**'
      - 'emus/**'

jobs:
  completeness-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pyyaml httpx

      - name: Analyze Decision Plane
        run: |
          python scripts/analyze_completeness.py \
            --codebase ./src \
            --emu-registry ${{ secrets.AMI_API_URL }} \
            --output completeness-report.json

      - name: Check Completeness Threshold
        run: |
          SCORE=$(jq '.completeness_score' completeness-report.json)
          if (( $(echo "$SCORE < 0.90" | bc -l) )); then
            echo "::error::Completeness score $SCORE below threshold 0.90"
            jq '.trigger_issues, .action_issues' completeness-report.json
            exit 1
          fi
          echo "::notice::Completeness score: $SCORE"

      - name: Report Unreachable EMUs
        if: failure()
        run: |
          echo "## Unreachable EMUs" >> $GITHUB_STEP_SUMMARY
          jq -r '.trigger_issues[] | "- \(.emu_key): \(.reason)"' completeness-report.json >> $GITHUB_STEP_SUMMARY
          echo "## Blocked Actions" >> $GITHUB_STEP_SUMMARY
          jq -r '.action_issues[] | "- \(.emu_key): \(.reason)"' completeness-report.json >> $GITHUB_STEP_SUMMARY
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Checking AMI decision plane completeness..."

python scripts/analyze_completeness.py --codebase ./src --emus ./emus --format json > /tmp/completeness.json

SCORE=$(jq '.completeness_score' /tmp/completeness.json)
THRESHOLD=0.90

if (( $(echo "$SCORE < $THRESHOLD" | bc -l) )); then
    echo "ERROR: Completeness score $SCORE below threshold $THRESHOLD"
    echo "Run 'python scripts/analyze_completeness.py --format markdown' for details"
    exit 1
fi

echo "Completeness check passed: $SCORE"
```

---

## Completeness Dashboard

Visualize your decision plane health:

```
DECISION PLANE HEALTH DASHBOARD

┌─────────────────────────────────────────────────────────────────────────────┐
│  OVERALL COMPLETENESS: 85%  [████████████████░░░░]                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LAYER BREAKDOWN:                                                            │
│                                                                              │
│  Invoke Coverage      [████████████████████] 100%  ✓ All EMUs have points   │
│  Trigger Reachability [████████████████░░░░]  84%  ⚠ 4 issues               │
│  Action Connectivity  [████████████████░░░░]  80%  ⚠ 5 blocked              │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  BLOCKING ISSUES:                                                            │
│                                                                              │
│  CRITICAL (blocks production EMUs):                                          │
│     • survey_sender executor missing                                         │
│     • billing_disputes route handler missing                                 │
│                                                                              │
│  HIGH (partial functionality):                                               │
│     • Mobile app missing 3 event emissions                                   │
│     • Language classifier low-confidence fallback needed                     │
│                                                                              │
│  MEDIUM (technical debt):                                                    │
│     • legacy.old_escalation EMU should be archived                           │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  EMU STATUS BY PROJECT:                                                      │
│                                                                              │
│  ecommerce (12 EMUs)   [████████████████████] 100% reachable                │
│  support (8 EMUs)      [████████████████░░░░]  75% reachable  (2 blocked)   │
│  notifications (5 EMUs) [████████████░░░░░░░░]  60% reachable  (2 blocked)   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Low trigger reachability | Atoms referenced but not emitted | Add atom builders or update triggers |
| Low action connectivity | Missing executors | Implement tool handlers |
| Score fluctuates | New EMUs added without infrastructure | Follow phased rollout |
| False positives | Dynamic atom construction | Add static hints or allowlist |

### Best Practices

1. **Run analysis on every PR**: Catch issues before merge
2. **Set escalating thresholds**: Start at 70%, increase to 90% over time
3. **Archive dead EMUs**: Remove unreachable EMUs from registry
4. **Document exceptions**: Some EMUs may intentionally be unreachable (seasonal, etc.)

---

**See Also**:
- [03-trigger-reachability.md](03-trigger-reachability.md) - Trigger dependencies
- [07-action-connectivity.md](07-action-connectivity.md) - Action requirements
