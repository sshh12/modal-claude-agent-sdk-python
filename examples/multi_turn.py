"""Multi-turn conversation example - maintain context across queries."""

import asyncio

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentClient,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
)


async def main():
    """Run a multi-turn conversation with persistent context."""
    options = ModalAgentOptions(
        system_prompt="You are a helpful coding assistant. Remember the context of our conversation.",
        secrets=[modal.Secret.from_name("anthropic-key")],
    )

    async with ModalAgentClient(options=options) as client:
        # First turn: create a project structure
        print("Turn 1: Creating project structure...")
        print("-" * 40)

        await client.query(
            "Create a Python project with a src/ directory containing "
            "an __init__.py and a calculator.py with basic math functions (add, subtract, multiply, divide)"
        )
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text = block.text
                        print(text[:300] + "..." if len(text) > 300 else text)
            elif isinstance(msg, ResultMessage):
                print(f"[{msg.subtype}] Completed turn 1")

        print("\n" + "=" * 50)
        print("Turn 2: Adding tests...")
        print("-" * 40)

        # Second turn: add tests (agent remembers the calculator module)
        await client.query(
            "Now create a tests/ directory with test_calculator.py that tests all the functions "
            "you just created. Use pytest conventions."
        )
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text = block.text
                        print(text[:300] + "..." if len(text) > 300 else text)
            elif isinstance(msg, ResultMessage):
                print(f"[{msg.subtype}] Completed turn 2")

        print("\n" + "=" * 50)
        print("Turn 3: Running tests...")
        print("-" * 40)

        # Third turn: run the tests
        await client.query("Run the tests and show me the results")
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(msg, ResultMessage):
                print(f"[{msg.subtype}] Completed turn 3")

        # Export conversation history
        print("\n" + "=" * 50)
        print("Conversation history:")
        print(client.export_history())


if __name__ == "__main__":
    asyncio.run(main())
