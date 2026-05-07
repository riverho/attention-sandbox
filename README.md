# Attention Sandbox 🛡️

> **Minimal folder sandbox for Pi. A stopper, not a cage.**

When the agent tries to touch something outside the mapped folders, it gets a friendly **"here's what's blocked, here's how to fix it"** message. The agent learns its boundaries and works with them — no wasted tool calls, no hitting walls.

```
Agent (smart): "I need ~/Desktop/. Should I add it to the sandbox?"
User: "yes"
Agent: !MAP ~/Desktop -> allow:rw
       read ~/Desktop/  ✅ Works!

Agent (dumb): read ~/Desktop/  ❌ BLOCKED — waste of a turn
```

---

## The Problem This Solves

Pi gives agents powerful tools (`read`, `bash`, `edit`, `write`). Without boundaries, agents wander into:
- `~/.ssh/` — your private keys
- `~/Desktop/` — your personal files  
- `/etc/passwd` — system files
- Other project directories — cross-contamination

**Without a sandbox:** Agent tries, fails, retries, wastes tokens, confuses user.

**With this sandbox:** Agent knows boundaries, asks before crossing, user stays in control.

---

## Philosophy: Agent-First Design

Most sandboxes are **user-centric** — they just block and notify the user. This one is **agent-centric** — it teaches the agent its boundaries so the agent can **plan around them**.

### How?

1. **Startup context injection**: The agent sees its sandbox boundaries in the system prompt
2. **Proactive behavior**: The agent checks `!STATUS` before trying unknown paths
3. **Conversational expansion**: The agent asks the user to add paths, rather than hitting walls
4. **Clear error messages**: If blocked, the agent knows exactly why and can adapt

---

## Install

```bash
# 1. Link extension
cd /path/to/attention-sandbox
ln -s $(pwd)/extension ~/.pi/agent/extensions/attention-sandbox

# 2. Add map to your project
mkdir -p /your/project/.pi
cp .pi/sandbox-map.yaml /your/project/.pi/sandbox-map.yaml

# 3. (Optional) Add agent instructions
ln -s $(pwd)/.pi/agents.md /your/project/.pi/agents.md

# 4. Reload Pi
/reload
```

---

## Auto-Init for New Folders

When you `cd` into a folder **without** `.pi/sandbox-map.yaml`, the extension auto-detects and creates one:

### Detected as Project

Finds `.git`, `.wenmei`, `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`:

```
[sandbox] Map auto-created:
[sandbox] Created .pi/sandbox-map.yaml
🟢 ~/my-project -> allow:rw (Project root (auto-detected))
🟡 ~/my-project/.git -> allow:ro (Git history read-only)
🔴 ~/my-project/node_modules -> deny (Dependencies)
🟡 ~ -> allow:ro (Parent workspace read-only)
🔴 / -> deny (Outside sandbox)
```

### Detected as Plain Folder

```
[sandbox] Map auto-created:
[sandbox] Created .pi/sandbox-map.yaml
🟢 ~/some-folder -> allow:rw (Current directory)
🟡 ~ -> allow:ro (Parent workspace read-only)
🔴 / -> deny (Outside sandbox)
```

The `.pi/sandbox-map.yaml` is written to disk immediately. Edit it anytime, or use `!MAP` commands.

---

## User Commands

Type these in Pi chat:

| Command | What It Does |
|---------|-------------|
| `!MAP <path> -> <perm>` | Add or update a path rule |
| `!UNMAP <path>` | Remove a path rule |
| `!STATUS` | Show current sandbox map |
| `!SANDBOX` | Show help and examples |

### Examples

```
!MAP ~/Desktop -> allow:rw     # Grant access
!MAP ~/.ssh -> deny             # Explicitly block
!MAP /tmp -> ask:rw            # Allow but log
!UNMAP ~/Desktop                # Remove rule
!STATUS                          # See all rules
```

---

## The Map File

`.pi/sandbox-map.yaml`:

