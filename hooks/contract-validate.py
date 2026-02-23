#!/usr/bin/env python3
"""SubagentStop hook: validate agent output against contract.

Runs from plugin hooks.json (SubagentStop).
Checks output signals and structured output if contract defines them.
Warnings to stderr. NEVER exits 2 — that would prevent agent from stopping.
Always exits 0.
"""

import json
import os
import sys

# Add hooks dir to path for lib import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_contract import (
    is_builtin, get_contract, check_signals,
    extract_contract_output, validate_output, debug_log
)


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, IOError):
        sys.exit(0)

    agent_type = input_data.get("agent_type", "")
    last_message = input_data.get("last_assistant_message", "")
    stop_hook_active = input_data.get("stop_hook_active", False)
    cwd = input_data.get("cwd", "")

    debug_log(f"SubagentStop: agent_type={agent_type}, stop_hook_active={stop_hook_active}")

    # Loop prevention
    if stop_hook_active:
        debug_log("  stop_hook_active=true, skipping to prevent loop")
        sys.exit(0)

    if is_builtin(agent_type):
        debug_log(f"  skipping builtin: {agent_type}")
        sys.exit(0)

    contract, md_path = get_contract(agent_type, cwd)

    if not contract:
        debug_log(f"  no contract for: {agent_type}")
        sys.exit(0)

    warnings = []
    output_mode = contract.get("output_mode", "signal")

    # Signal validation
    signals = contract.get("output_signals")
    if signals and isinstance(signals, list):
        passed, failed = check_signals(last_message, signals)
        debug_log(f"  signals: {len(passed)} passed, {len(failed)} failed")
        for sig in failed:
            warnings.append(f"Signal not detected: {sig}")

    # Structured output validation
    if output_mode == "structured":
        data = extract_contract_output(last_message)
        if data is None:
            warnings.append("Structured output expected but no <!-- CONTRACT_OUTPUT --> block found")
        else:
            schema = contract.get("output_schema", {})
            errors = validate_output(data, schema)
            for err in errors:
                warnings.append(f"Schema validation: {err}")

    # Report warnings to stderr (informational only)
    if warnings:
        debug_log(f"  {len(warnings)} warnings for {agent_type}")
        print(f"[agent-governance] Contract warnings for '{agent_type}':", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
    else:
        debug_log(f"  contract satisfied for {agent_type}")

    # ALWAYS exit 0 — never block agent completion
    sys.exit(0)


if __name__ == "__main__":
    main()
