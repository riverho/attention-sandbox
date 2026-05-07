name: attention-sandbox
description: |
  Minimal folder sandbox for Pi. Stops agent from accessing unmapped paths.
  Uses !MAP commands to define boundaries. Agent should read this to know its limits.
version: 1.0.0

# AGENTS: You Are In A Sandbox

You are operating inside a **!MAP sandbox**. This means only certain folders are accessible to you. **Do not waste tool calls hitting walls** — check your boundaries first.

## Your Current Boundaries

At startup, the system will tell you which paths are mapped. Typically this includes:
- Your working directory (allow:rw — free to edit)
- Parent directories (allow:ro — read only)
- Sensitive paths (deny — never touch)
- Everything else (deny — blocked by default)

## Rules (Read These!)

1. **Before accessing a new path, check if it's in your sandbox.**
   - Use `!STATUS` to see current boundaries.
   - Do NOT try to read/write outside mapped zones blindly.

2. **If you need access outside the map, ASK first.**
   - Say: *"I need to access ~/Desktop/ to complete this. Should I add it to the sandbox?"*
   - Do NOT just try and hit the wall — that's wasteful.

3. **Use !MAP commands to expand.**
   - `!MAP ~/Desktop -> allow:rw` — add with user permission
   - `!STATUS` — show current map
   - `!SANDBOX` — show help

4. **If you hit a sandbox stop, adapt.**
   - The error will say which path was blocked and what's currently allowed.
   - Suggest to the user how to fix it, then move on.
   - Do NOT retry the same blocked path multiple times.

## Example Good Behavior

**User:** "Check my Downloads folder for PDFs"

**Bad agent:**
```
> read ~/Downloads/
🔒 SANDBOX STOP — Downloads not in map
> (wasted call!)
```

**Good agent:**
```
> !STATUS
📋 Current map: ~/projects/attention-sandbox

I don't see ~/Downloads in the sandbox. Should I add it so I can check for PDFs?

User: yes

> !MAP ~/Downloads -> allow:rw
✅ Mapped

> read ~/Downloads/
(file list)
```

## Permission Icons

| Icon | Meaning | Your Action |
|------|---------|-------------|
| 🟢 | allow:rw | Free to read/write |
| 🟡 | allow:ro | Read only, no writes |
| 🔵 | ask:rw | Allowed but logged — user may review |
| 🔴 | deny | Never touch |

## When Sandbox Stops You

If you get this error:
```
🔒 SANDBOX STOP
The agent tried to read outside the mapped sandbox: ~/Desktop/secret.txt
Currently allowed paths:
    ~/projects/attention-sandbox
    ~/work/shared

To expand the sandbox: !MAP ~/Desktop -> allow:rw
```

**Do this:**
1. Show the user what's blocked and why
2. Ask if they want to expand the sandbox
3. If yes, use `!MAP`
4. If no, adapt your plan to work within mapped paths

## Advanced

- `!UNMAP ~/Desktop` — remove a path
- `!MAP ~/.ssh -> deny` — explicitly block a path
- Map files are saved in `.pi/sandbox-map.yaml`
