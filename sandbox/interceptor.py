"""
sandbox/interceptor.py — Tool Call Interception

Wraps agent tool calls, checks against !MAP, enforces HIL.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from sandbox.core import SandboxMap, Permission, Decision, extract_paths_from_tool
from sandbox.hil import HILApprover, ApprovalScope, format_hil_prompt


class SandboxResult:
    """Result of an intercepted tool call."""
    def __init__(self, allowed: bool, data: Any = None, error: str = "", hil_id: str = ""):
        self.allowed = allowed
        self.data = data
        self.error = error
        self.hil_id = hil_id

    def __bool__(self) -> bool:
        return self.allowed

    def __repr__(self) -> str:
        return f"SandboxResult(allowed={self.allowed}, hil_id={self.hil_id})"


class SandboxInterceptor:
    """
    The main gatekeeper. Wraps every tool call.
    """

    def __init__(self, map: SandboxMap, hil: HILApprover,
                 real_tools: Optional[Dict[str, Callable]] = None):
        self.map = map
        self.hil = hil
        self.real_tools = real_tools or {}
        self.blocked_count = 0
        self.approved_count = 0
        self.auto_approve_persist = False  # dev mode

    def register_tool(self, name: str, fn: Callable) -> None:
        self.real_tools[name] = fn

    def call(self, tool_name: str, arguments: dict) -> SandboxResult:
        """
        Main entry. Checks map, maybe triggers HIL, then executes or blocks.
        Also applies openclaw-grade path safety before execution.
        """
        targets = extract_paths_from_tool(tool_name, arguments)

        if not targets:
            return self._execute(tool_name, arguments)

        # Normalize and safety-check all targets
        decisions = self.map.check_many(targets)

        if all(d.rule.perm.is_allow for d in decisions):
            return self._execute(tool_name, arguments)

        deny_decisions = [d for d in decisions if d.rule.perm.is_deny]
        if deny_decisions:
            self.blocked_count += 1
            paths = ", ".join(d.path for d in deny_decisions)
            reason = " | ".join(d.rule.note for d in deny_decisions)
            return SandboxResult(
                allowed=False,
                error=f"🚫 SANDBOX DENIED: {tool_name} on {paths}\n   Rule: {reason}"
            )

        ask_decisions = [d for d in decisions if d.rule.perm.is_ask]
        ask_paths = [d.path for d in ask_decisions]
        reason = " | ".join(d.rule.note for d in ask_decisions)

        if all(self.hil.is_session_approved(p) for p in ask_paths):
            return self._execute(tool_name, arguments)

        req = self.hil.request_approval(tool_name, arguments, ask_paths, reason)
        return SandboxResult(
            allowed=False,
            error=f"⏸️ HIL PAUSED: {tool_name} on {ask_paths}\n{format_hil_prompt(req)}\n   → Approve with: hil.approve('{req.id}', scope)",
            hil_id=req.id
        )

    def resume(self, hil_id: str, scope: ApprovalScope = ApprovalScope.ONCE) -> Optional[SandboxResult]:
        """
        Resume a paused call after human approval.
        """
        req = self.hil.approve(hil_id, scope)
        if not req:
            return SandboxResult(allowed=False, error="HIL request not found or already handled")

        self.approved_count += 1

        if scope == ApprovalScope.PERSISTENT:
            # Update the map to allow this path
            from sandbox.core import Rule, Permission
            # Determine permission from the ask rule
            # Simple: allow rw for all ask paths
            for p in req.target_paths:
                self.map.add(Rule(path=p, perm=Permission.ALLOW_RW, note="HIL approved (persistent)"))

        return self._execute(req.tool_name, req.arguments)

    def deny_resume(self, hil_id: str) -> SandboxResult:
        req = self.hil.deny(hil_id)
        if not req:
            return SandboxResult(allowed=False, error="HIL request not found")
        self.blocked_count += 1
        return SandboxResult(allowed=False, error=f"🚫 HIL DENIED: {req.tool_name}")

    # ── Execution ────────────────────────────────────────────────────────

    def _execute(self, tool_name: str, arguments: dict) -> SandboxResult:
        fn = self.real_tools.get(tool_name)
        if not fn:
            return SandboxResult(allowed=False, error=f"Tool '{tool_name}' not registered")
        try:
            data = fn(**arguments)
            return SandboxResult(allowed=True, data=data)
        except Exception as e:
            return SandboxResult(allowed=False, error=str(e))

    # ── Stats ──────────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "blocked": self.blocked_count,
            "approved": self.approved_count,
            "pending_hil": len(self.hil.get_pending()),
            "map_rules": len(self.map.rules),
        }
