"""Host Modal Functions as Tools - deploy compute functions as agent tools.

This example demonstrates how to expose deployed Modal functions as host-side
tools for Claude agents. This enables agents to offload compute-intensive
work to separate Modal containers.

Prerequisites:
1. Deploy the Modal function first:
   modal deploy examples/modal_compute_functions.py

2. Then run the example:
   python examples/host_modal_functions_as_tools.py

Architecture:
- Modal function: Defined in modal_compute_functions.py, deployed separately
- Host tool: Runs on your machine, proxies calls to the Modal function
- Agent: Runs in a Modal sandbox, calls the host tool
"""

import asyncio
import json

import modal

from modal_agents_sdk import (
    AssistantMessage,
    HostTool,
    HostToolServer,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)


# Create a host tool that calls the deployed Modal function
async def fibonacci_tool_handler(args: dict) -> dict:
    """Host-side handler that proxies to the Modal function."""
    try:
        # Look up the deployed function by name
        remote_func = modal.Function.from_name("agent-compute-tools", "compute_fibonacci")
        result = await remote_func.remote.aio(n=args["n"])
        return {"content": [{"type": "text", "text": json.dumps(result)}]}
    except modal.exception.NotFoundError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Function not deployed. Run: modal deploy examples/modal_compute_functions.py",
                }
            ],
            "is_error": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "is_error": True,
        }


# Create the HostTool
fibonacci_tool = HostTool(
    name="compute_fibonacci",
    description="Compute the nth Fibonacci number using a Modal function",
    input_schema={
        "type": "object",
        "properties": {
            "n": {"type": "integer", "description": "The position in the Fibonacci sequence"}
        },
        "required": ["n"],
    },
    handler=fibonacci_tool_handler,
)

# Create a HostToolServer
compute_tools_server = HostToolServer(
    name="modal-compute",
    tools=[fibonacci_tool],
)


async def main():
    """Run an agent with a Modal function tool."""

    print("Modal Functions as Tools Example")
    print("=" * 60)
    print("Deploy the function first with:")
    print("  modal deploy examples/modal_compute_functions.py")
    print()
    print("Available tool:", fibonacci_tool.name)
    print("=" * 60)
    print()

    options = ModalAgentOptions(
        host_tools=[compute_tools_server],
        secrets=[modal.Secret.from_name("anthropic-key")],
        max_turns=5,
    )

    prompt = "Calculate the 20th Fibonacci number using the compute_fibonacci tool."

    print(f"Prompt: {prompt}\n")
    print("-" * 60)

    async for message in query(prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"\n[Assistant] {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"\n[Tool Call] {block.name}: {block.input}")
                elif isinstance(block, ToolResultBlock):
                    content = (
                        block.content if isinstance(block.content, str) else str(block.content)
                    )
                    status = "ERROR" if block.is_error else "OK"
                    print(f"[Tool Result] [{status}] {content}")

        elif isinstance(message, ResultMessage):
            print(f"\n\n[{message.subtype}] Completed in {message.num_turns} turns")


if __name__ == "__main__":
    asyncio.run(main())
