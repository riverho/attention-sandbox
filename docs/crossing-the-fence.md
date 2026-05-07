# What Happens When You Cross the Fence?

This document shows the **exact agent experience** when the sandbox boundary is hit.

## Three Boundary Types

| Zone | Permission | What Happens |
|------|-----------|--------------|
| **Inside** | `allow:rw` / `allow:ro` | Agent flows freely, no interruption |
| **Fence (Ask)** | `ask:rw` / `ask:ro` | **HIL Pause** — agent stops, human must approve |
| **Wall (Deny)** | `deny` | **Instant block** — agent gets error, must adapt |

---

## Scenario 1: Inside Sandbox (Free Flow)

```
Agent: read("README.md")
```

**Result:** ✅ Immediate success

```
Allowed: True
Data: # Attention Sandbox 🛡️
      > Logical filesystem sandbox for agentic AI...
```

The agent doesn't even know the sandbox exists. It just works.

---

## Scenario 2: Hitting the Fence (HIL Pause)

```
Agent: bash("ls ~/Desktop")
```

Where `~/Desktop` has `ask:rw` permission.

**Result:** ⏸️ Execution **PAUSED** — human sees:

```
⏸️  HIL PAUSED: bash on ['/Users/river/Desktop']

╔══════════════════════════════════════════════════════════════════╗
║  🤖 AGENT REQUESTS APPROVAL                                      ║
╠══════════════════════════════════════════════════════════════════╣
║  Tool:     bash                                                  ║
║  Paths:    /Users/river/Desktop                                  ║
║  Reason:   Desktop needs approval                                ║
║  ID:       a1b2c3d4                                              ║
╚══════════════════════════════════════════════════════════════════╝

Options:
  y / yes        — Approve once
  s / session    — Approve for this session
  p / persist    — Approve and add to map permanently
  n / no         — Deny
  ? <msg>        — Ask agent for clarification
```

### If Human Says "yes" (ONCE)

```
→ hil.approve('a1b2c3d4', once)

Result: ✅ Executes once
        Returns directory listing
```

**Next time** the agent touches Desktop → HIL triggers again.

### If Human Says "session" (SESSION)

```
→ hil.approve('a1b2c3d4', session)

Result: ✅ Executes
        Also caches: /Users/river/Desktop → approved for session
```

**Next time** the agent touches Desktop → ✅ **No pause**. Free flow.
**Even nested files** like `~/Desktop/subdir/file.txt` → ✅ Approved (directory covers descendants).

### If Human Says "persist" (PERSISTENT)

```
→ hil.approve('a1b2c3d4', persistent)

Result: ✅ Executes
        Also adds to !MAP:
        /Users/river/Desktop → allow:rw (HIL approved persistent)
```

**Forever after** — Desktop is in the map as `allow:rw`. No more HIL for this path.

### If Human Says "no" (DENY)

```
→ hil.deny('a1b2c3d4')

Result: 🚫 HIL DENIED: bash
```

Agent receives error and must adapt its plan (e.g., "I can't access Desktop, let me try another approach").

---

## Scenario 3: Hitting the Wall (DENY)

```
Agent: bash("cat ~/.ssh/id_rsa")
```

Where `~/.ssh` has `deny` permission.

**Result:** 🚫 **Instant block — no HIL, no pause**

```
🚫 SANDBOX DENIED: bash on /Users/river/.ssh/id_rsa
   Rule: Never
```

The agent cannot ask for approval. It cannot negotiate. The wall is absolute.

---

## Scenario 4: Write Protection on Read-Only

```
Agent: write("/etc/passwd", "hacked content")
```

Where `/etc` has `ask:ro` (read-only, ask first).

**Result:** 🚫 **Auto-denied** — no HIL needed

```
🚫 SANDBOX DENIED: write on /etc/passwd
   Rule: Write denied: Ask before roaming
```

Even if the human previously approved **reading** `/etc/passwd`, writing is a different permission and is denied at the map level. No HIL pause for writes on read-only zones.

---

## The Full Flow Diagram

```
Agent Tool Call
      │
      ▼
┌─────────────┐
│  Extract    │  ← Parse paths from read/bash/edit/write/mcp
│   Paths     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Check !MAP │  ← Longest-prefix match
└──────┬──────┘
       │
   ┌───┴───┐
   ▼       ▼       ▼
 allow   ask      deny
   │       │        │
   ▼       ▼        ▼
  ✅     ⏸️       🚫
execute  HIL      block
         pause    (no appeal)
          │
      ┌───┴───┐
      ▼       ▼
    approve  deny
      │        │
      ▼        ▼
     ✅       🚫
   execute   agent
             adapts
```

---

## What Pi Sees

When this is a Pi skill, Pi receives the `SandboxResult` and acts accordingly:

| Result | Pi Behavior |
|--------|-------------|
| `allowed=True` | Normal tool execution, result goes to context |
| `allowed=False, hil_id=""` | Error in context, Pi adapts plan |
| `allowed=False, hil_id="abc123"` | Pi **stops**, surfaces HIL prompt to user, waits |

After HIL resolution:
- Approved → Pi resumes with result
- Denied → Pi receives error, adapts plan

---

## Summary

| You Try | You Get |
|---------|---------|
| Touch `allow` zone | ✅ Instant success |
| Touch `ask` zone | ⏸️ HIL pause, negotiate with human |
| Touch `deny` zone | 🚫 Hard block, no appeal |
| Write to `ro` zone | 🚫 Auto-block at map level |
| Approve `session` | ✅ No more pauses this session |
| Approve `persistent` | ✅ Added to map forever |

The fence is a **conversation**. The wall is a ** verdict**.
