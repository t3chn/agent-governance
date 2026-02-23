#!/usr/bin/env python3
"""SubagentStart hook: inject contract context into agents.

Installed to ~/.claude/settings.json via setup.sh (not plugin hooks.json,
due to bug #16538 — additionalContext doesn't work from plugin hooks).

Reads agent_type from stdin JSON, finds agent .md, parses contract,
builds additionalContext with expectations and output format instructions.
Always exits 0.
"""

import json
import os
import sys

# Add hooks dir to path for lib import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_contract import is_builtin, get_contract, debug_log


def build_context(contract, agent_type):
    """Build additionalContext string from contract."""
    parts = ["[agent-governance] Contract active for this agent."]

    # Expectations
    expects = contract.get("expects")
    if expects and isinstance(expects, list):
        parts.append("\nExpected inputs:")
        for item in expects:
            if isinstance(item, dict):
                for k, v in item.items():
                    parts.append(f"  - {k}: {v}")
            elif isinstance(item, str):
                parts.append(f"  - {item}")

    # Output mode
    output_mode = contract.get("output_mode", "signal")

    # Output signals
    signals = contract.get("output_signals")
    if signals and isinstance(signals, list):
        parts.append("\nYour output MUST satisfy these signals:")
        for s in signals:
            parts.append(f"  - {s}")

    # Structured output instructions
    if output_mode == "structured":
        schema = contract.get("output_schema", {})
        required = schema.get("required", [])
        parts.append("\nOutput mode: STRUCTURED")
        parts.append("You MUST include a JSON block in your response using this format:")
        parts.append("<!-- CONTRACT_OUTPUT {\"key\": \"value\", ...} -->")
        if required:
            parts.append(f"Required fields: {', '.join(required)}")

    # Limits
    limits = contract.get("limits")
    if limits and isinstance(limits, dict):
        max_tokens = limits.get("max_tokens")
        if max_tokens:
            parts.append(f"\nAdvisory limit: ~{max_tokens} tokens output.")

    return "\n".join(parts)


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, IOError):
        sys.exit(0)

    agent_type = input_data.get("agent_type", "")
    cwd = input_data.get("cwd", "")
    debug_log(f"SubagentStart: agent_type={agent_type}, cwd={cwd}")

    if is_builtin(agent_type):
        debug_log(f"  skipping builtin: {agent_type}")
        sys.exit(0)

    contract, md_path = get_contract(agent_type, cwd)

    if not md_path:
        debug_log(f"  no agent .md found for: {agent_type}")
        sys.exit(0)

    if not contract:
        debug_log(f"  no contract in: {md_path}")
        sys.exit(0)

    context = build_context(contract, agent_type)
    debug_log(f"  injecting context ({len(context)} chars) for: {agent_type}")

    # Output hookSpecificOutput for SubagentStart
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": context
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
