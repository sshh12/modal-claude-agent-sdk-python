"""Resource limits example - fine-grained control over sandbox resources.

This example demonstrates how to configure CPU, memory, and timeout settings
for sandbox execution. Proper resource configuration ensures your agent has
enough resources for the task while avoiding unnecessary costs.

Resource Configuration Guidelines:

CPU (cpu parameter):
- Default: Modal's default allocation (typically 0.25-1 core)
- Increase for: Parallel processing, compilation, CPU-intensive computations
- Examples: Building projects (2-4 cores), data processing (2-8 cores)

Memory (memory parameter, in MiB):
- Default: Modal's default allocation (typically 256-512 MiB)
- Increase for: Large datasets, ML model loading, memory-intensive operations
- Examples: Data analysis (4096-8192), ML inference (8192-16384)

Timeout (timeout parameter, in seconds):
- Default: 3600 seconds (1 hour)
- Set based on your expected maximum execution time
- Add buffer for retries and unexpected delays

Idle Timeout (idle_timeout parameter, in seconds):
- Default: None (no idle timeout)
- Useful for: Interactive sessions, long-running agents
- Terminates sandbox after period of inactivity to save costs
"""

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
    """Run an agent with custom resource limits.

    This example configures:
    - 2 CPU cores for parallel operations
    - 4 GB RAM for data processing
    - 10 minute max execution time
    - 1 minute idle timeout for cost efficiency
    """
    # Configure resource limits for the sandbox
    options = ModalAgentOptions(
        # CPU allocation: 2 cores
        # Useful when the agent needs to:
        # - Run parallel processes (e.g., npm install, cargo build)
        # - Execute multi-threaded computations
        # - Perform CPU-intensive tasks like compilation
        cpu=2.0,
        # Memory allocation: 4096 MiB (4 GB)
        # Useful when the agent needs to:
        # - Process large files or datasets
        # - Load large libraries or models
        # - Work with memory-intensive applications
        memory=4096,
        # Execution timeout: 600 seconds (10 minutes)
        # Set this based on your expected task duration
        # Add buffer time for retries or unexpected delays
        # Default is 3600 seconds (1 hour)
        timeout=600,
        # Idle timeout: 60 seconds
        # Sandbox terminates after 1 minute of inactivity
        # Useful for:
        # - Cost optimization: don't pay for idle time
        # - Interactive sessions that may pause between actions
        # - Long-running agents with variable activity
        idle_timeout=60,
        # Anthropic API key secret
        secrets=[modal.Secret.from_name("anthropic-key")],
        # Custom system prompt explaining the resource context
        system_prompt=(
            "You are an assistant running in a sandbox with custom resource limits: "
            "2 CPU cores and 4 GB RAM. You can handle moderately intensive tasks."
        ),
    )

    print("Running agent with custom resource limits...")
    print("  CPU: 2 cores")
    print("  Memory: 4096 MiB (4 GB)")
    print("  Timeout: 600 seconds (10 minutes)")
    print("  Idle timeout: 60 seconds")
    print()

    # Run a task that benefits from the extra resources
    # This task processes data and benefits from extra CPU/memory
    async for message in query(
        "Create a Python script that demonstrates the available resources: "
        "1) Check and print the number of CPU cores available "
        "2) Check and print the total and available memory "
        "3) Create a simple multi-threaded task using ThreadPoolExecutor "
        "Save as resource_check.py and run it.",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Truncate long text for readability
                    text = block.text[:300] + "..." if len(block.text) > 300 else block.text
                    print(f"[assistant] {text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}({list(block.input.keys())})")
                elif isinstance(block, ToolResultBlock):
                    # Show truncated result
                    result = block.content[:200] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")

        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


async def example_configurations():
    """Show common resource configurations for different use cases.

    These are examples only - not executed in this script.
    """
    print("\n--- Common Resource Configurations ---\n")

    # Configuration 1: Light tasks (default-like)
    light_config = ModalAgentOptions(
        cpu=0.5,
        memory=512,
        timeout=300,  # 5 minutes
        secrets=[modal.Secret.from_name("anthropic-key")],
    )
    print("Light tasks (simple file operations, small scripts):")
    print(f"  CPU: {light_config.cpu}, Memory: {light_config.memory} MiB, Timeout: {light_config.timeout}s")

    # Configuration 2: Build/compile tasks
    build_config = ModalAgentOptions(
        cpu=4.0,  # More cores for parallel compilation
        memory=8192,  # 8 GB for build artifacts
        timeout=1800,  # 30 minutes for long builds
        secrets=[modal.Secret.from_name("anthropic-key")],
    )
    print("\nBuild/compile tasks (npm install, cargo build, make):")
    print(f"  CPU: {build_config.cpu}, Memory: {build_config.memory} MiB, Timeout: {build_config.timeout}s")

    # Configuration 3: Data processing
    data_config = ModalAgentOptions(
        cpu=2.0,
        memory=16384,  # 16 GB for large datasets
        timeout=3600,  # 1 hour for long processing
        idle_timeout=120,  # 2 minutes idle timeout
        secrets=[modal.Secret.from_name("anthropic-key")],
    )
    print("\nData processing (pandas, large files):")
    print(f"  CPU: {data_config.cpu}, Memory: {data_config.memory} MiB, Timeout: {data_config.timeout}s")

    # Configuration 4: Interactive/long-running
    interactive_config = ModalAgentOptions(
        cpu=1.0,
        memory=2048,
        timeout=7200,  # 2 hours max
        idle_timeout=300,  # 5 minutes idle timeout
        secrets=[modal.Secret.from_name("anthropic-key")],
    )
    print("\nInteractive/long-running sessions:")
    print(f"  CPU: {interactive_config.cpu}, Memory: {interactive_config.memory} MiB, Timeout: {interactive_config.timeout}s")
    print(f"  Idle timeout: {interactive_config.idle_timeout}s")


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())

    # Show example configurations (informational only)
    asyncio.run(example_configurations())
