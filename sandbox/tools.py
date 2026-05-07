"""
sandbox/tools.py — Real tool implementations with openclaw-grade safety.

These are the *actual* filesystem operations. The interceptor decides
*whether* to call them. Every write uses atomic temp+rename.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from sandbox.core import safe_normalize_path, is_path_inside, atomic_write_file


def tool_read(path: str, offset: int = 1, limit: int = 2000) -> str:
    """Read a file or image. Returns content."""
    p = Path(safe_normalize_path(path))
    if not p.exists():
        raise FileNotFoundError(f"No such file: {path}")
    if p.is_dir():
        items = list(p.iterdir())
        lines = [f"{i+1}. {item.name}{'/' if item.is_dir() else ''}" for i, item in enumerate(items)]
        return f"Directory: {path}\n" + "\n".join(lines)
    try:
        text = p.read_text()
        lines = text.splitlines()
        start = max(0, offset - 1)
        end = start + limit
        chunk = "\n".join(lines[start:end])
        if end < len(lines):
            chunk += f"\n\n... ({len(lines) - end} more lines)"
        return chunk
    except UnicodeDecodeError:
        return f"[Binary file: {path}]"


def tool_bash(command: str, timeout: Optional[int] = None) -> str:
    """Execute a bash command."""
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True,
        timeout=timeout
    )
    out = result.stdout or ""
    err = result.stderr or ""
    if result.returncode != 0:
        out += f"\n[exit code {result.returncode}]"
    if err:
        out += f"\n[stderr]\n{err}"
    return out.strip()


def tool_edit(path: str, edits: List[Dict[str, str]]) -> str:
    """Edit a file with exact replacements. Uses atomic write."""
    p = Path(safe_normalize_path(path))
    if not p.exists():
        raise FileNotFoundError(path)
    text = p.read_text()
    for e in edits:
        old = e["oldText"]
        new = e["newText"]
        if old not in text:
            raise ValueError(f"oldText not found in {path}")
        text = text.replace(old, new, 1)
    atomic_write_file(str(p), text)
    return f"Edited {path} ({len(edits)} replacements)"


def tool_write(path: str, content: str) -> str:
    """Write content to a file atomically."""
    p = Path(safe_normalize_path(path))
    atomic_write_file(str(p), content)
    return f"Wrote {len(content)} bytes to {path}"


def tool_mcp(server: str, tool: str, args: Optional[str] = None) -> str:
    """Stub for MCP calls. Production would route to real MCP."""
    return f"[MCP stub] server={server} tool={tool} args={args}"


def get_all_tools() -> Dict[str, Any]:
    return {
        "read": tool_read,
        "bash": tool_bash,
        "edit": tool_edit,
        "write": tool_write,
        "mcp": tool_mcp,
    }
