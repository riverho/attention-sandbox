"""
sandbox/core.py — The !MAP engine + openclaw-grade path safety

Manages path-to-permission mappings with longest-prefix matching,
plus symlink guards, realpath canonicalization, and boundary verification
ported from openclaw's fs-safe.ts.
"""
from __future__ import annotations

import os
import re
import tempfile
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class Permission(Enum):
    ALLOW_RW = "allow:rw"
    ALLOW_RO = "allow:ro"
    DENY = "deny"
    ASK_RW = "ask:rw"
    ASK_RO = "ask:ro"

    @property
    def is_allow(self) -> bool:
        return self in (Permission.ALLOW_RW, Permission.ALLOW_RO)

    @property
    def is_deny(self) -> bool:
        return self == Permission.DENY

    @property
    def is_ask(self) -> bool:
        return self in (Permission.ASK_RW, Permission.ASK_RO)

    @property
    def is_write(self) -> bool:
        return self in (Permission.ALLOW_RW, Permission.ASK_RW)


@dataclass
class Rule:
    path: str          # normalized absolute path
    perm: Permission
    note: str = ""


@dataclass
class Decision:
    path: str
    rule: Rule
    approved: Optional[bool] = None   # None = not yet HIL'd
    reason: str = ""


# ── Openclaw-Grade Path Safety ──────────────────────────────────────────────

def safe_normalize_path(p: str) -> str:
    """
    Expand ~ and env vars, resolve to absolute, then realpath.
    Raises ValueError if path contains symlink components that escape.
    """
    p = os.path.expanduser(p)
    p = os.path.expandvars(p)
    p = os.path.abspath(p)
    # realpath resolves symlinks — this is the key guard from openclaw
    try:
        real = os.path.realpath(p)
    except (OSError, ValueError) as e:
        raise ValueError(f"Path resolution failed: {p}") from e
    return real


def ensure_trailing_sep(p: str) -> str:
    """Ensure path ends with separator for safe prefix matching."""
    return p if p.endswith(os.sep) else p + os.sep


def is_path_inside(root: str, target: str) -> bool:
    """
    Check if target is inside root. Both must be normalized.
    Uses trailing-separator trick to prevent partial directory name matches.
    """
    root_sep = ensure_trailing_sep(root)
    target_sep = ensure_trailing_sep(target) if os.path.isdir(target) else target
    return target_sep.startswith(root_sep) or target == root


def has_symlink_component(p: str) -> bool:
    """Check if any component of the path is a symlink."""
    p = safe_normalize_path(p)
    current = p
    while current != os.path.dirname(current):
        if os.path.islink(current):
            return True
        current = os.path.dirname(current)
    return False


def safe_resolve_within_root(root: str, target: str) -> str:
    """
    Resolve target path within root boundary.
    Raises PermissionError if resolved path escapes root (symlink, .., etc.)
    """
    root_real = safe_normalize_path(root)
    target_expanded = os.path.expanduser(os.path.expandvars(target))
    
    if os.path.isabs(target_expanded):
        resolved = safe_normalize_path(target_expanded)
    else:
        resolved = safe_normalize_path(os.path.join(root_real, target_expanded))
    
    if not is_path_inside(root_real, resolved):
        raise PermissionError(
            f"outside-workspace: {resolved} is outside root {root_real}"
        )
    
    # Double-check no symlink escapes
    if has_symlink_component(resolved):
        # Verify the realpath is still inside
        real = os.path.realpath(resolved)
        if not is_path_inside(root_real, real):
            raise PermissionError(
                f"symlink-escape: {resolved} resolves to {real} outside root"
            )
    
    return resolved


# ── !MAP Engine ───────────────────────────────────────────────────────────

