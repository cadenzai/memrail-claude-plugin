# Memrail Claude Code Plugin

Expert system for SOMA AMI (Self-Organizing Memory Architecture — Adaptive Memory Intelligence).

## What's Included

### Skill: `ami` (invoke as `/memrail:ami`)
Complete reference system for EMU design, ATOM builders, trigger DSL, and SDK integration.
- 12 reference documents covering fundamentals through advanced patterns
- Dual SDK coverage: Python (`ami-sdk`) and TypeScript (`@memrail/ami-sdk`)

### Agents
- **topology-scanner** — Discover decision topology of a codebase (read-only analysis)
- **memrail-architect** — Design ATOM schemas, EMU triggers, and execution policies
- **memrail-implementer** — Implement SDK integrations, ATOM builders, event pipelines
- **memrail-validator** — Validate, test, audit, and review AMI integrations

## Installation

```bash
claude --plugin-dir /path/to/memrail-claude-plugin
```

## SDK Support

| Feature | Python (`ami-sdk`) | TypeScript (`@memrail/ami-sdk`) |
|---------|-------------------|-------------------------------|
| AsyncAMIClient | ✅ | ✅ (AMIClient) |
| state/tag/event | ✅ | ✅ |
| atoms_from_dict | ✅ | ✅ (atomsFromDict) |
| StateObject | ✅ | ✅ |
| ToolRegistry | ✅ | ✅ |
| ActionExecutor | ✅ | ✅ |
| CLI (`ami`) | ✅ | ✅ |
