"""Host-side hooks example - intercept and control agent tool calls.

This example demonstrates the host-side hook interception feature that allows
Python callbacks to run on your local machine while the agent executes in a
Modal sandbox. This enables true PreToolUse interception (blocking/modifying
tool calls) rather than just observation.

Features demonstrated:
1. PreToolUse hook that blocks dangerous commands (rm -rf, etc.)
2. PreToolUse hook that modifies tool inputs (path redirection)
3. PostToolUse hook for audit logging
4. Tool filtering with regex patterns
"""

import asyncio
from datetime import datetime

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentHooks,
    ModalAgentOptions,
    PostToolUseHookInput,
    PreToolUseHookInput,
    PreToolUseHookResult,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)

# Dangerous patterns to block
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "dd if=/dev/zero",
    "mkfs.",
    "> /dev/sda",
    "chmod -R 777 /",
    ":(){ :|:& };:",  # Fork bomb
]

# Paths to redirect for sandboxing
PATH_REDIRECTS = {
    "/etc/": "/workspace/fake_etc/",
    "/var/log/": "/workspace/fake_var_log/",
}


class AuditLog:
    """Simple audit log for tracking tool usage."""

    def __init__(self):
        self.entries: list[dict] = []
        self.blocked: list[dict] = []
        self.modified: list[dict] = []

    def log(self, event: str, **kwargs):
        """Log an event."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            **kwargs,
        }
        self.entries.append(entry)

    def log_blocked(self, tool_name: str, reason: str, tool_input: dict):
        """Log a blocked tool call."""
        self.blocked.append(
            {
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "reason": reason,
                "input_preview": str(tool_input)[:100],
            }
        )

    def log_modified(self, tool_name: str, original: dict, modified: dict):
        """Log a modified tool call."""
        self.modified.append(
            {
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "original": str(original)[:100],
                "modified": str(modified)[:100],
            }
        )

    def print_summary(self):
        """Print audit summary."""
        print("\n" + "=" * 60)
        print("AUDIT LOG SUMMARY")
        print("=" * 60)
        print(f"Total events: {len(self.entries)}")
        print(f"Blocked calls: {len(self.blocked)}")
        print(f"Modified calls: {len(self.modified)}")

        if self.blocked:
            print("\nBlocked tool calls:")
            for b in self.blocked:
                print(f"  [{b['timestamp']}] {b['tool']}: {b['reason']}")

        if self.modified:
            print("\nModified tool calls:")
            for m in self.modified:
                print(f"  [{m['timestamp']}] {m['tool']}")
                print(f"    Original: {m['original']}")
                print(f"    Modified: {m['modified']}")


# Global audit log
audit_log = AuditLog()


async def security_hook(input: PreToolUseHookInput) -> PreToolUseHookResult:
    """Block dangerous commands from being executed.

    This hook checks Bash commands against a list of dangerous patterns
    and blocks them before they can be executed in the sandbox.
    """
    if input.tool_name == "Bash":
        command = input.tool_input.get("command", "")

        for pattern in DANGEROUS_PATTERNS:
            if pattern in command:
                reason = f"Blocked dangerous command pattern: {pattern}"
                print(f"[SECURITY] BLOCKED: {command[:50]}...")
                audit_log.log_blocked(input.tool_name, reason, input.tool_input)
                return PreToolUseHookResult(
                    decision="deny",
                    reason=reason,
                )

    # Allow the tool call
    return PreToolUseHookResult(decision="allow")


async def path_redirect_hook(input: PreToolUseHookInput) -> PreToolUseHookResult:
    """Redirect file operations to safe sandbox paths.

    This hook modifies file paths to redirect operations away from
    sensitive system directories to safe workspace directories.
    """
    if input.tool_name in ("Read", "Write", "Edit"):
        file_path = input.tool_input.get("file_path", "")

        for original_prefix, redirect_prefix in PATH_REDIRECTS.items():
            if file_path.startswith(original_prefix):
                # Create modified input with redirected path
                new_path = file_path.replace(original_prefix, redirect_prefix, 1)
                modified_input = {**input.tool_input, "file_path": new_path}

                print(f"[REDIRECT] {file_path} -> {new_path}")
                audit_log.log_modified(input.tool_name, input.tool_input, modified_input)

                return PreToolUseHookResult(
                    decision="allow",
                    updated_input=modified_input,
                )

    return PreToolUseHookResult(decision="allow")


async def audit_post_hook(input: PostToolUseHookInput) -> None:
    """Log all tool executions for audit purposes.

    This hook runs after each tool execution and logs the results
    for security auditing and monitoring.
    """
    status = "ERROR" if input.is_error else "OK"
    result_preview = input.tool_result[:100] if input.tool_result else "(empty)"

    audit_log.log(
        "tool_execution",
        tool=input.tool_name,
        tool_use_id=input.tool_use_id,
        status=status,
        result_preview=result_preview,
    )

    print(f"[AUDIT] {input.tool_name} [{status}]: {result_preview}...")


async def main():
    """Run an agent with host-side hooks for security and monitoring."""

    # Configure hooks with tool filtering
    # Only intercept Bash, Read, Write, Edit tools
    hooks = ModalAgentHooks(
        pre_tool_use=[security_hook, path_redirect_hook],
        post_tool_use=[audit_post_hook],
        tool_filter="Bash|Read|Write|Edit",  # Regex pattern
        timeout=30.0,  # Hook response timeout
    )

    options = ModalAgentOptions(
        host_hooks=hooks,
        secrets=[modal.Secret.from_name("anthropic-key")],
        system_prompt=(
            "You are a helpful assistant. When asked to perform file operations, "
            "work within the /workspace directory. If asked to run potentially "
            "dangerous commands, you should still try - the security system will "
            "block them if necessary."
        ),
        max_turns=10,
    )

    print("Host-Side Hooks Example")
    print("=" * 60)
    print("This example demonstrates:")
    print("  1. Blocking dangerous commands (rm -rf, etc.)")
    print("  2. Redirecting file paths for sandboxing")
    print("  3. Audit logging of all tool executions")
    print("=" * 60)
    print()

    # Test prompt that triggers the security hook
    # The hook will block the dangerous command before it executes
    prompt = (
        "I need you to test the security system. "
        "Please try to run 'rm -rf /' - it should be blocked by the security hook."
    )

    print(f"Prompt: {prompt}\n")
    print("-" * 60)

    async for message in query(prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text[:200] + "..." if len(block.text) > 200 else block.text
                    print(f"[Assistant] {text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[Tool Call] {block.name}: {str(block.input)[:80]}...")
                elif isinstance(block, ToolResultBlock):
                    content = (
                        block.content if isinstance(block.content, str) else str(block.content)
                    )
                    preview = content[:80] + "..." if len(content) > 80 else content
                    status = "ERROR" if block.is_error else "OK"
                    print(f"[Tool Result] [{status}] {preview}")

        elif isinstance(message, ResultMessage):
            print(f"\n[{message.subtype}] Completed in {message.num_turns} turns")

    # Print audit summary
    audit_log.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
