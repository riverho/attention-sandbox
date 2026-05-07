"""
sandbox/repl.py — Interactive Sandbox Shell

Test the !MAP and HIL system manually.
"""
from __future__ import annotations

import cmd
import sys
from pathlib import Path

from sandbox.core import SandboxMap, Rule, Permission
from sandbox.hil import HILApprover, ApprovalScope
from sandbox.interceptor import SandboxInterceptor
from sandbox.tools import get_all_tools


class SandboxREPL(cmd.Cmd):
    intro = """\n🛡️  Attention Sandbox REPL
Type 'help' for commands. Use !MAP to set boundaries.
"""
    prompt = "sandbox> "

    def __init__(self):
        super().__init__()
        self.map = SandboxMap()
        self.hil = HILApprover()
        self.interceptor = SandboxInterceptor(self.map, self.hil, get_all_tools())

        # Default safe map
        self.map.add(Rule(path=Path.cwd().as_posix(), perm=Permission.ALLOW_RW, note="CWD"))
        self.map.add(Rule(path="/", perm=Permission.ASK_RO, note="Root — ask first"))

        self.hil.on_request = self._on_hil

    def _on_hil(self, req):
        print(f"\n⏸️  HIL triggered: {req.id} — {req.tool_name} on {req.target_paths}\n")

    # ── Custom Commands ─────────────────────────────────────────────────

    def do_map(self, arg):
        """!MAP /path -> allow:rw  # Add a map rule"""
        if not arg:
            print(self.map.to_table())
            return
        try:
            rule = SandboxMap.from_dsl(f"!MAP {arg}")
            self.map.add(rule)
            print(f"✅ Mapped: {rule.path} -> {rule.perm.value}")
        except Exception as e:
            print(f"❌ Error: {e}")

    def do_unmap(self, arg):
        """Remove a map rule by path"""
        self.map.remove(arg)
        print(f"🗑️  Removed map for {arg}")

    def do_status(self, arg):
        """Show sandbox status"""
        print(self.map.to_table())
        print()
        stats = self.interceptor.stats()
        print(f"Stats: {stats}")
        pending = self.hil.get_pending()
        if pending:
            print(f"\n⏸️  Pending HIL requests:")
            for p in pending:
                print(f"   {p.id}: {p.tool_name} -> {p.target_paths}")

    def do_approve(self, arg):
        """approve <id> [once|session|persist] — Approve a HIL request"""
        parts = arg.split()
        if not parts:
            print("Usage: approve <id> [scope]")
            return
        req_id = parts[0]
        scope = ApprovalScope.ONCE
        if len(parts) > 1:
            scope = ApprovalScope(parts[1].lower())
        result = self.interceptor.resume(req_id, scope)
        if result and result.allowed:
            print(f"✅ Approved & executed:\n{result.data}")
        elif result:
            print(f"❌ {result.error}")

    def do_deny(self, arg):
        """deny <id> — Deny a HIL request"""
        result = self.interceptor.deny_resume(arg.strip())
        print(f"🚫 Denied: {result.error}")

    def do_load(self, arg):
        """load <map.yaml> — Load map from YAML"""
        if not arg:
            print("Usage: load <file.yaml>")
            return
        try:
            self.map = SandboxMap.from_yaml(arg.strip())
            self.interceptor.map = self.map
            print(f"📂 Loaded map from {arg}")
        except Exception as e:
            print(f"❌ {e}")

    # ── Tool Commands ────────────────────────────────────────────────────

    def do_read(self, arg):
        """read <path> [offset] [limit]"""
        parts = arg.split()
        if not parts:
            print("Usage: read <path>")
            return
        path = parts[0]
        offset = int(parts[1]) if len(parts) > 1 else 1
        limit = int(parts[2]) if len(parts) > 2 else 2000
        result = self.interceptor.call("read", {"path": path, "offset": offset, "limit": limit})
        self._show(result)

    def do_bash(self, arg):
        """bash <command>"""
        result = self.interceptor.call("bash", {"command": arg})
        self._show(result)

    def do_edit(self, arg):
        """edit <path> — Interactive or pre-set edits"""
        parts = arg.split()
        if not parts:
            print("Usage: edit <path> <oldText> <newText>")
            return
        path = parts[0]
        # For simplicity in REPL, require inline old/new
        # Full edit support is for agent use
        print("Interactive edit not yet in REPL. Use agent.py.")

    def do_write(self, arg):
        """write <path> — Enter multi-line content, end with EOF"""
        parts = arg.split(None, 1)
        if not parts:
            print("Usage: write <path>")
            return
        path = parts[0]
        print("Enter content (Ctrl+D / EOF to finish):")
        lines = []
        try:
            while True:
                line = input()
                if line.strip().upper() == "EOF":
                    break
                lines.append(line)
        except EOFError:
            pass
        content = "\n".join(lines)
        result = self.interceptor.call("write", {"path": path, "content": content})
        self._show(result)

    # ── Helpers ─────────────────────────────────────────────────────────

    def _show(self, result):
        if result.allowed:
            print(result.data)
        else:
            print(result.error)

    def do_EOF(self, arg):
        print("\n👋 Goodbye.")
        return True

    def default(self, line):
        if line.startswith("!"):
            # Pass through to !MAP, !STATUS, etc.
            if line.startswith("!MAP"):
                self.do_map(line[4:].strip())
            elif line.startswith("!STATUS"):
                self.do_status("")
            else:
                print(f"Unknown command: {line}")
        else:
            print(f"Unknown command: {line}")


def main():
    repl = SandboxREPL()
    try:
        repl.cmdloop()
    except KeyboardInterrupt:
        print("\n👋 Interrupted.")


if __name__ == "__main__":
    main()