class SandboxMap:
    """
    A runtime permission map for filesystem targets.
    Uses longest-prefix matching. Later rules override earlier ones at same depth.
    """

    def __init__(self, rules: Optional[List[Rule]] = None):
        self.rules: List[Rule] = rules or []
        self._sort()

    @classmethod
    def from_yaml(cls, path: str) -> "SandboxMap":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        rules = []
        for raw_path, cfg in data.get("map", {}).items():
            perm = Permission(cfg["perm"])
            note = cfg.get("note", "")
            rules.append(Rule(path=safe_normalize_path(raw_path), perm=perm, note=note))
        return cls(rules)

    @classmethod
    def from_dsl(cls, line: str) -> "Rule":
        """
        Parse a !MAP DSL line:
            !MAP /some/path -> allow:rw  # note
        """
        line = line.strip()
        if line.startswith("!MAP"):
            line = line[4:].strip()
        if "->" not in line:
            raise ValueError(f"Invalid !MAP syntax: {line}")
        path_part, rest = line.split("->", 1)
        path = safe_normalize_path(path_part.strip())
        rest = rest.strip()
        note = ""
        if "#" in rest:
            rest, note = rest.split("#", 1)
            note = note.strip()
        perm = Permission(rest.strip())
        return Rule(path=path, perm=perm, note=note)

    def add(self, rule: Rule) -> None:
        # Normalize rule path to realpath for security (handles macOS /etc -> /private/etc etc.)
        rule.path = safe_normalize_path(rule.path)
        self.rules = [r for r in self.rules if r.path != rule.path]
        self.rules.append(rule)
        self._sort()

    def remove(self, path: str) -> None:
        path = safe_normalize_path(path)
        self.rules = [r for r in self.rules if r.path != path]

    def check(self, target: str, operation: str = "read") -> Decision:
        target = safe_normalize_path(target)
        best: Optional[Rule] = None
        for rule in self.rules:
            if target.startswith(rule.path) or rule.path == target:
                if best is None or len(rule.path) > len(best.path):
                    best = rule
        if best is None:
            best = Rule(path="/", perm=Permission.DENY, note="No matching map rule")
        if operation == "write" and not best.perm.is_write:
            best = Rule(path=best.path, perm=Permission.DENY, note=f"Write denied: {best.note}")
        return Decision(path=target, rule=best)

    def check_many(self, targets: List[Tuple[str, str]]) -> List[Decision]:
        return [self.check(t, op) for t, op in targets]

    def _sort(self) -> None:
        self.rules.sort(key=lambda r: len(r.path))

    def to_table(self) -> str:
        lines = ["┌────────────────────────────────────────┬─────────────┬─────────────────────┐",
                 "│ Path                                   │ Permission  │ Note                │",
                 "├────────────────────────────────────────┼─────────────┼─────────────────────┤"]
        for r in self.rules:
            lines.append(f"│ {r.path:<38} │ {r.perm.value:<11} │ {r.note:<19} │")
        lines.append("└────────────────────────────────────────┴─────────────┴─────────────────────┘")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"SandboxMap({len(self.rules)} rules)"


# ── Path Extraction from Tool Calls ────────────────────────────────────────

def extract_paths_from_tool(tool_name: str, arguments: dict) -> List[Tuple[str, str]]:
    paths: List[Tuple[str, str]] = []
    if tool_name in ("read", "edit"):
        if "path" in arguments:
            op = "write" if tool_name == "edit" else "read"
            paths.append((arguments["path"], op))
    elif tool_name == "write":
        if "path" in arguments:
            paths.append((arguments["path"], "write"))
    elif tool_name == "bash":
        cmd = arguments.get("command", "")
        paths.extend(_extract_from_bash(cmd))
    elif tool_name == "mcp":
        paths.extend(_deep_scan_paths(arguments))
    return paths


def _extract_from_bash(cmd: str) -> List[Tuple[str, str]]:
    paths: List[Tuple[str, str]] = []
    tokens = cmd.split()
    file_ops = {"cp", "mv", "rm", "rmdir", "touch", "cat", "head", "tail",
                "ls", "mkdir", "chmod", "chown", "nano", "vim", "sed", "awk",
                "grep", "find", "tar", "zip", "unzip"}
    op_map = {
        "cp": "read", "mv": "write", "rm": "write", "rmdir": "write",
        "touch": "write", "cat": "read", "head": "read", "tail": "read",
        "ls": "read", "mkdir": "write", "chmod": "write", "chown": "write",
        "nano": "write", "vim": "write", "sed": "write", "awk": "read",
        "grep": "read", "find": "read", "tar": "read", "zip": "read", "unzip": "write",
    }
    if not tokens:
        return paths
    base = tokens[0]
    if base == "sudo" and len(tokens) > 1:
        base = tokens[1]
        tokens = tokens[1:]
    if base in file_ops:
        op = op_map.get(base, "read")
        for tok in tokens[1:]:
            if tok.startswith("-"):
                continue
            if tok in (">", ">>", "|<", "2>", "2>>"):
                break
            if tok.startswith(("/", "./", "../", "~")):
                paths.append((tok, op))
    for match in re.finditer(r'(?<![\w-])(/\S+)', cmd):
        p = match.group(1).strip("'\"")
        if not any(existing[0] == p for existing in paths):
            paths.append((p, "read"))
    return paths


def _deep_scan_paths(obj, current_op: str = "read") -> List[Tuple[str, str]]:
    paths: List[Tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("path", "file", "filename", "dir", "directory", "src", "dst", "source", "target"):
                if isinstance(v, str) and v.startswith(("/", "./", "../", "~")):
                    paths.append((v, current_op))
            else:
                paths.extend(_deep_scan_paths(v, current_op))
    elif isinstance(obj, list):
        for item in obj:
            paths.extend(_deep_scan_paths(item, current_op))
    return paths


# ── Atomic Write Helper (from openclaw fs-safe) ───────────────────────────

def atomic_write_file(target_path: str, data: str | bytes, mode: int = 0o600) -> None:
    """
    Write data atomically using temp file + rename.
    If something goes wrong, the original file is untouched.
    """
    p = Path(target_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=f".{p.name}.",
            dir=str(p.parent)
        )
        if isinstance(data, str):
            os.write(fd, data.encode("utf-8"))
        else:
            os.write(fd, data)
        os.close(fd)
        fd = None
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, str(p))
        tmp_path = None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
