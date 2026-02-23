#!/bin/bash
# agent-governance: Install/uninstall hooks to ~/.claude/settings.json
# Installs both SubagentStart and SubagentStop hooks.
# SubagentStart MUST be in settings.json (additionalContext doesn't work from plugin hooks).
# SubagentStop is also installed here as fallback (local plugin discovery is unreliable).
# Usage: setup.sh [--uninstall]
set -euo pipefail

SETTINGS="$HOME/.claude/settings.json"
PLUGIN_DIR="$HOME/.claude/plugins/agent-governance"

install_hooks() {
    python3 -c "
import json, sys, os

settings_path = os.path.expanduser('$SETTINGS')
plugin_dir = '$PLUGIN_DIR'

hooks_to_install = [
    ('SubagentStart', f'python3 {plugin_dir}/hooks/agent-audit.py'),
    ('SubagentStop',  f'python3 {plugin_dir}/hooks/contract-validate.py'),
]

# Load or create settings
if os.path.isfile(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

hooks = settings.setdefault('hooks', {})
installed = []

for event, cmd in hooks_to_install:
    event_hooks = hooks.setdefault(event, [])

    # Check if already installed
    already = False
    for entry in event_hooks:
        for h in entry.get('hooks', []):
            if cmd in h.get('command', ''):
                already = True
                break
        if already:
            break

    if already:
        print(f'  {event}: already installed')
    else:
        event_hooks.append({
            'matcher': '',
            'hooks': [{'type': 'command', 'command': cmd}]
        })
        installed.append(event)
        print(f'  {event}: installed')

if installed:
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')
    print(f'agent-governance: {len(installed)} hook(s) written to settings.json')
else:
    print('agent-governance: all hooks already installed')
"
}

uninstall_hooks() {
    python3 -c "
import json, sys, os

settings_path = os.path.expanduser('$SETTINGS')
plugin_dir = '$PLUGIN_DIR'
marker = 'agent-governance'

if not os.path.isfile(settings_path):
    print('agent-governance: settings.json not found, nothing to uninstall')
    sys.exit(0)

with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.get('hooks', {})
removed_count = 0

for event in list(hooks.keys()):
    event_hooks = hooks[event]
    new_hooks = []
    for entry in event_hooks:
        keep = True
        for h in entry.get('hooks', []):
            if marker in h.get('command', ''):
                keep = False
                removed_count += 1
        if keep:
            new_hooks.append(entry)
    if new_hooks:
        hooks[event] = new_hooks
    else:
        del hooks[event]

if removed_count:
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')
    print(f'agent-governance: {removed_count} hook(s) removed from settings.json')
else:
    print('agent-governance: no hooks found, nothing to uninstall')
"
}

case "\${1:-}" in
    --uninstall)
        uninstall_hooks
        ;;
    *)
        install_hooks
        ;;
esac
