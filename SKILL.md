---
name: attention-sandbox
description: Minimal folder sandbox for Pi with !MAP-based permission control. Auto-detects project boundaries and creates `.pi/sandbox-map.yaml` in new folders. Stops agent from accessing unmapped paths with a friendly note explaining how to expand. Agent-first design teaches the agent to ask before hitting walls. Use when working across multiple directories, handling sensitive files, or keeping agents within project boundaries.
license: MIT
metadata:
  version: "1.0.0"
  author: "wenmei"
  repository: "https://github.com/yourusername/attention-sandbox"
  tags: ["security", "sandbox", "filesystem", "hil", "permissions"]
---

# Attention Sandbox

A logical sandbox for Pi (and other agents). No chroot. No containers. Just intent.

## What It Does

- **!MAP**: Declarative path → permission mapping (allow:rw, allow:ro, ask:rw, ask:ro, deny)
- **Agentic Reach**: The agent *can* try to reach anywhere — the sandbox intercepts and enforces
- **HIL Gate**: Human-in-the-loop pause when hitting `ask` rules or unmapped territory
- **Folder-Centric**: Drop `.wenmei/` or use `!MAP` anywhere on your filesystem — no migration needed
- **Openclaw-Grade Security**: Ports symlink guards, realpath verification, and path boundary checks from openclaw's fs-safe.ts

## When to Use This Skill

Use this skill when:

- Working with files across multiple project directories in one session
- Handling sensitive paths (SSH keys, credentials, personal documents)
- The agent needs freedom to explore but human oversight for risky operations
- You want different permission levels for different agent roles
- You're building a folder-centric workspace system (like wenmei)
- You want recoverable deletions (`trash/` > `rm`)

## Quick Start

### 1. Install Dependencies

```bash
pip install pyyaml
```

### 2. Try the REPL

```bash
python -m sandbox.repl --map maps/default.yaml
```

Inside the REPL:
```
!MAP /Users/river/Desktop -> ask:rw
!STATUS
read README.md
bash ls -la /
```

### 3. Use in Agent Code

```python
from sandbox import SandboxMap, SandboxInterceptor, HILApprover, get_all_tools, Permission, Rule

# Load or build a map
smap = SandboxMap.from_yaml("maps/default.yaml")

# Or add rules dynamically
smap.add(Rule(path="/project/src", perm=Permission.ALLOW_RW))
smap.add(Rule(path="/project/secrets", perm=Permission.ASK_RO))
smap.add(Rule(path="~/.ssh", perm=Permission.DENY))

# Create interceptor
hil = HILApprover()
interceptor = SandboxInterceptor(smap, hil, get_all_tools())

# Every tool call now goes through the map
result = interceptor.call("read", {"path": "/etc/passwd"})
# result.hil_id -> HIL paused, human must approve
```

## !MAP Syntax

### YAML Maps (static)

```yaml
# maps/dev.yaml
map:
  /Users/river/projects/my-app:
    perm: allow:rw
    note: "Main project"

  /Users/river/.ssh:
    perm: deny
    note: "Never"

  /:
    perm: ask:ro
    note: "Catch-all: ask before roaming"
```

### DSL (dynamic, in REPL or agent)

```
!MAP /some/path -> allow:rw  # free access
!MAP /other/path -> ask:ro   # HIL pause on read
!MAP /secret -> deny         # blocked
!UNMAP /some/path            # remove rule
```

## Permission Levels

| Permission | Read | Write | Behavior |
|-----------|------|-------|----------|
| `allow:rw` | ✅ | ✅ | Autonomous |
| `allow:ro` | ✅ | ❌ | Read-only, autonomous |
| `ask:rw` | ✅ | ✅ | HIL pause, then can write |
| `ask:ro` | ✅ | ❌ | HIL pause, read-only |
| `deny` | ❌ | ❌ | Blocked immediately |

## HIL Approval Scopes

When HIL triggers, the human can respond:

- `once` — Allow this single call only
- `session` — Allow this path for current session
- `persistent` — Update the map permanently

## Security Model

This sandbox uses **layered boundaries**:

