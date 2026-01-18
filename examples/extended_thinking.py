"""Extended thinking example - complex reasoning with visible thought process.

This example demonstrates how to use Claude's extended thinking capabilities
for complex multi-step reasoning problems. Extended thinking allows Claude
to show its step-by-step reasoning process before providing a final answer.

Extended thinking is particularly useful for:
- Complex math word problems
- Logic puzzles and riddles
- Multi-step planning problems
- Code debugging with detailed analysis
- Strategic decision making
"""

import asyncio

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    query,
)

# A complex logic puzzle that benefits from step-by-step reasoning
COMPLEX_REASONING_PROMPT = """
Solve this logic puzzle step by step:

Five friends (Alice, Bob, Carol, Dave, and Eve) each have a different favorite
programming language (Python, Rust, Go, TypeScript, and Java) and work at
different companies (Google, Meta, Apple, Microsoft, and Amazon).

Clues:
1. Alice works at Google and doesn't use Python or Java.
2. The person who uses Rust works at Amazon.
3. Bob uses TypeScript but doesn't work at Meta or Apple.
4. Carol doesn't work at Microsoft and doesn't use Go.
5. Dave works at Meta.
6. The person at Apple uses Python.
7. Eve doesn't use Java.
8. The person who uses Go works at Microsoft.

Determine each person's favorite language and workplace.
Explain your reasoning at each step.
"""


async def main():
    """Run a complex reasoning task with extended thinking enabled.

    This demonstrates how Claude processes complex problems with visible
    reasoning steps captured in ThinkingBlock content.
    """
    # Configure options for extended thinking
    # Using a model that supports extended thinking capabilities
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        # Use a model that supports extended thinking
        # Claude 3.5 Sonnet and Claude 3 Opus support thinking
        model="claude-sonnet-4-20250514",
        system_prompt=(
            "You are an expert logical reasoner. When solving complex problems, "
            "think through each step carefully and show your reasoning process. "
            "Break down problems into smaller parts and validate each conclusion "
            "before moving to the next step."
        ),
        # Limit tools since this is a pure reasoning task
        allowed_tools=[],
    )

    print("=" * 70)
    print("EXTENDED THINKING EXAMPLE: Logic Puzzle Solver")
    print("=" * 70)
    print("\nSending complex logic puzzle to Claude...")
    print("-" * 70)
    print(COMPLEX_REASONING_PROMPT)
    print("-" * 70)
    print("\nProcessing with extended thinking...\n")

    thinking_blocks_found = []
    text_blocks_found = []

    async for message in query(COMPLEX_REASONING_PROMPT, options=options):
        # Handle different message types using isinstance() checks
        if isinstance(message, SystemMessage):
            print(f"[system:{message.subtype}] Session initialized")

        elif isinstance(message, AssistantMessage):
            # Iterate through content blocks to find thinking and text
            for block in message.content:
                if isinstance(block, ThinkingBlock):
                    # ThinkingBlock contains the model's reasoning process
                    # This shows Claude's internal chain-of-thought
                    thinking_blocks_found.append(block)
                    print("\n" + "=" * 70)
                    print("THINKING PROCESS (Extended Thinking Block)")
                    print("=" * 70)
                    # Display thinking content (may be lengthy for complex problems)
                    thinking_text = block.thinking
                    if len(thinking_text) > 2000:
                        print(thinking_text[:2000])
                        print(f"\n... [truncated, {len(thinking_text)} total characters]")
                    else:
                        print(thinking_text)
                    print("=" * 70 + "\n")

                elif isinstance(block, TextBlock):
                    # TextBlock contains the final response
                    text_blocks_found.append(block)
                    print("\n" + "-" * 70)
                    print("FINAL ANSWER")
                    print("-" * 70)
                    print(block.text)
                    print("-" * 70)

        elif isinstance(message, ResultMessage):
            print(f"\n[result:{message.subtype}] Completed in {message.num_turns} turns")
            if message.total_cost_usd:
                print(f"[cost] ${message.total_cost_usd:.4f}")
            if message.usage:
                print(f"[usage] {message.usage}")

    # Summary of what we captured
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Thinking blocks captured: {len(thinking_blocks_found)}")
    print(f"Text blocks captured: {len(text_blocks_found)}")

    if thinking_blocks_found:
        total_thinking_chars = sum(len(b.thinking) for b in thinking_blocks_found)
        print(f"Total thinking content: {total_thinking_chars} characters")

    if text_blocks_found:
        total_text_chars = sum(len(b.text) for b in text_blocks_found)
        print(f"Total response content: {total_text_chars} characters")


if __name__ == "__main__":
    asyncio.run(main())
