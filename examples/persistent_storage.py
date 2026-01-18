"""Persistent storage example - use Modal volumes for data persistence."""

import asyncio

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)


async def main():
    """Run agents that persist data across executions."""
    # Create or get a volume for persistent storage
    data_volume = modal.Volume.from_name("agent-workspace", create_if_missing=True)

    options = ModalAgentOptions(
        volumes={"/data": data_volume},
        cwd="/data",  # Work directly in the persistent volume
        system_prompt="Always save files in the current working directory, not in /tmp. The current directory is /data which is a persistent volume.",
        secrets=[modal.Secret.from_name("anthropic-key")],
    )

    # First run: create some files
    print("First run: Creating project files...")
    async for message in query(
        "Create a simple Python project in the CURRENT DIRECTORY (not /tmp) with:\n"
        "1. A main.py file with a hello world function\n"
        "2. A utils.py file with a helper function\n"
        "3. A README.md describing the project\n"
        "Save all files in the current working directory so they persist.",
        options=options,
    ):
        if isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    print(text[:200] + "..." if len(text) > 200 else text)

    print("\n" + "=" * 50)
    print("Second run: Checking persisted files...")

    # Second run: verify files persisted
    async for message in query(
        "List all files in the current directory and show their contents",
        options=options,
    ):
        if isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    print(text[:500] + "..." if len(text) > 500 else text)


if __name__ == "__main__":
    asyncio.run(main())
