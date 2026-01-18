"""Quick start example - simplest usage of Modal Agents SDK."""

import asyncio

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


async def main():
    """Run a simple agent query."""
    # Configure with your Anthropic API key secret
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
    )

    print("Running agent to create hello.txt...")

    async for message in query(
        "Create a file called hello.txt with the content 'Hello from Modal!'",
        options=options,
    ):
        # Use isinstance() to handle different message types cleanly
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[assistant] {block.text[:200]}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}({list(block.input.keys())})")
                elif isinstance(block, ToolResultBlock):
                    result = block.content[:100] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")

        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


if __name__ == "__main__":
    asyncio.run(main())
