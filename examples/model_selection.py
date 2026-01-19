"""Model selection example - choose different Claude models for different use cases.

This example demonstrates how to use the `model` option to select different
Claude models depending on your task requirements:

- Faster/cheaper models (like Haiku) for simple, quick tasks
- More capable models (like Sonnet or Opus) for complex reasoning

Trade-offs to consider:
- Speed: Smaller models respond faster
- Cost: Smaller models are cheaper per token
- Capability: Larger models handle complex reasoning better
- Quality: Larger models produce more nuanced outputs

Available models (as of 2024):
- claude-3-5-haiku-latest: Fast and efficient for simple tasks
- claude-sonnet-4-20250514: Balanced performance and capability
- claude-opus-4-20250514: Most capable for complex reasoning
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


async def run_with_model(task: str, model: str, description: str) -> dict:
    """Run a task with a specific model and return timing/cost info.

    Args:
        task: The prompt to send to the agent.
        model: The model identifier to use.
        description: A description of the task for logging.

    Returns:
        A dict with model, duration_ms, total_cost_usd, and num_turns.
    """
    print(f"\n{'=' * 60}")
    print(f"Task: {description}")
    print(f"Model: {model}")
    print(f"{'=' * 60}")

    options = ModalAgentOptions(
        model=model,
        secrets=[modal.Secret.from_name("anthropic-key")],
        # Limit tools for these examples
        allowed_tools=["Read", "Write", "Bash", "Glob"],
    )

    result_info = {
        "model": model,
        "duration_ms": 0,
        "total_cost_usd": None,
        "num_turns": 0,
    }

    async for message in query(task, options=options):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Truncate long responses for readability
                    text = block.text[:300] + "..." if len(block.text) > 300 else block.text
                    print(f"[assistant] {text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}({list(block.input.keys())})")
                elif isinstance(block, ToolResultBlock):
                    result = block.content[:100] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")

        elif isinstance(message, ResultMessage):
            result_info["duration_ms"] = message.duration_ms
            result_info["total_cost_usd"] = message.total_cost_usd
            result_info["num_turns"] = message.num_turns
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")

    return result_info


async def main():
    """Compare different models for simple vs complex tasks."""

    # Store results for comparison
    results = []

    # =========================================================================
    # Task 1: Simple task - good fit for a fast, efficient model
    # =========================================================================
    # Haiku is ideal for straightforward tasks that don't require deep reasoning.
    # It's faster and more cost-effective for simple operations.

    simple_task = (
        "Create a file called greeting.txt with the content 'Hello, World!' "
        "and then read it back to confirm it was created correctly."
    )

    result1 = await run_with_model(
        task=simple_task,
        model="claude-3-5-haiku-latest",
        description="Simple file creation (using Haiku - fast/cheap)",
    )
    results.append(result1)

    # =========================================================================
    # Task 2: Complex reasoning task - benefits from a more capable model
    # =========================================================================
    # Sonnet or Opus are better for tasks requiring:
    # - Multi-step reasoning
    # - Code analysis
    # - Complex problem solving
    # - Nuanced understanding

    complex_task = (
        "Write a Python script at /workspace/fibonacci.py that implements "
        "three different approaches to calculate Fibonacci numbers:\n"
        "1. Recursive (simple but inefficient)\n"
        "2. Memoized (recursive with caching)\n"
        "3. Iterative (most efficient)\n\n"
        "Include docstrings, type hints, and a main block that benchmarks "
        "all three approaches for n=30, printing the time taken for each."
    )

    result2 = await run_with_model(
        task=complex_task,
        model="claude-sonnet-4-20250514",
        description="Complex code generation (using Sonnet - balanced)",
    )
    results.append(result2)

    # =========================================================================
    # Summary: Compare timing and cost
    # =========================================================================
    print("\n" + "=" * 60)
    print("SUMMARY: Model Comparison")
    print("=" * 60)

    for result in results:
        cost_str = f"${result['total_cost_usd']:.6f}" if result["total_cost_usd"] else "N/A"
        duration_str = f"{result['duration_ms'] / 1000:.2f}s" if result["duration_ms"] else "N/A"
        print(f"\nModel: {result['model']}")
        print(f"  Duration: {duration_str}")
        print(f"  Cost: {cost_str}")
        print(f"  Turns: {result['num_turns']}")

    print("\n" + "-" * 60)
    print("Key Takeaways:")
    print("- Use Haiku for simple, quick tasks (file ops, simple queries)")
    print("- Use Sonnet for balanced performance (most general tasks)")
    print("- Use Opus for complex reasoning (analysis, difficult problems)")
    print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