```yaml
map:
  ~/projects/my-app:
    perm: allow:rw
    note: "Main project"

  ~/work/shared:
    perm: allow:ro
    note: "Shared assets read-only"

  ~/.ssh:
    perm: deny
    note: "Never"

  /:
    perm: deny
    note: "Everything else blocked"
```

Rules:
- **Longest-prefix wins**: `~/projects/my-app/src` matches `~/projects/my-app` first
- **Default deny**: If no rule matches, it's blocked
- **Write protection**: `allow:ro` zones auto-deny writes

---

## Agent Experience

### At Startup

The agent sees this in its context:

```
📋 SANDBOX BOUNDARIES — You are operating inside a !MAP sandbox.

You may freely access these paths:
  ~/projects/attention-sandbox
  ~/work/shared

Rules:
  1. Before accessing paths outside the map, ASK the user to expand.
  2. Use !MAP <path> -> allow:rw to add paths (user must confirm).
  3. If you hit a sandbox stop, adapt your plan — do not retry blindly.
```

### During Work

**Good agent behavior:**

```
User: "Check my Downloads folder for PDFs"

Agent: "I don't see ~/Downloads in the sandbox. Should I add it?"

User: "yes"

Agent: !MAP ~/Downloads -> allow:rw
       read ~/Downloads/
       (returns file list)
```

**Bad agent behavior (wasted turn):**

```
User: "Check my Downloads folder for PDFs"

Agent: read ~/Downloads/
       🔒 SANDBOX STOP — path not in map
       (wasted tool call, user confused)
```

### When Blocked

If the agent hits a wall:

```
🔒 SANDBOX STOP

The agent tried to read outside the mapped sandbox:
  ~/Desktop/secret.txt

Currently allowed paths:
    ~/projects/attention-sandbox
    ~/work/shared

To expand the sandbox:
  !MAP ~/Desktop -> allow:rw

Or ask the user: "Should I add ~/Desktop to the sandbox?"
```

The agent reads this, adapts, and either:
- Asks the user to expand
- Finds an alternative within mapped paths

---

## Permission Levels

| Permission | Icon | Read | Write | Agent Behavior |
|-----------|------|------|-------|---------------|
| `allow:rw` | 🟢 | ✅ | ✅ | Free flow |
| `allow:ro` | 🟡 | ✅ | ❌ | Read only |
| `ask:rw` | 🔵 | ✅ | ✅ | Allowed, logged for review |
| `ask:ro` | 🔵 | ✅ | ❌ | Read-only, logged |
| `deny` | 🔴 | ❌ | ❌ | Never touch |

---

## Folder-Centric (wenmei-style)

Any folder can become a sandbox:

1. Drop `.pi/sandbox-map.yaml` in any folder
2. Open that folder in Pi
3. The extension loads the map automatically

No migration. No cage. The sandbox follows the folder.

---

## Files

```
extension/
├── src/
│   └── index.ts          # The stopper + commands (~250 lines)
├── package.json
└── tsconfig.json

.pi/
├── sandbox-map.yaml      # Example map
└── agents.md             # Agent instructions (loaded by Pi)

README.md                 # This file
```

---

## Why No HIL / Pause / Resume?

Pi is minimal. This extension is minimal.

| Feature | Why Not Here |
|---------|-------------|
| Pause/Resume | Pi has no native tool pause. Complex to hack. |
| Key prompts (1/2/3) | Pi's TUI is streaming. Single-keystroke interrupts are non-native. |
| Overlay UI | Heavy extension work. Not minimal. |
| **Stop + Explain + Agent Context** | ✅ Native. Agent adapts. User sees. Simple. |

---

## Audit Trail

If `.wenmei/` exists in the working directory, stops are logged:

```jsonl
{"ts":"2026-05-07T14:30:00Z","kind":"sandbox.stop","tool":"read","path":"~/Desktop/secret.txt","reason":"outside-map"}
```

Best-effort logging. No crash if `.wenmei` doesn't exist.

---

## License

MIT

---

*Built for Pi. Built for minimal. Built for wenmei. Built for smart agents.*