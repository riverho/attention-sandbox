"""
sandbox/hil.py — Human-in-the-Loop Approval

Manages pause/resume and approval decisions.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Awaitable


class ApprovalScope(Enum):
    ONCE = "once"           # Allow this single call only
    SESSION = "session"     # Allow for this session
    PERSISTENT = "persistent"  # Update the map permanently


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class HILRequest:
    id: str
    tool_name: str
    arguments: dict
    target_paths: List[str]
    reason: str
    created_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    scope: Optional[ApprovalScope] = None
    response: Optional[str] = None  # human's free-text response


class HILApprover:
    """
    Manages pending approvals. Can work synchronously (blocking) or async.
    """

    def __init__(self):
        self.pending: Dict[str, HILRequest] = {}
        self.approved_cache: set = set()  # (path, scope) pairs approved this session
        self.on_request: Optional[Callable[[HILRequest], None]] = None  # callback when HIL triggered
        self.history: List[HILRequest] = []

    def request_approval(self, tool_name: str, arguments: dict,
                         target_paths: List[str], reason: str) -> HILRequest:
        req = HILRequest(
            id=str(uuid.uuid4())[:8],
            tool_name=tool_name,
            arguments=arguments,
            target_paths=target_paths,
            reason=reason,
            created_at=datetime.now(),
        )
        self.pending[req.id] = req
        self.history.append(req)
        if self.on_request:
            self.on_request(req)
        return req

    def approve(self, req_id: str, scope: ApprovalScope = ApprovalScope.ONCE,
                response: str = "") -> Optional[HILRequest]:
        req = self.pending.pop(req_id, None)
        if not req:
            return None
        req.status = ApprovalStatus.APPROVED
        req.scope = scope
        req.response = response
        if scope in (ApprovalScope.SESSION, ApprovalScope.PERSISTENT):
            for p in req.target_paths:
                self.approved_cache.add(p)
        return req

    def deny(self, req_id: str, response: str = "") -> Optional[HILRequest]:
        req = self.pending.pop(req_id, None)
        if not req:
            return None
        req.status = ApprovalStatus.DENIED
        req.response = response
        return req

    def is_session_approved(self, path: str) -> bool:
        """Check if path is approved, including parent directory approvals."""
        for approved_path in self.approved_cache:
            if path.startswith(approved_path):
                return True
        return False

    def get_pending(self) -> List[HILRequest]:
        return list(self.pending.values())

    def clear_history(self) -> None:
        self.history.clear()


# ── Console UI helpers ───────────────────────────────────────────────────

def format_hil_prompt(req: HILRequest) -> str:
    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════════╗",
        "║  🤖 AGENT REQUESTS APPROVAL                                      ║",
        "╠══════════════════════════════════════════════════════════════════╣",
        f"║  Tool:     {req.tool_name:<47} ║",
        f"║  Paths:    {', '.join(req.target_paths)[:47]:<47} ║",
        f"║  Reason:   {req.reason[:47]:<47} ║",
        f"║  ID:       {req.id:<47} ║",
        "╚══════════════════════════════════════════════════════════════════╝",
        "",
        "Options:",
        "  y / yes        — Approve once",
        "  s / session    — Approve for this session",
        "  p / persist    — Approve and add to map",
        "  n / no         — Deny",
        "  ? <msg>        — Ask agent for clarification",
        "",
    ]
    return "\n".join(lines)
