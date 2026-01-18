"""Multi-agent example - define specialized sub-agents for delegated tasks.

This example demonstrates using the `agents` option to define custom sub-agents
that specialize in different tasks. The main agent can delegate to these
sub-agents based on the nature of the work.

Sub-agents have their own configurations including:
- description: What the agent specializes in
- allowed_tools: Which tools the agent can use
- system_prompt: Optional custom instructions for the agent
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

# Define specialized sub-agents for different tasks
AGENTS = {
    "code-reviewer": {
        "description": "Reviews code for bugs, style issues, security vulnerabilities, and suggests improvements. "
        "Specializes in analyzing existing code without making modifications.",
        "allowed_tools": ["Read", "Grep", "Glob"],
        "system_prompt": (
            "You are an expert code reviewer. Focus on:\n"
            "- Identifying bugs and potential issues\n"
            "- Code style and readability\n"
            "- Security vulnerabilities\n"
            "- Performance improvements\n"
            "- Best practices and design patterns\n"
            "Provide constructive feedback with specific line references."
        ),
    },
    "test-writer": {
        "description": "Writes comprehensive unit tests and integration tests for code. "
        "Creates test files following best practices for the detected testing framework.",
        "allowed_tools": ["Read", "Write", "Bash", "Glob"],
        "system_prompt": (
            "You are an expert test engineer. When writing tests:\n"
            "- Use appropriate testing frameworks (pytest for Python, jest for JS, etc.)\n"
            "- Cover edge cases and error conditions\n"
            "- Write clear test descriptions\n"
            "- Follow AAA pattern (Arrange, Act, Assert)\n"
            "- Aim for high code coverage"
        ),
    },
    "documentation-writer": {
        "description": "Writes and updates documentation including docstrings, README files, "
        "and API documentation. Ensures code is well-documented and easy to understand.",
        "allowed_tools": ["Read", "Write", "Glob"],
        "system_prompt": (
            "You are a technical writer specializing in code documentation. Focus on:\n"
            "- Clear and concise docstrings\n"
            "- Comprehensive README files\n"
            "- API documentation with examples\n"
            "- Usage guides and tutorials\n"
            "- Maintaining consistent documentation style"
        ),
    },
}


async def main():
    """Run an agent with specialized sub-agents for a code quality workflow."""
    # Configure options with sub-agents defined
    options = ModalAgentOptions(
        # Define the specialized sub-agents
        agents=AGENTS,
        # Main agent can use all tools plus delegate to sub-agents
        allowed_tools=[
            "Read",
            "Write",
            "Bash",
            "Glob",
            "Grep",
            # Sub-agents are available as tools with the "agent:" prefix
            "agent:code-reviewer",
            "agent:test-writer",
            "agent:documentation-writer",
        ],
        system_prompt=(
            "You are a senior software engineer with access to specialized sub-agents. "
            "Delegate tasks to the appropriate sub-agent based on their expertise:\n"
            "- Use 'code-reviewer' for reviewing and analyzing existing code\n"
            "- Use 'test-writer' for creating unit tests and integration tests\n"
            "- Use 'documentation-writer' for writing or updating documentation\n\n"
            "Coordinate between sub-agents to complete complex tasks efficiently."
        ),
        secrets=[modal.Secret.from_name("anthropic-key")],
    )

    # Prompt that demonstrates multi-agent delegation
    prompt = """
    Please perform a code quality review on the following Python module:

    1. First, have the code-reviewer analyze src/modal_agents_sdk/_client.py
       for any issues or improvements

    2. Based on the review, have the test-writer create appropriate unit tests
       if any are missing

    3. Finally, have the documentation-writer ensure the module has proper
       docstrings and documentation

    Summarize the findings and actions taken by each sub-agent.
    """

    print("Running multi-agent code quality workflow...")
    print("=" * 60)

    async for message in query(prompt, options=options):
        # Handle different message types using isinstance() checks
        if isinstance(message, SystemMessage):
            print(f"\n[system:{message.subtype}] Session initialized")
            print("-" * 40)

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Print assistant text responses
                    print(f"\n{block.text}")

                elif isinstance(block, ToolUseBlock):
                    # Show when tools (including sub-agents) are being used
                    tool_name = block.name
                    if tool_name.startswith("agent:"):
                        # Sub-agent invocation
                        agent_name = tool_name.replace("agent:", "")
                        print(f"\n[delegating to {agent_name}]")
                        # Show the task being delegated
                        if "task" in block.input:
                            task_preview = str(block.input["task"])[:100]
                            print(f"  Task: {task_preview}...")
                    else:
                        # Regular tool usage
                        print(f"[tool] {tool_name}({list(block.input.keys())})")

                elif isinstance(block, ToolResultBlock):
                    # Show truncated tool results
                    if isinstance(block.content, str):
                        result_preview = block.content[:200]
                        if len(block.content) > 200:
                            result_preview += "..."
                        print(f"[result] {result_preview}")

        elif isinstance(message, ResultMessage):
            print("\n" + "=" * 60)
            print(f"[{message.subtype}] Workflow completed")
            print(f"  Total turns: {message.num_turns}")
            if hasattr(message, "usage") and message.usage:
                print(f"  Tokens used: {message.usage}")


if __name__ == "__main__":
    asyncio.run(main())
