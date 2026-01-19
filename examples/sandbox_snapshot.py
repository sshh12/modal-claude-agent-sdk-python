"""Sandbox snapshot example - save and restore sandbox filesystem state.

This example demonstrates Modal's filesystem snapshot feature to:
- Create a development environment with installed packages
- Snapshot it for fast reuse
- Restore from snapshot to skip setup time

Use cases:
- Pre-configured development environments
- Checkpoint long-running tasks
- Share consistent environments across team
- Fast iteration on complex setups

Note: This example requires access to the underlying Modal sandbox object,
which may require modifications to the SDK internals or use of Modal directly.
"""

import asyncio

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


async def create_environment_and_snapshot():
    """Create a development environment and demonstrate snapshotting concept."""

    print("Phase 1: Creating development environment...")
    print("=" * 50)

    # Create a custom image with pre-installed packages
    # This is similar to what a snapshot would provide
    base_image = (
        ModalAgentImage.default()
        .apt_install("git", "curl")
        .pip_install("requests", "pandas", "pytest", "black", "mypy")
        .run_commands("mkdir -p /workspace/src /workspace/tests")
    )

    options = ModalAgentOptions(
        image=base_image,
        secrets=[modal.Secret.from_name("anthropic-key")],
        allowed_tools=["Bash", "Write", "Read"],
        cwd="/workspace",
        system_prompt="You are setting up a Python development environment in /workspace.",
    )

    print("Setting up project structure...")

    async for message in query(
        "Set up a Python project:\n"
        "1. Verify pandas and pytest are installed (show versions)\n"
        "2. Create src/__init__.py\n"
        "3. Create src/calculator.py with add, subtract, multiply, divide functions\n"
        "4. Create tests/test_calculator.py with pytest tests\n"
        "5. List the project structure",
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    print(text[:300] + "..." if len(text) > 300 else text)
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}")
        elif isinstance(message, ResultMessage):
            print(f"\n[{message.subtype}] Environment setup complete")

    return base_image


async def use_prepared_environment(image):
    """Use the prepared environment for actual work."""

    print("\nPhase 2: Using prepared environment...")
    print("=" * 50)

    options = ModalAgentOptions(
        image=image,
        secrets=[modal.Secret.from_name("anthropic-key")],
        allowed_tools=["Bash", "Write", "Read", "Edit"],
        cwd="/workspace",
        system_prompt=(
            "You have a pre-configured Python environment with pandas, pytest, "
            "black, and mypy installed. The project structure is already set up."
        ),
    )

    # The environment is ready - we can start working immediately
    async for message in query(
        "The environment should be ready. Please:\n"
        "1. Show the installed packages (pip list | grep -E 'pandas|pytest')\n"
        "2. List the files in /workspace\n"
        "3. Run the tests with pytest\n"
        "4. Format the code with black",
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}")
        elif isinstance(message, ResultMessage):
            print(f"\n[{message.subtype}] Work completed")


async def demonstrate_modal_snapshot():
    """Show how Modal's native snapshot API works."""

    print("\nModal Snapshot API Reference:")
    print("=" * 50)
    print("""
To use Modal's filesystem snapshot feature directly:

    # Create a sandbox
    sb = modal.Sandbox.create(
        "python", "-c", "import pandas; print('ready')",
        app=app,
        image=my_image
    )

    # Do some setup work
    p = sb.exec("pip", "install", "some-package")
    p.wait()

    # Take a snapshot - returns an Image
    snapshot_image = sb.snapshot_filesystem()
    print(f"Snapshot ID: {snapshot_image.object_id}")

    # Later, create a new sandbox from the snapshot
    sb2 = modal.Sandbox.create(
        "python", "-c", "print('restored')",
        app=app,
        image=snapshot_image  # Use snapshot as base
    )

Benefits:
- Only stores filesystem differences from base image
- Fast cold starts when restoring
- Snapshots persist indefinitely
- Can be shared via snapshot IDs
""")


async def main():
    """Demonstrate sandbox snapshotting workflow."""

    print("Modal Agents SDK - Sandbox Snapshot Example")
    print("=" * 50)
    print()
    print("This example demonstrates environment preparation and reuse,")
    print("which is conceptually similar to Modal's snapshot feature.")
    print()

    # Create and configure environment
    prepared_image = await create_environment_and_snapshot()

    # Use the prepared environment
    await use_prepared_environment(prepared_image)

    # Show the native Modal API
    await demonstrate_modal_snapshot()

    print("\n" + "=" * 50)
    print("Snapshot workflow demonstration complete!")
    print()
    print("Key concepts:")
    print("  - ModalAgentImage: Pre-configure environments with packages")
    print("  - Modal snapshot_filesystem(): Save sandbox state at any point")
    print("  - Restore from snapshot: Fast startup with pre-configured state")
    print("  - Share snapshots: Use snapshot IDs across team/runs")


if __name__ == "__main__":
    asyncio.run(main())
