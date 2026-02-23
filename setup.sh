#!/bin/bash
# agent-governance: Install/uninstall SubagentStart hook to ~/.claude/settings.json
# Usage: setup.sh [--uninstall]
set -euo pipefail

SETTINGS="$HOME/.claude/settings.json"
HOOK_CMD="python3 $HOME/.claude/plugins/agent-governance/hooks/agent-audit.py"
HOOK_EVENT="SubagentStart"

install_hook() {
    python3 -c "
import json, sys, os

settings_path = os.path.expanduser('$SETTINGS')
hook_cmd = '''$HOOK_CMD'''

# Load or create settings
if os.path.isfile(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

# Ensure hooks structure
hooks = settings.setdefault('hooks', {})
event_hooks = hooks.setdefault('$HOOK_EVENT', [])

# Check if already installed
for entry in event_hooks:
    for h in entry.get('hooks', []):
        if hook_cmd in h.get('command', ''):
            print('agent-governance: SubagentStart hook already installed')
            sys.exit(0)

# Add hook
event_hooks.append({
    'matcher': '',
    'hooks': [{'type': 'command', 'command': hook_cmd}]
})

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')

print('agent-governance: SubagentStart hook installed to settings.json')
"
}

uninstall_hook() {
    python3 -c "
import json, sys, os

settings_path = os.path.expanduser('$SETTINGS')
hook_cmd = '''$HOOK_CMD'''

if not os.path.isfile(settings_path):
    print('agent-governance: settings.json not found, nothing to uninstall')
    sys.exit(0)

with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.get('hooks', {})
event_hooks = hooks.get('$HOOK_EVENT', [])

new_hooks = []
removed = False
for entry in event_hooks:
    keep = True
    for h in entry.get('hooks', []):
        if hook_cmd in h.get('command', ''):
            keep = False
            removed = True
    if keep:
        new_hooks.append(entry)

if removed:
    if new_hooks:
        hooks['$HOOK_EVENT'] = new_hooks
    else:
        del hooks['$HOOK_EVENT']
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')
    print('agent-governance: SubagentStart hook removed from settings.json')
else:
    print('agent-governance: SubagentStart hook not found, nothing to uninstall')
"
}

case "${1:-}" in
    --uninstall)
        uninstall_hook
        ;;
    *)
        install_hook
        ;;
esac
