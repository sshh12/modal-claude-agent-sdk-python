"""Custom tools example - configure MCP servers for additional capabilities."""

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
    """Run an agent with custom MCP tools configured."""
    # Configure MCP servers for additional tools
    # Note: These servers run inside the sandbox
    options = ModalAgentOptions(
        mcp_servers={
            # Filesystem server for enhanced file operations
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
            },
        },
        # Restrict to specific tools for safety
        allowed_tools=[
            "Read",
            "Write",
            "Bash",
            "Glob",
            "mcp__filesystem__read_file",
            "mcp__filesystem__write_file",
            "mcp__filesystem__list_directory",
        ],
        secrets=[modal.Secret.from_name("anthropic-key")],
    )

    print("Running agent with MCP tools...")

    async for message in query(
        "Use the available tools to create a project structure with:\n"
        "- src/main.py with a hello world function\n"
        "- src/utils.py with some utility functions\n"
        "- README.md with project documentation\n"
        "Then list all the files you created.",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}")
        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


if __name__ == "__main__":
    asyncio.run(main())
