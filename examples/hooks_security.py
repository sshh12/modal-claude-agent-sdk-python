"""Security and monitoring example - secure sandbox configuration with audit logging.

This example demonstrates security best practices for Modal sandboxes:
- Network isolation with CIDR allowlist (only Anthropic API access)
- Tool restrictions via allowed_tools/disallowed_tools
- Client-side audit logging by observing streamed messages
- Secure system prompts that discourage dangerous operations

Note: Since the agent runs in a remote Modal sandbox, Python callback hooks
(like PreToolUse) cannot intercept tool calls. Instead, we use:
1. Network isolation to prevent data exfiltration
2. Tool restrictions to limit capabilities
3. System prompts to guide safe behavior
4. Client-side monitoring for audit trails
"""

import asyncio
from datetime import datetime

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)

# Anthropic API CIDR - required for agent to function
ANTHROPIC_API_CIDR = ["160.79.104.0/23"]


class SecurityAuditLog:
    """Client-side audit logger for monitoring agent tool usage."""

    def __init__(self):
        self.entries = []
        self.alerts = []

    def log_tool_use(self, tool_name: str, tool_input: dict, tool_id: str):
        """Log a tool invocation."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "tool_invocation",
            "tool": tool_name,
            "tool_id": tool_id,
            "input_summary": self._summarize_input(tool_name, tool_input),
        }
        self.entries.append(entry)

        # Check for potentially concerning patterns
        self._check_security_patterns(tool_name, tool_input)

        print(f"[AUDIT] {entry['timestamp']} - {tool_name}: {entry['input_summary']}")

    def log_tool_result(self, tool_id: str, is_error: bool):
        """Log a tool result."""
        status = "error" if is_error else "success"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "tool_result",
            "tool_id": tool_id,
            "status": status,
        }
        self.entries.append(entry)

    def _summarize_input(self, tool_name: str, tool_input: dict) -> str:
        """Create a safe summary of tool input for logging."""
        if tool_name == "Bash":
            cmd = tool_input.get("command", "")[:80]
            return (
                f"command='{cmd}...'"
                if len(tool_input.get("command", "")) > 80
                else f"command='{cmd}'"
            )
        elif tool_name in ["Write", "Edit", "Read"]:
            return f"file={tool_input.get('file_path', 'unknown')}"
        else:
            return f"keys={list(tool_input.keys())}"

    def _check_security_patterns(self, tool_name: str, tool_input: dict):
        """Check for security-concerning patterns and log alerts."""
        if tool_name == "Bash":
            command = tool_input.get("command", "")

            # Patterns that might indicate concerning behavior
            warning_patterns = [
                ("rm -rf", "Recursive deletion detected"),
                ("curl", "Network request via curl"),
                ("wget", "Network request via wget"),
                ("/etc/", "Access to /etc/ directory"),
                ("env", "Environment variable access"),
                ("export", "Environment modification"),
            ]

            for pattern, description in warning_patterns:
                if pattern in command:
                    alert = {
                        "timestamp": datetime.now().isoformat(),
                        "severity": "warning",
                        "description": description,
                        "command": command[:100],
                    }
                    self.alerts.append(alert)
                    print(f"[ALERT] {description}: {command[:50]}...")

    def print_summary(self):
        """Print audit log summary."""
        print("\n" + "=" * 60)
        print("AUDIT LOG SUMMARY")
        print("=" * 60)
        print(f"Total events: {len(self.entries)}")
        print(f"Security alerts: {len(self.alerts)}")

        # Count by tool
        tool_counts = {}
        for entry in self.entries:
            if entry["event"] == "tool_invocation":
                tool = entry["tool"]
                tool_counts[tool] = tool_counts.get(tool, 0) + 1

        print("\nTool usage:")
        for tool, count in sorted(tool_counts.items()):
            print(f"  {tool}: {count} calls")

        if self.alerts:
            print("\nSecurity alerts:")
            for alert in self.alerts:
                print(f"  [{alert['severity']}] {alert['description']}")


async def main():
    """Run an agent with security monitoring and network isolation."""

    audit_log = SecurityAuditLog()

    # Configure secure sandbox with network isolation
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        # Network isolation: only allow Anthropic API
        cidr_allowlist=ANTHROPIC_API_CIDR,
        # Restrict available tools
        allowed_tools=["Bash", "Write", "Read", "Glob"],
        # Disallow tools that could be used for exfiltration
        disallowed_tools=["WebFetch", "WebSearch"],
        # System prompt that encourages safe behavior
        system_prompt=(
            "You are a helpful assistant working in a secure sandbox environment. "
            "Important security guidelines:\n"
            "- Only work with files in the current directory or /tmp\n"
            "- Do not attempt to access system files in /etc, /root, etc.\n"
            "- Do not attempt network operations (curl, wget, etc.) as they will fail\n"
            "- Focus on the user's requested task"
        ),
        max_turns=10,
    )

    print("Security-Hardened Modal Agent Example")
    print("=" * 60)
    print("Security measures in place:")
    print(f"  - Network isolation: Only {ANTHROPIC_API_CIDR}")
    print("  - Disallowed tools: WebFetch, WebSearch")
    print("  - Client-side audit logging enabled")
    print("=" * 60)
    print()

    prompt = (
        "Please do the following tasks:\n"
        "1. Create a file called hello.txt with 'Hello World'\n"
        "2. List files in the current directory\n"
        "3. Show the current working directory\n"
        "4. Create a simple Python script and run it"
    )

    async for message in query(prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    print(f"[assistant] {text[:200]}{'...' if len(text) > 200 else ''}")
                elif isinstance(block, ToolUseBlock):
                    audit_log.log_tool_use(block.name, block.input, block.id)
                elif isinstance(block, ToolResultBlock):
                    audit_log.log_tool_result(
                        block.tool_use_id, block.is_error if block.is_error else False
                    )
        elif isinstance(message, ResultMessage):
            print(f"\n[{message.subtype}] Completed in {message.num_turns} turns")

    # Print audit summary
    audit_log.print_summary()

    print("\n" + "=" * 60)
    print("Security notes:")
    print("  - All tool usage has been logged for audit purposes")
    print("  - Network isolation prevented external connections")
    print("  - This audit log could be sent to a SIEM or logging service")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