```
┌─────────────────────────────────────────┐
│  OS / Kernel / User permissions         │  ← Ultimate hard boundary
├─────────────────────────────────────────┤
│  !MAP Soft Boundary                     │  ← Contextual, role-based
│  - allow / ask / deny per path          │
├─────────────────────────────────────────┤
│  Path Safety (from openclaw fs-safe)    │  ← Symlink/hardlink guards
│  - realpath() canonicalization          │
│  - O_NOFOLLOW-style checks              │
│  - is_path_inside() boundary verify     │
│  - Atomic writes with temp + verify     │
├─────────────────────────────────────────┤
│  Wenmei Folder Services                 │  ← Session, journal, trash
│  - .wenmei/journal.jsonl                │
│  - .wenmei/trash/                       │
│  - .wenmei/pi-sessions/                 │
└─────────────────────────────────────────┘
```

## Integration with Pi

This skill is designed to integrate with Pi's tool system. When loaded, Pi knows to:

1. **Check paths before tool calls**: The interceptor wraps `read`, `bash`, `edit`, `write`, `mcp`
2. **Surface HIL requests**: When `ask` is hit, Pi presents the HIL prompt to the user
3. **Respect denials**: `deny` rules return clear errors so Pi can adapt its plan
4. **Update maps dynamically**: Pi can use `!MAP` commands to expand its sandbox as needed

### Example Pi Integration

```python
# In your Pi extension or agent runner
from sandbox import SandboxMap, SandboxInterceptor, HILApprover, get_all_tools

class SandboxedPiRunner:
    def __init__(self, cwd: str):
        # Auto-map the current working directory
        self.map = SandboxMap()
        self.map.add(Rule(path=cwd, perm=Permission.ALLOW_RW))
        self.map.add(Rule(path="/", perm=Permission.ASK_RO))
        
        self.hil = HILApprover()
        self.interceptor = SandboxInterceptor(self.map, self.hil, get_all_tools())
    
    def run_tool(self, name: str, args: dict) -> dict:
        result = self.interceptor.call(name, args)
        if result.hil_id:
            # Surface to Pi UI for human approval
            return {"status": "hil_pending", "hil_id": result.hil_id, "reason": result.error}
        if result.allowed:
            return {"status": "ok", "data": result.data}
        return {"status": "denied", "error": result.error}
```

## Files

```
attention-sandbox/
├── SKILL.md              # This file — skill instructions for Pi
├── README.md             # Human documentation
├── sandbox/              # Python package
│   ├── __init__.py
│   ├── core.py           # !MAP engine + path safety (openclaw-grade)
│   ├── hil.py            # Human-in-the-loop approval queue
│   ├── interceptor.py    # Tool call gatekeeper
│   ├── tools.py          # Real tool implementations
│   └── repl.py           # Interactive sandbox shell
├── maps/                 # Example permission maps
│   └── default.yaml
└── scripts/              # Setup helpers
    └── install.sh
```

## Tips for Using with Pi

1. **Start restrictive, expand as needed**: Begin with `allow` for cwd and `ask` for everything else. Let the agent prove it needs access.

2. **Use session approval for exploration**: When the agent hits an `ask` boundary during research, approve with `session` scope so it can continue without repeated pauses.

3. **Persistent approval for recurring projects**: When working with the same project repeatedly, use `persistent` scope to add it to the map permanently.

4. **Audit with the journal**: Check `.wenmei/journal.jsonl` (or the HIL history) to see what the agent tried to access.

5. **Trash > rm**: The sandbox's `trash/` directory ensures recoverable deletion. Pi should prefer trashing over permanent deletion.

## Troubleshooting

**"outside-workspace" errors**: The path safety layer blocked a symlink escape or path traversal. Verify the path is within a mapped boundary and not a symlink pointing outside.

**HIL not triggering**: Check that the path matches an `ask` rule. Remember that `deny` takes precedence, and longer path prefixes win.

**Permission not updating**: Remember to use `interceptor.resume(hil_id, scope)` with `persistent` scope to permanently update the map.

## License

MIT — See repository for full license.
