"""Shared library for agent-governance hooks. Stdlib only."""

import json
import os
import re
import sys

BUILTIN_AGENTS = frozenset({
    "Bash", "Explore", "Plan", "general-purpose", "Task",
    "code-simplifier", "code-reviewer", "code-explorer", "code-architect",
    "statusline-setup", "claude-code-guide",
})

DEBUG_LOG = "/tmp/agent-governance-debug.log"


def debug_log(msg):
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(DEBUG_LOG, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def is_builtin(agent_type):
    """Check if agent_type is a built-in (skip processing)."""
    if not agent_type:
        return True
    # Handle plugin-prefixed agents like "feature-dev:code-reviewer"
    base = agent_type.split(":")[-1] if ":" in agent_type else agent_type
    return base in BUILTIN_AGENTS


def find_agent_md(agent_type, cwd=None):
    """Find agent .md file. Search order: cwd/.claude/agents/ -> ~/.claude/agents/."""
    # Strip plugin prefix for file lookup
    name = agent_type.split(":")[-1] if ":" in agent_type else agent_type

    candidates = []
    if cwd:
        candidates.append(os.path.join(cwd, ".claude", "agents", f"{name}.md"))
    candidates.append(os.path.expanduser(f"~/.claude/agents/{name}.md"))

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def parse_frontmatter(filepath):
    """Parse YAML-like frontmatter from agent .md file. No pyyaml dependency."""
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except (IOError, OSError):
        return {}

    # Extract frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    fm_text = match.group(1)
    return _parse_yaml_block(fm_text)


def _parse_inline_value(value):
    """Parse an inline YAML value: strings, bools, inline arrays [a, b], numbers."""
    # Inline array: [a, b, c]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_inline_value(item.strip()) for item in inner.split(",")]

    # Quoted string
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]

    # Booleans
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False

    # Numbers
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    return value


def _parse_yaml_block(text):
    """Minimal YAML parser for frontmatter. Handles flat keys, lists, nested blocks."""
    result = {}
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Detect indentation level
        indent = len(line) - len(line.lstrip())

        # Top-level key:value or key: (block)
        kv_match = re.match(r"^(\w[\w_-]*):\s*(.*)", stripped)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip()

            if value:
                result[key] = _parse_inline_value(value)
                i += 1
            else:
                # Block: collect indented lines
                block_lines = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.strip()
                    if not next_stripped:
                        block_lines.append("")
                        i += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= indent:
                        break
                    block_lines.append(next_line)
                    i += 1
                result[key] = _parse_block_content(block_lines, indent + 2)
        else:
            i += 1

    return result


def _parse_block_content(lines, base_indent):
    """Parse indented block content — returns dict or list."""
    if not lines:
        return {}

    # Check if it's a list (first non-empty line starts with -)
    first_real = next((l for l in lines if l.strip()), "")
    if first_real.strip().startswith("- "):
        return _parse_list(lines)

    # Otherwise it's a nested dict
    result = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        indent = len(line) - len(line.lstrip())
        kv_match = re.match(r"^(\w[\w_-]*):\s*(.*)", stripped)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip()
            if value:
                result[key] = _parse_inline_value(value)
                i += 1
            else:
                block_lines = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.strip()
                    if not next_stripped:
                        block_lines.append("")
                        i += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= indent:
                        break
                    block_lines.append(next_line)
                    i += 1
                result[key] = _parse_block_content(block_lines, indent + 2)
        else:
            i += 1

    return result


def _parse_list(lines):
    """Parse a YAML list from indented lines."""
    items = []
    current_item_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current_item_lines:
                items.append(_finalize_list_item(current_item_lines))
            current_item_lines = [stripped[2:].strip()]
        else:
            current_item_lines.append(stripped)

    if current_item_lines:
        items.append(_finalize_list_item(current_item_lines))
    return items


def _finalize_list_item(lines):
    """Finalize a list item — returns string or dict."""
    if len(lines) == 1:
        return _parse_inline_value(lines[0])

    # Multi-line → parse as dict
    return _parse_yaml_block("\n".join(lines))


def get_contract(agent_type, cwd=None):
    """Get contract from agent definition. Returns (contract_dict, agent_md_path) or (None, None)."""
    md_path = find_agent_md(agent_type, cwd)
    if not md_path:
        return None, None

    fm = parse_frontmatter(md_path)
    if not fm:
        return None, md_path

    contract = fm.get("contract")
    if not contract:
        # Check contract_ref
        ref = fm.get("contract_ref")
        if ref:
            ref_path = ref if os.path.isabs(ref) else os.path.join(os.path.dirname(md_path), ref)
            if os.path.isfile(ref_path):
                ref_fm = parse_frontmatter(ref_path)
                contract = ref_fm.get("contract") if ref_fm else None
                if not contract:
                    # Try reading as plain YAML-like
                    contract = _parse_yaml_block(open(ref_path).read()) if os.path.isfile(ref_path) else None

    if isinstance(contract, dict):
        return contract, md_path
    return None, md_path


def check_signals(text, signals):
    """Check if text contains expected output signals. Returns (passed, failed) signal lists."""
    if not signals or not text:
        return [], signals or []

    text_lower = text.lower()
    passed = []
    failed = []

    for signal in signals:
        if not isinstance(signal, str):
            continue
        # Extract keywords from signal description (words 4+ chars)
        keywords = [w.lower() for w in re.findall(r'\b\w{4,}\b', signal)]
        if not keywords:
            passed.append(signal)
            continue
        # Signal passes if majority of keywords found
        found = sum(1 for kw in keywords if kw in text_lower)
        if found >= len(keywords) * 0.5:
            passed.append(signal)
        else:
            failed.append(signal)

    return passed, failed


def extract_contract_output(text):
    """Extract JSON from <!-- CONTRACT_OUTPUT {...} --> comment block."""
    if not text:
        return None

    match = re.search(
        r'<!--\s*CONTRACT_OUTPUT\s+(.*?)\s*-->',
        text, re.DOTALL
    )
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def validate_output(data, schema):
    """Validate data against schema. Try jsonschema, fallback to manual check."""
    if not schema or not data:
        return []

    errors = []

    # Try jsonschema if available
    try:
        import jsonschema
        try:
            jsonschema.validate(data, schema)
            return []
        except jsonschema.ValidationError as e:
            return [str(e.message)]
    except ImportError:
        pass

    # Manual fallback: check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Check properties types if specified
    properties = schema.get("properties", {})
    for field, spec in properties.items():
        if field in data and isinstance(spec, dict):
            expected_type = spec.get("type")
            if expected_type == "array" and not isinstance(data[field], list):
                errors.append(f"Field '{field}' should be array, got {type(data[field]).__name__}")
            elif expected_type == "string" and not isinstance(data[field], str):
                errors.append(f"Field '{field}' should be string, got {type(data[field]).__name__}")
            elif expected_type == "object" and not isinstance(data[field], dict):
                errors.append(f"Field '{field}' should be object, got {type(data[field]).__name__}")

    return errors
