"""Budget control example - demonstrate cost controls and budget limits.

This example shows how to:
1. Set conservative limits on agent execution (max_turns)
2. Track execution costs via ResultMessage.total_cost_usd
3. Handle graceful completion when limits are reached
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


async def run_with_turn_limit():
    """Run an agent with strict turn limits to control costs.

    The max_turns option limits how many conversation turns the agent
    can take, which directly impacts API usage and cost.
    """
    print("=" * 60)
    print("Example 1: Running with max_turns limit")
    print("=" * 60)

    # Configure with conservative turn limit
    # Lower max_turns = fewer API calls = lower cost
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        max_turns=3,  # Strict limit: only 3 turns allowed
    )

    # This task might normally take multiple turns, but we limit it
    prompt = (
        "Create a Python module with three files: "
        "utils.py with helper functions, "
        "config.py with configuration handling, "
        "and main.py that uses both. "
        "Then run main.py to test it."
    )

    print(f"Task: {prompt[:80]}...")
    print("Max turns allowed: 3")
    print("-" * 60)

    turn_count = 0
    final_cost = None

    async for message in query(prompt, options=options):
        if isinstance(message, SystemMessage):
            print("[system] Session initialized")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Truncate long text for readability
                    text = block.text
                    if len(text) > 150:
                        text = text[:150] + "..."
                    print(f"[assistant] {text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}")
                elif isinstance(block, ToolResultBlock):
                    print("[tool_result] (output received)")

        elif isinstance(message, ResultMessage):
            turn_count = message.num_turns
            final_cost = message.total_cost_usd

            print("-" * 60)
            print(f"[result] Status: {message.subtype}")
            print(f"[result] Turns used: {turn_count}")

            if final_cost is not None:
                print(f"[result] Total cost: ${final_cost:.6f}")
            else:
                print("[result] Total cost: (not available)")

            # Check if we hit the turn limit
            if turn_count >= 3:
                print("[info] Turn limit reached - agent stopped gracefully")

    return turn_count, final_cost


async def track_cost_across_tasks():
    """Track cumulative cost across multiple agent tasks.

    This demonstrates how to monitor spending by accumulating
    costs from each ResultMessage.
    """
    print("\n" + "=" * 60)
    print("Example 2: Tracking cumulative costs across tasks")
    print("=" * 60)

    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        max_turns=2,  # Keep each task short
    )

    # Simple tasks to demonstrate cost tracking
    tasks = [
        "Create a file called task1.txt with 'Hello from task 1'",
        "Create a file called task2.txt with 'Hello from task 2'",
        "List all .txt files in the current directory",
    ]

    cumulative_cost = 0.0
    budget_limit = 0.10  # Example budget limit: $0.10

    print(f"Budget limit: ${budget_limit:.2f}")
    print("-" * 60)

    for i, task in enumerate(tasks, 1):
        print(f"\nTask {i}: {task[:50]}...")

        # Check if we should continue based on budget
        if cumulative_cost >= budget_limit:
            print(f"[budget] Budget limit reached (${cumulative_cost:.6f} >= ${budget_limit:.2f})")
            print(f"[budget] Skipping remaining {len(tasks) - i + 1} tasks")
            break

        async for message in query(task, options=options):
            if isinstance(message, ResultMessage):
                task_cost = message.total_cost_usd or 0.0
                cumulative_cost += task_cost

                print(f"  [result] Task {i} completed in {message.num_turns} turns")
                print(f"  [result] Task cost: ${task_cost:.6f}")
                print(f"  [result] Cumulative cost: ${cumulative_cost:.6f}")

                # Warn if approaching budget limit
                if cumulative_cost > budget_limit * 0.8:
                    remaining = budget_limit - cumulative_cost
                    print(f"  [warning] Approaching budget limit! Remaining: ${remaining:.6f}")

    print("-" * 60)
    print(f"Final cumulative cost: ${cumulative_cost:.6f}")
    print(f"Budget utilization: {(cumulative_cost / budget_limit) * 100:.1f}%")

    return cumulative_cost


async def demonstrate_cost_reporting():
    """Demonstrate detailed cost reporting from ResultMessage.

    The ResultMessage contains comprehensive execution metrics
    including cost, duration, and usage statistics.
    """
    print("\n" + "=" * 60)
    print("Example 3: Detailed cost and usage reporting")
    print("=" * 60)

    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        max_turns=2,
    )

    prompt = "What is 2 + 2? Reply with just the number."
    print(f"Task: {prompt}")
    print("-" * 60)

    async for message in query(prompt, options=options):
        if isinstance(message, ResultMessage):
            print("\nExecution Report:")
            print(f"  Status: {message.subtype}")
            print(f"  Is Error: {message.is_error}")
            print(f"  Number of Turns: {message.num_turns}")
            print(f"  Duration (ms): {message.duration_ms}")
            print(f"  API Duration (ms): {message.duration_api_ms}")
            print(f"  Session ID: {message.session_id}")

            if message.total_cost_usd is not None:
                print(f"  Total Cost (USD): ${message.total_cost_usd:.6f}")

            if message.usage:
                print(f"  Usage: {message.usage}")

            if message.result:
                result_preview = str(message.result)[:100]
                print(f"  Result: {result_preview}...")


async def main():
    """Run all budget control examples."""
    print("Modal Agents SDK - Budget Control Examples")
    print("This demonstrates cost controls and budget management.\n")

    # Example 1: Turn limits
    _turns, _cost = await run_with_turn_limit()

    # Example 2: Cumulative cost tracking
    _total_cost = await track_cost_across_tasks()

    # Example 3: Detailed reporting
    await demonstrate_cost_reporting()

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("Key takeaways for budget control:")
    print("  1. Use max_turns to limit conversation length and API calls")
    print("  2. Monitor total_cost_usd from ResultMessage after each task")
    print("  3. Implement budget checks before starting new tasks")
    print("  4. Use detailed reporting for cost analysis and optimization")


if __name__ == "__main__":
    asyncio.run(main())
