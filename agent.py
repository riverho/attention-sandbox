"""
agent.py — Example Agent Runner with Sandbox

Shows how to run an agent loop where every tool call passes through
the !MAP + HIL interceptor.
"""
from __future__ import annotations

import json
from pathlib import Path

from sandbox import (
    SandboxMap, SandboxInterceptor, HILApprover,
    ApprovalScope, get_all_tools
)


class DummyAgent:
    """
    A toy agent that reads a task and issues tool calls.
    In production, this is where your LLM (Pi, Claude, GPT-4, etc.) lives.
    """

    def __init__(self, interceptor: SandboxInterceptor):
        self.interceptor = interceptor
        self.messages = []

    def run_task(self, task: str) -> None:
        print(f"🤖 Agent task: {task}\n")
        self.messages.append({"role": "user", "content": task})

        # Simulated "LLM decides to read a file"
        # In reality, this comes from the model's function call
        calls = self._plan(task)

        for call in calls:
            tool = call["tool"]
            args = call["args"]
            print(f"  → {tool}({json.dumps(args, indent=None)})")

            result = self.interceptor.call(tool, args)

            if result.hil_id:
                print(f"\n⏸️  HIL PAUSED (id={result.hil_id})")
                print(result.error)
                # In a real system, the UI would show the HIL prompt and wait
                # Here we simulate human approval:
                human_input = input("\nApprove? [y/s/p/n] ").strip().lower()
                if human_input in ("y", "yes", "s", "session", "p", "persist"):
                    scope = ApprovalScope.ONCE
                    if human_input in ("s", "session"):
                        scope = ApprovalScope.SESSION
                    elif human_input in ("p", "persist"):
                        scope = ApprovalScope.PERSISTENT
                    result = self.interceptor.resume(result.hil_id, scope)
                    if result.allowed:
                        print(f"✅ Success:\n{result.data[:500]}...\n")
                    else:
                        print(f"❌ Error: {result.error}\n")
                else:
                    result = self.interceptor.deny_resume(result.hil_id)
                    print(f"🚫 Denied. Agent should adapt.\n")

            elif result.allowed:
                print(f"  ✅ Success:\n{result.data[:500]}...\n")
                self.messages.append({"role": "tool", "content": result.data})
            else:
                print(f"  ❌ Blocked: {result.error}\n")
                self.messages.append({"role": "tool", "content": result.error})

    def _plan(self, task: str) -> list:
        """
        Hardcoded plans for demo purposes.
        Real agent would use LLM reasoning.
        """
        if "readme" in task.lower():
            return [{"tool": "read", "args": {"path": "README.md"}}]
        if "outside" in task.lower() or "root" in task.lower():
            return [{"tool": "read", "args": {"path": "/etc/passwd"}}]
        if "desktop" in task.lower():
            return [{"tool": "bash", "args": {"command": "ls ~/Desktop"}}]
        if "edit" in task.lower():
            return [{"tool": "edit", "args": {"path": "README.md", "edits": [{"oldText": "## Roadmap", "newText": "## Roadmap (Updated!)"}]}}]
        if "bash" in task.lower():
            return [{"tool": "bash", "args": {"command": "echo Hello from sandbox"}}]
        return [{"tool": "read", "args": {"path": task}}]


def main():
    # Load map
    map_path = Path("maps/default.yaml")
    if map_path.exists():
        smap = SandboxMap.from_yaml(str(map_path))
    else:
        smap = SandboxMap()

    hil = HILApprover()
    interceptor = SandboxInterceptor(smap, hil, get_all_tools())

    print("🛡️  Attention Sandbox — Agent Runner\n")
    print(smap.to_table())
    print()

    agent = DummyAgent(interceptor)

    print("Demo tasks you can try:")
    print("  - 'Read the readme'")
    print("  - 'Look outside the sandbox (root)'")
    print("  - 'Check my desktop'")
    print("  - 'Edit the readme'")
    print("  - 'Run a bash command'")
    print("  - Or type a file path")
    print()

    while True:
        try:
            task = input("Task> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not task:
            continue
        if task in ("quit", "exit", "q"):
            break
        agent.run_task(task)
        print("─" * 60)

    print(f"\nFinal stats: {interceptor.stats()}")


if __name__ == "__main__":
    main()
