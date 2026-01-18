"""Hooks and monitoring example - observe agent behavior."""

import asyncio
from datetime import datetime

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)


def log_tool_use(tool_name: str, tool_input: dict) -> None:
    """Log when a tool is used."""
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] TOOL: {tool_name}")
    print(f"  Input: {tool_input}")


async def main():
    """Run an agent with hooks for monitoring tool usage."""
    # Note: Hooks in this SDK are configured via the options but execute
    # inside the sandbox. For local monitoring, you can observe the
    # streamed messages.

    options = ModalAgentOptions(
        system_prompt="You are a helpful assistant. Explain what you're doing as you work.",
        max_turns=5,  # Limit turns for this example
        secrets=[modal.Secret.from_name("anthropic-key")],
    )

    print("Running agent with monitoring...")
    print("=" * 50)

    tool_count = 0
    message_count = 0

    async for message in query(
        "Create a simple Python script that prints 'Hello, World!' and save it as hello.py. "
        "Then run it to verify it works.",
        options=options,
    ):
        message_count += 1

        if isinstance(message, SystemMessage):
            print(f"\n[Message {message_count}] Type: {message.subtype}")

        elif isinstance(message, AssistantMessage):
            print(f"\n[Message {message_count}] Type: assistant")
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    tool_count += 1
                    print(f"  Tool #{tool_count}: {block.name}")
                    input_preview = str(block.input)[:100]
                    print(f"    Input: {input_preview}...")
                elif isinstance(block, ToolResultBlock):
                    content = block.content[:50] if isinstance(block.content, str) else "..."
                    print(f"  Tool Result: {content}")
                elif isinstance(block, TextBlock):
                    text_preview = block.text[:200] if len(block.text) > 200 else block.text
                    print(f"  Text: {text_preview}")

        elif isinstance(message, ResultMessage):
            print(f"\n[Message {message_count}] Type: {message.subtype}")
            print(f"  Duration: {message.duration_ms}ms")

    print("\n" + "=" * 50)
    print(f"Summary: {message_count} messages, {tool_count} tool uses")


if __name__ == "__main__":
    asyncio.run(main())
