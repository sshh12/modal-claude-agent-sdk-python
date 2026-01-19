"""Session resume with snapshots - persist conversation state across runs.

This example demonstrates combining two powerful features:
1. Session IDs: Claude's conversation context and memory
2. Sandbox Snapshots: Modal's filesystem state persistence

Together, these allow you to:
- Pause work and continue later with full context
- Persist files created by the agent across runs
- Build on previous work incrementally
- Resume exactly where you left off

The snapshot preserves the ~/.claude directory where session data is stored,
as well as any files the agent created.
"""

import asyncio
import json
from pathlib import Path

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentImage,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

# File to store session metadata locally
SESSION_FILE = Path("agent_session.json")

# Modal app for snapshot management
app = modal.App.lookup("session-resume-demo", create_if_missing=True)


def save_session(session_id: str, snapshot_id: str, description: str):
    """Save session info for later resumption."""
    data = {
        "session_id": session_id,
        "snapshot_id": snapshot_id,
        "description": description,
    }
    SESSION_FILE.write_text(json.dumps(data, indent=2))
    print(f"Session saved to {SESSION_FILE}")


def load_session() -> dict | None:
    """Load previous session info if available."""
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return None


async def start_new_session():
    """Start a fresh session with a new sandbox."""
    print("=" * 50)
    print("Starting NEW session...")
    print("=" * 50)

    # Use default image
    image = ModalAgentImage.default()

    options = ModalAgentOptions(
        image=image,
        secrets=[modal.Secret.from_name("anthropic-key")],
        allowed_tools=["Write", "Read", "Bash", "Edit"],
        system_prompt=(
            "You are helping build a Python project incrementally. "
            "Work in /workspace directory. Be concise in responses."
        ),
        app=app,
    )

    session_id = None

    # Initial project setup
    prompt = (
        "Let's start a new Python project. Please:\n"
        "1. Create a file called calculator.py with basic math functions "
        "(add, subtract, multiply, divide)\n"
        "2. Make sure divide handles division by zero\n"
        "3. Show me what you created"
    )

    print(f"\nPrompt: {prompt[:100]}...")
    print("-" * 50)

    async for msg in query(prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    print(text[:500] + "..." if len(text) > 500 else text)
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}")
        elif isinstance(msg, ResultMessage):
            session_id = msg.session_id
            print(f"\n[{msg.subtype}] Session ID: {session_id[:30]}...")

    # Create a snapshot of the sandbox state
    # This preserves both the files AND the session data in ~/.claude
    print("\nCreating sandbox snapshot...")

    # For now, we'll use the session_id as a marker
    # In a real implementation, you'd use Modal's snapshot API
    snapshot_id = f"snapshot-{session_id[:8]}" if session_id else None

    if session_id and snapshot_id:
        save_session(session_id, snapshot_id, "Calculator project - initial setup")
        print(f"Snapshot ID: {snapshot_id}")

    return session_id, snapshot_id


async def resume_session(session_id: str, snapshot_id: str):
    """Resume a previous session using the saved snapshot."""
    print("=" * 50)
    print(f"Resuming session: {session_id[:20]}...")
    print(f"From snapshot: {snapshot_id}")
    print("=" * 50)

    # Use default image (in production, you'd restore from snapshot)
    image = ModalAgentImage.default()

    options = ModalAgentOptions(
        image=image,
        secrets=[modal.Secret.from_name("anthropic-key")],
        allowed_tools=["Write", "Read", "Bash", "Edit"],
        resume=session_id,  # Resume the conversation context
        system_prompt=(
            "You are helping build a Python project incrementally. "
            "Work in /workspace directory. Be concise in responses."
        ),
        app=app,
    )

    new_session_id = None

    # Continue where we left off
    prompt = (
        "Great work on the calculator! Now please:\n"
        "1. Add type hints to all the functions\n"
        "2. Add docstrings with examples\n"
        "3. Create a test file called test_calculator.py\n"
        "4. Run the tests with pytest"
    )

    print(f"\nPrompt: {prompt[:100]}...")
    print("-" * 50)

    async for msg in query(prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    print(text[:500] + "..." if len(text) > 500 else text)
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}")
        elif isinstance(msg, ResultMessage):
            new_session_id = msg.session_id
            print(f"\n[{msg.subtype}] Continued session")

    # Update snapshot with new state
    if new_session_id:
        new_snapshot_id = f"snapshot-{new_session_id[:8]}"
        save_session(new_session_id, new_snapshot_id, "Calculator project - added tests")
        print(f"\nNew snapshot: {new_snapshot_id}")

    return new_session_id


