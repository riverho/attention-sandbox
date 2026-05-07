# Attention Sandbox 🛡️

> **A folder sandbox for Pi that teaches the agent its boundaries — so it asks before it wanders.**

When the agent tries to touch something outside the mapped folders, it gets a friendly **"here's what's blocked, here's how to fix it"** message. The agent learns its boundaries and works with them — no wasted tool calls, no hitting walls.

```
Agent (smart): "I need ~/Desktop/. Should I add it to the sandbox?"
User: "yes"
Agent: !MAP ~/Desktop -> allow:rw
       read ~/Desktop/  ✅ Works!

Agent (dumb): read ~/Desktop/  ❌ BLOCKED — waste of a turn
```

---

## Why Use This?

**Three reasons:**

### 1. Agent-First Boundaries (No Wasted Turns)

Most sandboxes just **block** and tell the user. This one **teaches the agent** so the agent plans around boundaries:

- At startup, the agent sees its sandbox map in context
- Before touching unknown paths, it checks `!STATUS` or asks you
- When blocked, it adapts instead of retrying blindly

**Result:** Fewer wasted tool calls, fewer confusing errors, smoother sessions.

### 2. Multi-Path Summary (See Everything At Once)

When an agent command touches multiple paths, you see **all blocked paths in one message** — not one error per path:

```
🔒 SANDBOX STOP

The agent tried bash on 3 paths outside the sandbox:
  • ~/Desktop        (not in map)
  • ~/Downloads      (not in map)
  • /etc/passwd     (denied: default deny)

Currently allowed:
  • ~/projects/my-app
  • ~/work/shared

To expand:
  !MAP ~/Desktop -> allow:rw
  !MAP ~/Downloads -> allow:rw

Or ask: "Should I add these to the sandbox: ~/Desktop, ~/Downloads?"
```

**Result:** You decide once, add multiple paths, agent continues.

### 3. Auto-Init (Zero Config)

Drop into any folder — the sandbox auto-detects the project and creates `.pi/sandbox-map.yaml`:

| What It Finds | What It Maps |
|---------------|-------------|
| `.git`, `package.json`, etc. | Project root = `allow:rw` |
| `node_modules/`, `.venv/` | Dependencies = `deny` (don't touch) |
| `.git/` | Git history = `allow:ro` |
| Parent directory | Read-only (peek but don't touch) |
| Everything else | Denied by default |

**Result:** Open any project, sandbox is ready in seconds. No manual setup.

---

## The Problem This Solves

Pi gives agents powerful tools (`read`, `bash`, `edit`, `write`). Without boundaries, agents wander into:

- `~/.ssh/` — your private keys
- `~/Desktop/` — your personal files
- `/etc/passwd` — system files
- Other project directories — cross-contamination
- Dependency folders — modifying `node_modules`

**Without a sandbox:** Agent tries, fails, retries, wastes tokens, confuses you.

**With this sandbox:** Agent knows boundaries, asks before crossing, you stay in control.

---

## Philosophy: Agent-First Design

Most sandboxes are **user-centric** — they just block and notify the user. This one is **agent-centric** — it teaches the agent its boundaries so the agent can **plan around them**.

### How?

1. **Startup context injection**: The agent sees its sandbox boundaries in the system prompt
2. **Proactive behavior**: The agent checks `!STATUS` before trying unknown paths
3. **Conversational expansion**: The agent asks the user to add paths, rather than hitting walls
4. **Clear error messages**: If blocked, the agent knows exactly why and can adapt
5. **Bulk suggestions**: When multiple paths are blocked, all are shown with `!MAP` commands ready

---

## Install

```bash
# 1. Link extension
cd /path/to/attention-sandbox
ln -s $(pwd)/extension ~/.pi/agent/extensions/attention-sandbox

# 2. Reload Pi
/reload
```

That's it. The extension auto-detects your project and creates `.pi/sandbox-map.yaml`.

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

### When Blocked (Multi-Path)

If the agent hits multiple walls at once:

```
🔒 SANDBOX STOP

The agent tried to bash on 3 path(s) outside the sandbox:
  • ~/Desktop        (not in map)
  • ~/Downloads      (not in map)
  • /etc/passwd     (denied: default deny)

Currently allowed paths:
    ~/projects/attention-sandbox
    ~/work/shared

To expand the sandbox, add the paths you want to allow:
  !MAP ~/Desktop -> allow:rw
  !MAP ~/Downloads -> allow:rw

Or ask: "Should I add these paths to the sandbox: ~/Desktop, ~/Downloads?"
```

The agent reads this, adapts, and either:
- Asks you to expand (you can approve multiple at once)
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
