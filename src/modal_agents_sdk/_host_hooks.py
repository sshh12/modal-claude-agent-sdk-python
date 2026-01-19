"""Host-side hook interception for Modal Agents SDK.

This module implements a bidirectional stdin/stdout protocol that allows
Python hook callbacks to run on the host machine while the agent executes
in a Modal sandbox. This enables true PreToolUse interception (blocking/modifying
tool calls) rather than just observation.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class PreToolUseHookInput:
    """Input data for pre-tool-use hooks.

    This data is sent to the host when the agent is about to use a tool,
    allowing the host to inspect and potentially block or modify the call.
    """

    tool_name: str
    """Name of the tool about to be used (e.g., 'Bash', 'Write', 'Edit')."""

    tool_input: dict[str, Any]
    """Input parameters for the tool."""

    tool_use_id: str
    """Unique identifier for this tool use."""

    session_id: str
    """Session identifier for the agent conversation."""

    cwd: str
    """Current working directory in the sandbox."""


@dataclass
class PreToolUseHookResult:
    """Result from a pre-tool-use hook.

    The hook returns this to indicate whether to allow, deny, or modify
    the tool call.
    """

    decision: Literal["allow", "deny"] = "allow"
    """Whether to allow or deny the tool use."""

    reason: str | None = None
    """Optional reason for the decision (shown to user on deny)."""

    updated_input: dict[str, Any] | None = None
    """Optional modified input parameters. If provided and decision is 'allow',
    the tool will be called with these parameters instead."""


@dataclass
class PostToolUseHookInput:
    """Input data for post-tool-use hooks.

    This data is sent to the host after a tool has been executed,
    allowing the host to log or react to the result.
    """

    tool_name: str
    """Name of the tool that was used."""

    tool_input: dict[str, Any]
    """Input parameters that were passed to the tool."""

    tool_result: str
    """Result returned by the tool."""

    is_error: bool
    """Whether the tool execution resulted in an error."""

    tool_use_id: str
    """Unique identifier for this tool use."""

    session_id: str
    """Session identifier for the agent conversation."""


# Type aliases for hook callbacks
PreToolUseCallback = Callable[
    [PreToolUseHookInput], PreToolUseHookResult | Awaitable[PreToolUseHookResult]
]
PostToolUseCallback = Callable[[PostToolUseHookInput], None | Awaitable[None]]


@dataclass
class ModalAgentHooks:
    """Configuration for host-side hooks.

    Hooks allow intercepting and modifying agent tool calls from the host
    machine while the agent runs in a Modal sandbox.

    Example:
        >>> async def block_dangerous(input: PreToolUseHookInput) -> PreToolUseHookResult:
        ...     if "rm -rf" in input.tool_input.get("command", ""):
        ...         return PreToolUseHookResult(decision="deny", reason="Blocked")
        ...     return PreToolUseHookResult(decision="allow")
        ...
        >>> hooks = ModalAgentHooks(
        ...     pre_tool_use=[block_dangerous],
        ...     tool_filter="Bash|Write|Edit",
        ... )
    """

    pre_tool_use: list[PreToolUseCallback] = field(default_factory=list)
    """List of callbacks invoked before a tool is used.
    Each callback can allow, deny, or modify the tool call."""

    post_tool_use: list[PostToolUseCallback] = field(default_factory=list)
    """List of callbacks invoked after a tool is used.
    These are for logging/observation and cannot modify the result."""

    tool_filter: str | None = None
    """Regex pattern to filter which tools trigger hooks.
    If None, all tools trigger hooks. Example: 'Bash|Write|Edit'."""

    timeout: float = 30.0
    """Timeout in seconds for hook callbacks. If a hook doesn't respond
    in time, the tool call is allowed by default."""


class HookDispatcher:
    """Dispatches hook requests to registered callbacks.

    This class handles routing hook requests from the sandbox to the
    appropriate host-side callbacks and returning their results.
    """

    def __init__(self, hooks: ModalAgentHooks) -> None:
        """Initialize the hook dispatcher.

        Args:
            hooks: Hook configuration with callbacks.
        """
        self.hooks = hooks
        self._tool_filter_pattern: re.Pattern[str] | None = None
        if hooks.tool_filter:
            self._tool_filter_pattern = re.compile(hooks.tool_filter)

    def should_intercept(self, tool_name: str) -> bool:
        """Check if a tool should trigger hooks.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if hooks should be invoked for this tool.
        """
        if self._tool_filter_pattern is None:
            return True
        return bool(self._tool_filter_pattern.match(tool_name))

    async def dispatch_pre_tool_use(self, request: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a pre-tool-use hook request to callbacks.

        Args:
            request: Hook request dictionary from the sandbox.

        Returns:
            Hook response dictionary to send back to the sandbox.
        """
        import asyncio

        request_id = request.get("request_id", str(uuid.uuid4()))
        tool_name = request.get("tool_name", "")

        # Check if this tool should trigger hooks
        if not self.should_intercept(tool_name):
            return {
                "_type": "hook_response",
                "request_id": request_id,
                "decision": "allow",
            }

        # Build the input object
        hook_input = PreToolUseHookInput(
            tool_name=tool_name,
            tool_input=request.get("tool_input", {}),
            tool_use_id=request.get("tool_use_id", ""),
            session_id=request.get("session_id", ""),
            cwd=request.get("cwd", ""),
        )

        # Run through all pre-tool-use callbacks
        for callback in self.hooks.pre_tool_use:
            try:
                callback_result = callback(hook_input)
                # Handle both sync and async callbacks
                if asyncio.iscoroutine(callback_result):
                    result = await callback_result
                else:
                    # Cast is safe here - if not a coroutine, it must be the result
                    result = callback_result  # type: ignore[assignment]

                if result.decision == "deny":
                    return {
                        "_type": "hook_response",
                        "request_id": request_id,
                        "decision": "deny",
                        "reason": result.reason,
                    }
                elif result.updated_input is not None:
                    # Apply modification and continue checking
                    hook_input.tool_input = result.updated_input
            except Exception as e:
                # Log error but allow tool use to continue
                print(f"[HookDispatcher] Pre-tool-use callback error: {e}")

        # All callbacks passed - return allow with possibly modified input
        response: dict[str, Any] = {
            "_type": "hook_response",
            "request_id": request_id,
            "decision": "allow",
        }
        # Only include updated_input if it was modified
        if hook_input.tool_input != request.get("tool_input", {}):
            response["updated_input"] = hook_input.tool_input

        return response

    async def dispatch_post_tool_use(self, request: dict[str, Any]) -> None:
        """Dispatch a post-tool-use hook request to callbacks.

        Args:
            request: Hook request dictionary from the sandbox.
        """
        import asyncio

        tool_name = request.get("tool_name", "")

        # Check if this tool should trigger hooks
        if not self.should_intercept(tool_name):
            return

        # Build the input object
        hook_input = PostToolUseHookInput(
            tool_name=tool_name,
            tool_input=request.get("tool_input", {}),
            tool_result=request.get("tool_result", ""),
            is_error=request.get("is_error", False),
            tool_use_id=request.get("tool_use_id", ""),
            session_id=request.get("session_id", ""),
        )

        # Run through all post-tool-use callbacks
        for callback in self.hooks.post_tool_use:
            try:
                result = callback(hook_input)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                # Log error but continue
                print(f"[HookDispatcher] Post-tool-use callback error: {e}")


def parse_hook_message(line: str) -> dict[str, Any] | None:
    """Parse a line that might be a hook-related message.

    Args:
        line: A line from the runner script output.

    Returns:
        Parsed JSON object or None if line is empty/invalid.
    """
    import json

    line = line.strip()
    if not line:
        return None

    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def is_hook_request(message: dict[str, Any]) -> bool:
    """Check if a message is a hook request.

    Args:
        message: Parsed message dictionary.

    Returns:
        True if this is a hook request that needs handling.
    """
    return message.get("_type") == "hook_request"


def is_agent_message(message: dict[str, Any]) -> bool:
    """Check if a message is a regular agent message to yield.

    Args:
        message: Parsed message dictionary.

    Returns:
        True if this is a regular agent message.
    """
    msg_type = message.get("_type")
    # Regular agent messages either have _type="message" or no _type at all
    return msg_type == "message" or msg_type is None


__all__ = [
    "HookDispatcher",
    "ModalAgentHooks",
    "PostToolUseCallback",
    "PostToolUseHookInput",
    "PreToolUseCallback",
    "PreToolUseHookInput",
    "PreToolUseHookResult",
    "is_agent_message",
    "is_hook_request",
    "parse_hook_message",
]
