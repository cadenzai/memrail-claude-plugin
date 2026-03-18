# Memrail Claude Code Plugin

Expert system for Memrail SOMA AMI - decision infrastructure for automated systems.

## What's Included

### Skill: `memrail` (invoke as `/memrail:memrail`)
Complete reference system for EMU design, ATOM builders, trigger DSL, and SDK integration.
- 12 reference documents covering fundamentals through advanced patterns
- Dual SDK coverage: Python (`memrail`) and TypeScript (`@memrail/sdk`)

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

| Feature | Python (`memrail`) | TypeScript (`@memrail/sdk`) |
|---------|-------------------|-------------------------------|
| AsyncAMIClient | ✅ | ✅ (AMIClient) |
| state/tag/event | ✅ | ✅ |
| atoms_from_dict | ✅ | ✅ (atomsFromDict) |
| StateObject | ✅ | ✅ |
| ToolRegistry | ✅ | ✅ |
| ActionExecutor | ✅ | ✅ |
| CLI (`ami`) | ✅ | ✅ |
