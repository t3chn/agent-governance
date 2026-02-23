# agent-governance

Handoff contracts and tool auditing for Claude Code multi-agent workflows.

## Problem

When multiple agents collaborate, there's no way to enforce what an agent should produce or verify it delivered. Agents get vague instructions and return unpredictable output.

## Solution

Add a `contract:` block to agent frontmatter. Two hooks enforce it:

- **SubagentStart** — injects contract expectations into the agent's context
- **SubagentStop** — validates output against contract signals and schema

## Contract format

```yaml
---
name: code-reviewer
description: Reviews code for issues
tools: [Read, Grep, Glob]
contract:
  version: "1.0"
  expects:
    - target_path: "path to review"
  output_signals:
    - "contains findings with severity levels"
    - "includes specific file paths and line numbers"
  limits:
    max_tokens: 30000
---
```

### Signal mode (default)

Output signals are natural language descriptions of expected output. The hook checks for keyword presence — no structured format required.

### Structured mode

For machine-readable output, set `output_mode: structured` and define `output_schema`. The agent includes a JSON envelope:

```
<!-- CONTRACT_OUTPUT {"findings": [...], "summary": "..."} -->
```

The hook validates required fields and types.

## Install

```bash
# Clone
git clone https://github.com/vitaly/agent-governance.git ~/.claude/plugins/agent-governance

# Install SubagentStart hook to settings.json (required — plugin hooks can't inject context due to bug #16538)
bash ~/.claude/plugins/agent-governance/setup.sh
```

Enable the plugin in Claude Code settings.

## Uninstall

```bash
bash ~/.claude/plugins/agent-governance/setup.sh --uninstall
```

## Structure

```
.claude-plugin/plugin.json     Plugin manifest
hooks/hooks.json               SubagentStop hook (runs from plugin)
hooks/lib_contract.py          Shared library (stdlib only)
hooks/agent-audit.py           SubagentStart hook (installed to settings.json)
hooks/contract-validate.py     SubagentStop hook (runs from plugin)
skills/agent-contracts/        Documentation skill
setup.sh                       Install/uninstall SubagentStart hook
```

## How it works

1. Agent spawned → `agent-audit.py` finds its `.md` file → parses `contract:` → injects expectations via `additionalContext`
2. Agent finishes → `contract-validate.py` checks output signals (keyword match) and structured output (schema validation)
3. Warnings go to stderr. Hooks never block agent completion (always exit 0).

Built-in agents (Bash, Explore, Plan, etc.) are skipped automatically.

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

## License

MIT
