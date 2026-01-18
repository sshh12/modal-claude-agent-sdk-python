"""Network File System example - use Modal NFS for shared storage across sandboxes.

NetworkFileSystem (NFS) provides concurrent read/write access from multiple sandboxes,
making it ideal for:
- Shared workspaces where multiple agents collaborate
- Real-time data sharing between parallel tasks
- Scenarios requiring simultaneous access to the same files

Key difference from Volumes:
- NFS: Concurrent read/write from multiple sandboxes simultaneously
- Volumes: Better for single-sandbox persistence, requires commit/reload for sharing
"""

import asyncio

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    query,
)


async def main():
    """Demonstrate NetworkFileSystem for shared storage across sandbox instances."""
    # Create or get a NetworkFileSystem for shared storage
    # NFS allows concurrent read/write access from multiple sandboxes
    nfs = modal.NetworkFileSystem.from_name("shared-workspace", create_if_missing=True)

    options = ModalAgentOptions(
        # Mount the NFS to /shared - this path will be accessible across all sandboxes
        network_file_systems={"/shared": nfs},
        cwd="/shared",  # Work directly in the shared directory
        system_prompt=(
            "You are working in a shared workspace at /shared. "
            "This directory uses a NetworkFileSystem, which means multiple sandboxes "
            "can read and write to it simultaneously. Always save your work to /shared."
        ),
        secrets=[modal.Secret.from_name("anthropic-key")],
    )

    # First task: Write a file to the shared storage
    print("Task 1: Writing to shared NetworkFileSystem...")
    print("-" * 50)

    async for message in query(
        "Create a file called shared_data.txt in the current directory with the content: "
        "'This file was created in the shared workspace and can be accessed by multiple sandboxes.'",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    print(f"[assistant] {text[:200]}{'...' if len(text) > 200 else ''}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}")

        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")

    print("\n" + "=" * 50)
    print("Task 2: Reading from shared NetworkFileSystem (simulating another sandbox)...")
    print("-" * 50)

    # Second task: Read the file from another "sandbox" session
    # In a real scenario, this could be a completely different sandbox instance
    # running in parallel, and it would still have access to the same data
    async for message in query(
        "List all files in the current directory and read the contents of shared_data.txt",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    print(f"[assistant] {text[:300]}{'...' if len(text) > 300 else ''}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}")

        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")

    print("\n" + "=" * 50)
    print("NetworkFileSystem vs Volume comparison:")
    print("-" * 50)
    print("NetworkFileSystem (NFS):")
    print("  - Concurrent read/write from multiple sandboxes")
    print("  - Changes visible immediately to all connected sandboxes")
    print("  - Ideal for shared workspaces and collaborative tasks")
    print()
    print("Volume:")
    print("  - Optimized for single-sandbox persistence")
    print("  - Requires commit/reload to share changes between sandboxes")
    print("  - Better performance for large file operations in isolation")


if __name__ == "__main__":
    asyncio.run(main())
