"""Type definitions and re-exports from claude-agent-sdk."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Re-export types from claude-agent-sdk for convenience
from claude_agent_sdk import (
    AssistantMessage,
    ContentBlock,
    Message,
    ResultMessage,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk.types import StreamEvent, TextBlock, ThinkingBlock

# Type aliases
HookCallback = Callable[[dict[str, Any]], None]
ToolValidator = Callable[[str, dict[str, Any]], bool]


def _convert_content_block(block: dict[str, Any]) -> ContentBlock:
    """Convert a raw dict to a ContentBlock type.

    Args:
        block: Raw block dictionary.

    Returns:
        Typed content block (TextBlock, ToolUseBlock, etc.).
    """
    # Check for explicit type field first
    block_type = block.get("type", "")

    if block_type == "text":
        return TextBlock(text=block.get("text", ""))
    elif block_type == "tool_use":
        return ToolUseBlock(
            id=block.get("id", ""),
            name=block.get("name", ""),
            input=block.get("input", {}),
        )
    elif block_type == "tool_result":
        return ToolResultBlock(
            tool_use_id=block.get("tool_use_id", ""),
            content=block.get("content"),
            is_error=block.get("is_error"),
        )
    elif block_type == "thinking":
        return ThinkingBlock(
            thinking=block.get("thinking", ""),
            signature=block.get("signature", ""),
        )

    # Detect block type by fields (agent output doesn't always include "type")
    # ToolUseBlock: has 'id' and 'name' and 'input'
    if "id" in block and "name" in block and "input" in block:
        return ToolUseBlock(
            id=block["id"],
            name=block["name"],
            input=block["input"],
        )

    # ToolResultBlock: has 'tool_use_id'
    if "tool_use_id" in block:
        return ToolResultBlock(
            tool_use_id=block["tool_use_id"],
            content=block.get("content"),
            is_error=block.get("is_error"),
        )

    # ThinkingBlock: has 'thinking' and 'signature'
    if "thinking" in block and "signature" in block:
        return ThinkingBlock(
            thinking=block["thinking"],
            signature=block["signature"],
        )

    # TextBlock: has 'text'
    if "text" in block:
        return TextBlock(text=block["text"])

    # Unknown block type - wrap content as TextBlock
    return TextBlock(text=str(block))


def convert_message(raw: dict[str, Any]) -> Message:
    """Convert a raw message dict to a proper Message type.

    This allows using isinstance() checks and attribute access:

        async for message in query(prompt="Hello"):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

    Args:
        raw: Raw message dictionary from the agent output.

    Returns:
        Typed Message object (AssistantMessage, SystemMessage, ResultMessage, etc.).
    """
    # Check for subtype field to determine message type
    subtype = raw.get("subtype")

    if subtype == "init":
        # SystemMessage for init
        return SystemMessage(
            subtype=subtype,
            data=raw.get("data", raw),
        )
    elif subtype in ("success", "error"):
        # ResultMessage for completion status
        return ResultMessage(
            subtype=subtype,
            duration_ms=raw.get("duration_ms", 0),
            duration_api_ms=raw.get("duration_api_ms", 0),
            is_error=raw.get("is_error", subtype == "error"),
            num_turns=raw.get("num_turns", 0),
            session_id=raw.get("session_id", ""),
            total_cost_usd=raw.get("total_cost_usd"),
            usage=raw.get("usage"),
            result=raw.get("result"),
            structured_output=raw.get("structured_output"),
        )
    elif "content" in raw:
        # AssistantMessage with content blocks
        raw_content = raw.get("content", [])
        content = [
            _convert_content_block(block) if isinstance(block, dict) else block
            for block in raw_content
        ]
        return AssistantMessage(
            content=content,
            model=raw.get("model", ""),
            parent_tool_use_id=raw.get("parent_tool_use_id"),
            error=raw.get("error"),
        )
    elif "event" in raw:
        # StreamEvent
        return StreamEvent(
            uuid=raw.get("uuid", ""),
            session_id=raw.get("session_id", ""),
            event=raw.get("event", {}),
            parent_tool_use_id=raw.get("parent_tool_use_id"),
        )
    else:
        # Unknown format - wrap in SystemMessage
        return SystemMessage(
            subtype=subtype or "unknown",
            data=raw,
        )


__all__ = [
    "AssistantMessage",
    "ContentBlock",
    "HookCallback",
    "Message",
    "ResultMessage",
    "StreamEvent",
    "SystemMessage",
    "TextBlock",
    "ThinkingBlock",
    "ToolResultBlock",
    "ToolUseBlock",
    "ToolValidator",
    "UserMessage",
    "convert_message",
]