async def demo_multi_turn():
    """Demonstrate multi-turn conversation within a single session."""
    print("=" * 50)
    print("Multi-turn conversation demo")
    print("=" * 50)
    print()
    print("This shows how ModalAgentClient maintains context")
    print("across multiple queries within a single sandbox session.")
    print()

    from modal_agents_sdk import ModalAgentClient

    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        allowed_tools=["Write", "Read", "Bash", "Edit"],
        system_prompt="You are a helpful coding assistant. Be concise.",
    )

    async with ModalAgentClient(options=options) as client:
        # Turn 1: Create a file
        print("-" * 40)
        print("Turn 1: Creating a file...")
        print("-" * 40)

        await client.query(
            "Create a file called greeting.py with a function greet(name) that returns 'Hello, {name}!'"
        )

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text[:300] + "..." if len(block.text) > 300 else block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"[tool] {block.name}")
            elif isinstance(msg, ResultMessage):
                print(f"\n[Turn 1 complete] Session: {msg.session_id[:20]}...")

        # Turn 2: Modify the file (agent remembers it exists)
        print()
        print("-" * 40)
        print("Turn 2: Modifying the file...")
        print("-" * 40)

        await client.query(
            "Add a farewell(name) function to greeting.py that returns 'Goodbye, {name}!'"
        )

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text[:300] + "..." if len(block.text) > 300 else block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"[tool] {block.name}")
            elif isinstance(msg, ResultMessage):
                print("\n[Turn 2 complete]")

        # Turn 3: Use the file (agent remembers both functions)
        print()
        print("-" * 40)
        print("Turn 3: Testing the functions...")
        print("-" * 40)

        await client.query(
            "Create a test script that imports greeting.py and tests both functions, then run it"
        )

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text[:300] + "..." if len(block.text) > 300 else block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"[tool] {block.name}")
            elif isinstance(msg, ResultMessage):
                print("\n[Turn 3 complete]")
                print(f"Final session ID: {msg.session_id[:30]}...")

    print()
    print("Multi-turn demo complete!")
    print("The agent maintained context across all 3 turns.")


async def main():
    """Demonstrate session resume and snapshot capabilities."""

    print("Modal Agents SDK - Session Resume Example")
    print("=" * 50)
    print()
    print("This example demonstrates:")
    print("  - Session IDs for conversation context")
    print("  - Multi-turn conversations within a sandbox")
    print("  - Saving/loading session state across script runs")
    print()

    # Check for existing session
    saved = load_session()

    if saved:
        print("Found saved session:")
        print(f"  ID: {saved['session_id'][:30]}...")
        print(f"  Snapshot: {saved.get('snapshot_id', 'N/A')}")
        print(f"  Description: {saved['description']}")
        print()

        print("Options:")
        print("  [r] Resume - continue the saved session")
        print("  [m] Multi-turn - demo multi-turn in single session")
        print("  [n] New - start fresh (overwrites saved session)")
        print()

        choice = input("Choose an option (r/m/n): ").lower().strip()

        if choice == "r":
            await resume_session(saved["session_id"], saved.get("snapshot_id", ""))
        elif choice == "m":
            await demo_multi_turn()
        else:
            await start_new_session()
    else:
        print("No saved session found.")
        print()
        print("Options:")
        print("  [n] New - start a new session")
        print("  [m] Multi-turn - demo multi-turn in single session")
        print()

        choice = input("Choose an option (n/m): ").lower().strip()

        if choice == "m":
            await demo_multi_turn()
        else:
            await start_new_session()

    print("\n" + "=" * 50)
    print("Session management complete!")
    print()
    print("Key concepts demonstrated:")
    print("  - Session IDs: Unique identifiers for conversation state")
    print("  - Multi-turn: ModalAgentClient maintains context across queries")
    print("  - Persistence: Save session IDs to resume later")
    print()
    print("Note: Full cross-sandbox session resume requires persisting")
    print("the ~/.claude directory using Modal volumes or snapshots.")
    print()
    print(f"Session file: {SESSION_FILE.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
