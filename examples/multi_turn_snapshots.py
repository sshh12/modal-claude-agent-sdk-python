"""Multi-turn conversations with filesystem snapshots.

Demonstrates Modal's snapshot_filesystem() API to:
1. Run an agent query in a sandbox
2. Snapshot the filesystem state after the turn
3. Create a NEW sandbox from the snapshot for the next turn
4. Preserve both files AND conversation context across sandbox transitions

This differs from multi_turn.py which uses a single persistent sandbox.
Here, each turn runs in a completely fresh sandbox that starts from
the previous turn's filesystem snapshot.

Use cases:
- Checkpoint long-running tasks at each step
- Recovery from failures by restoring to a previous snapshot
- Share exact environment state across team members
- Create reproducible starting points for experiments
"""

import asyncio

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentClient,
    ModalAgentImage,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)


async def main():
    """Run multi-turn conversation with snapshots between each turn."""

    print("Modal Agents SDK - Multi-turn Snapshots Example")
    print("=" * 60)
    print()
    print("Each turn runs in a NEW sandbox created from the previous")
    print("turn's filesystem snapshot, preserving files across sandboxes.")
    print()

    # Define the conversation turns
    turns = [
        "Create /workspace/calculator.py with add and subtract functions.",
        "Add multiply and divide functions to calculator.py (handle div by zero).",
        "Create test_calculator.py with pytest tests and run them.",
    ]

    # Start with the default image
    current_image = ModalAgentImage.default()
    session_id: str | None = None
    snapshots: list[modal.Image] = []

    for i, prompt in enumerate(turns, start=1):
        print(f"\n{'=' * 60}")
        print(f"Turn {i}: {prompt[:50]}...")
        print("=" * 60)

        options = ModalAgentOptions(
            image=current_image,
            secrets=[modal.Secret.from_name("anthropic-key")],
            allowed_tools=["Bash", "Read", "Write", "Edit"],
            cwd="/workspace",
            resume=session_id,
        )

        async with ModalAgentClient(options=options) as client:
            # Run the query
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text = block.text
                            print(text[:300] + "..." if len(text) > 300 else text)
                        elif isinstance(block, ToolUseBlock):
                            print(f"  [tool] {block.name}")
                elif isinstance(msg, ResultMessage):
                    session_id = msg.session_id
                    print(f"\n[{msg.subtype}] Turn {i} complete")

            # Snapshot before the sandbox terminates
            print("[Taking snapshot...]")
            snapshot = await client.snapshot()
            snapshots.append(snapshot)
            print(f"[Snapshot: {snapshot.object_id[:30]}...]")

        # Context manager exit terminates sandbox automatically
        print("[Sandbox terminated]")

        # Next turn uses snapshot as base image
        current_image = ModalAgentImage(snapshot)

    # Summary
    print("\n" + "=" * 60)
    print("Complete! Created", len(snapshots), "snapshots:")
    for i, snap in enumerate(snapshots, 1):
        print(f"  Turn {i}: {snap.object_id[:40]}...")


if __name__ == "__main__":
    asyncio.run(main())
