---
name: agent-contracts
description: Use when creating or reviewing agent definitions that participate in multi-agent workflows, when you need to add handoff contracts to agents, or when debugging agent output validation failures.
---

# Agent Contracts

Contracts define what an agent expects as input and what it must produce as output. They live in the agent's frontmatter and are enforced by the `agent-governance` plugin hooks.

## Contract Format

### Minimal (signal mode)

```yaml
---
name: my-reviewer
description: Reviews code for issues
tools: [Read, Grep, Glob]
contract:
  version: "1.0"
  expects:
    - target_path: "path to review"
  output_signals:
    - "contains findings or states no issues"
    - "includes file paths with line numbers"
  limits:
    max_tokens: 30000
---
```

Signal mode checks that the agent's output contains keywords from each signal description. No structured output required — the agent writes naturally.

### Full (structured mode)

```yaml
---
name: my-analyzer
description: Analyzes codebase architecture
tools: [Read, Grep, Glob, Bash]
contract:
  version: "1.0"
  output_mode: structured
  expects:
    - target_path: "directory to analyze"
    - analysis_scope: "full|focused|quick"
  output_schema:
    required: [findings, severity_summary]
    properties:
      findings:
        type: array
        items:
          required: [file, severity, description]
      severity_summary:
        type: object
  output_signals:
    - "includes severity assessment"
  limits:
    max_tokens: 50000
---
```

Structured mode tells the agent to include a JSON envelope in its output:

```
<!-- CONTRACT_OUTPUT {"findings": [...], "severity_summary": {...}} -->
```

The envelope is validated against `output_schema`. Signal checks also run.

## Key Fields

| Field | Required | Description |
|-------|----------|-------------|
| `version` | Yes | Always `"1.0"` |
| `expects` | No | List of expected input parameters (documented for callers) |
| `output_signals` | No | Natural language descriptions of expected output characteristics |
| `output_mode` | No | `"signal"` (default) or `"structured"` |
| `output_schema` | No | JSON Schema-like validation for structured mode |
| `limits.max_tokens` | No | Advisory token limit for agent output |

## Writing Good Signals

Signals are checked via keyword extraction. Use specific, descriptive phrases:

**Good signals:**
- `"contains severity assessment with critical/high/medium/low ratings"`
- `"includes specific file paths and line numbers for each finding"`
- `"provides actionable recommendations for each issue"`

**Bad signals (too vague):**
- `"has output"` — matches anything
- `"is good"` — no extractable keywords
- `"ok"` — too short

Rule of thumb: each signal should contain 2+ words of 4+ characters that would appear in the expected output.

## External Contract Files

For complex contracts, use `contract_ref` to point to a separate file:

```yaml
---
name: my-agent
contract_ref: ./contracts/reviewer-contract.md
---
```

The referenced file should contain frontmatter with a `contract:` block.

## Setup

The plugin has two hooks:
- **SubagentStop** (via plugin hooks.json) — validates output automatically
- **SubagentStart** (requires settings.json) — injects contract context into agents

Install the SubagentStart hook:
```bash
bash ~/.claude/plugins/agent-governance/setup.sh
```

Uninstall:
```bash
bash ~/.claude/plugins/agent-governance/setup.sh --uninstall
```

## Debugging

Check `/tmp/agent-governance-debug.log` for hook execution details.

Common issues:
- **No validation running**: Ensure plugin is enabled and setup.sh was run
- **Signals always fail**: Check that signal descriptions contain specific keywords (4+ chars)
- **Structured output not found**: Agent must include `<!-- CONTRACT_OUTPUT {...} -->` in its response
