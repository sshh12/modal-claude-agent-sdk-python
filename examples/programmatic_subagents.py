"""Programmatic subagents example - define specialized agents in code.

This example demonstrates using the agents option to define custom subagents:
- Specialized agents for specific tasks
- Different tool sets per agent
- Different models for cost optimization
- Agent composition and delegation

The main agent can delegate tasks to specialized subagents using the Task tool.
"""

import asyncio

import modal

# AgentDefinition comes from the claude-agent-sdk package
from claude_agent_sdk import AgentDefinition

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)


async def main():
    """Run an orchestrator agent with specialized subagents."""

    print("Modal Agents SDK - Programmatic Subagents Example")
    print("=" * 60)

    # Define specialized subagents using AgentDefinition dataclass
    # Each agent has: description, prompt, tools (optional), model (optional)
    agents = {
        # Code review specialist - read-only, fast model
        "code-reviewer": AgentDefinition(
            description="Reviews Python code for bugs, style issues, and improvements",
            prompt=(
                "You are an expert Python code reviewer. When given code, analyze it for:\n"
                "- Bugs and potential errors\n"
                "- Style issues and PEP 8 compliance\n"
                "- Performance improvements\n"
                "- Security vulnerabilities\n\n"
                "Provide specific, actionable feedback with line references."
            ),
            tools=["Read", "Glob", "Grep"],  # Read-only tools
            model="haiku",  # Fast and cheap for reviews
        ),
        # Documentation writer - can read and write
        "doc-writer": AgentDefinition(
            description="Writes documentation, docstrings, and README files",
            prompt=(
                "You are a technical documentation specialist. Write clear, "
                "comprehensive documentation including:\n"
                "- Function and class docstrings (Google style)\n"
                "- README files with usage examples\n"
                "- Inline comments for complex logic\n\n"
                "Be concise but thorough. Use proper markdown formatting."
            ),
            tools=["Read", "Write", "Edit"],
            model="haiku",
        ),
        # Test writer - needs to read code and run tests
        "test-writer": AgentDefinition(
            description="Creates comprehensive pytest test cases for Python code",
            prompt=(
                "You are a testing expert. Write comprehensive pytest tests including:\n"
                "- Unit tests for each public function\n"
                "- Edge cases and boundary conditions\n"
                "- Error handling tests\n"
                "- Use fixtures and parametrize where appropriate\n\n"
                "Include docstrings explaining what each test verifies."
            ),
            tools=["Read", "Write", "Bash"],
            model="sonnet",  # Better reasoning for complex test design
        ),
    }

    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        allowed_tools=["Read", "Write", "Bash", "Task"],  # Task enables subagent delegation
        agents=agents,
        system_prompt=(
            "You are a development team lead coordinating a code improvement project.\n\n"
            "You have specialized subagents available:\n"
            "- code-reviewer: For analyzing code quality and finding issues\n"
            "- doc-writer: For writing documentation and docstrings\n"
            "- test-writer: For creating comprehensive test suites\n\n"
            "Delegate tasks to the appropriate specialist using the Task tool. "
            "Coordinate their work and summarize the results."
        ),
        max_turns=15,  # Allow enough turns for multi-agent coordination
    )

    # Sample code for the agents to work on
    sample_code = '''
def calculate_discount(price, discount_percent):
    if discount_percent > 100:
        return 0
    return price * (1 - discount_percent / 100)

def apply_bulk_discount(items, threshold=10):
    total = sum(item['price'] for item in items)
    if len(items) >= threshold:
        return calculate_discount(total, 15)
    return total

def format_price(amount):
    return f"${amount:.2f}"
'''

    prompt = f"""
I have this Python pricing module that needs improvement:

```python
{sample_code}
```

Please coordinate the following tasks:
1. Save this code to pricing.py
2. Have the code-reviewer analyze it for issues
3. Have the doc-writer add proper documentation
4. Have the test-writer create a test suite
5. Summarize all the improvements made by each specialist
"""

    print("\nSubagents defined:")
    for name, agent_def in agents.items():
        print(f"  - {name}: {agent_def.description[:50]}...")
    print()
    print("Starting coordinated development workflow...")
    print("-" * 60)

    async for message in query(prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    # Print with reasonable truncation
                    if len(text) > 400:
                        print(text[:400] + "\n... [truncated]")
                    else:
                        print(text)
                elif isinstance(block, ToolUseBlock):
                    if block.name == "Task":
                        agent_type = block.input.get("subagent_type", "unknown")
                        desc = block.input.get("description", "")
                        print(f"\n[DELEGATE -> {agent_type}] {desc}")
                    else:
                        print(f"[tool] {block.name}")
        elif isinstance(message, ResultMessage):
            print(f"\n[{message.subtype}] Completed in {message.num_turns} turns")
            if message.total_cost_usd:
                print(f"Total cost: ${message.total_cost_usd:.4f}")

    print("\n" + "=" * 60)
    print("Subagent workflow complete!")
    print()
    print("Key concepts demonstrated:")
    print("  - agents dict: Define specialized agents with custom prompts")
    print("  - Tool restrictions: Each agent has appropriate tool access")
    print("  - Model selection: Use cheaper models (haiku) for simpler tasks")
    print("  - Task delegation: Main agent coordinates specialist work")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
