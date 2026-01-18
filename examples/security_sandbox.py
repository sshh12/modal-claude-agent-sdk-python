"""Security sandbox example - network isolation and security features.

This example demonstrates how to run agents in isolated environments with
restricted network access. This is useful for:

- Running untrusted or user-provided code safely
- Processing sensitive data without risk of exfiltration
- Ensuring compliance with data residency requirements
- Creating restricted execution environments

IMPORTANT: The agent needs network access to call the Anthropic API.
Using block_network=True will prevent the agent from working.
Instead, use cidr_allowlist to allow only the Anthropic API while
blocking all other network access.

Anthropic API IP ranges (from https://docs.anthropic.com/en/api/ip-addresses):
- IPv4: 160.79.104.0/23
- IPv6: 2607:6bc0::/48
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

# Anthropic API IP ranges - required for agent to function
# Source: https://docs.anthropic.com/en/api/ip-addresses
ANTHROPIC_API_CIDR = [
    "160.79.104.0/23",  # Anthropic API IPv4
    # Note: IPv6 (2607:6bc0::/48) may also be needed depending on your setup
]


async def run_secure_agent():
    """Run an agent that can ONLY reach the Anthropic API.

    This configuration blocks all network access except to Anthropic's API,
    preventing the agent from:
    - Making requests to arbitrary URLs
    - Exfiltrating data to external servers
    - Downloading malicious payloads
    - Accessing internal network resources

    The agent can still perform local operations like file I/O and computation.
    """
    # Configure sandbox to allow ONLY Anthropic API access
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        # Only allow connections to Anthropic API - everything else is blocked
        cidr_allowlist=ANTHROPIC_API_CIDR,
        system_prompt=(
            "You are a secure data processing assistant. "
            "You work in an isolated environment with restricted network access. "
            "You can only reach the Anthropic API - all other network access is blocked. "
            "Focus on local file operations and computations."
        ),
    )

    print("=" * 60)
    print("Running agent with RESTRICTED network (Anthropic API only)")
    print("=" * 60)
    print(f"Allowed CIDR ranges: {ANTHROPIC_API_CIDR}")
    print()

    # This prompt asks for work that can be done locally
    # The agent cannot fetch URLs or reach external services
    prompt = (
        "Create a Python script called data_processor.py that:\n"
        "1. Generates sample customer data (names, ages, purchase amounts)\n"
        "2. Calculates statistics (mean, median, total purchases by age group)\n"
        "3. Saves results to a JSON file called results.json\n"
        "Then run the script and show me the results."
    )

    async for message in query(prompt, options=options):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started in secure sandbox")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Truncate long responses for readability
                    text = block.text[:400] + "..." if len(block.text) > 400 else block.text
                    print(f"[assistant] {text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}({list(block.input.keys())})")
                elif isinstance(block, ToolResultBlock):
                    result = block.content[:150] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")

        elif isinstance(message, ResultMessage):
            print()
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


async def run_with_internal_network():
    """Run an agent that can reach Anthropic API + internal services.

    This is useful when the agent needs to:
    - Call the Anthropic API (required)
    - Access internal databases or services
    - Reach private APIs on your network

    While still blocking:
    - Public internet access
    - External API calls
    - Data exfiltration to unknown hosts
    """
    # Configure sandbox to allow Anthropic API + internal networks
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        cidr_allowlist=[
            # Required: Anthropic API
            "160.79.104.0/23",
            # Example: Your internal network ranges
            # Uncomment and modify these for your environment:
            # "10.0.0.0/8",        # Private network (Class A)
            # "172.16.0.0/12",     # Private network (Class B)
            # "192.168.0.0/16",    # Private network (Class C)
        ],
        system_prompt=(
            "You are an assistant with access to internal services. "
            "You can reach the AI API and internal network resources, "
            "but cannot access the public internet."
        ),
    )

    print()
    print("=" * 60)
    print("Running agent with Anthropic API + internal network access")
    print("=" * 60)
    print()

    # This task demonstrates local-only work
    prompt = (
        "Create a simple Python script called security_check.py that:\n"
        "1. Prints the current working directory\n"
        "2. Lists environment variables (excluding sensitive ones like API keys)\n"
        "3. Shows available disk space\n"
        "Run the script and show the results."
    )

    async for message in query(prompt, options=options):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started with network restrictions")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text[:400] + "..." if len(block.text) > 400 else block.text
                    print(f"[assistant] {text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}({list(block.input.keys())})")
                elif isinstance(block, ToolResultBlock):
                    result = block.content[:150] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")

        elif isinstance(message, ResultMessage):
            print()
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


async def main():
    """Demonstrate security sandbox features.

    Security configurations:

    1. cidr_allowlist with Anthropic API only:
       - Agent can call Claude API (required for operation)
       - All other network access is blocked
       - Best for maximum security while still allowing agent to work

    2. cidr_allowlist with Anthropic API + internal ranges:
       - Agent can call Claude API
       - Agent can reach internal services (databases, APIs, etc.)
       - Public internet is still blocked

    NOTE: block_network=True is NOT supported because the agent needs
    to reach the Anthropic API. Use cidr_allowlist instead.
    """
    print("Modal Agents SDK - Security Sandbox Examples")
    print("=" * 60)
    print()
    print("This example demonstrates network isolation features using cidr_allowlist.")
    print()
    print("The agent REQUIRES network access to the Anthropic API to function.")
    print("Using block_network=True will prevent the agent from working.")
    print()
    print("Anthropic API CIDR (required): 160.79.104.0/23")
    print("Source: https://docs.anthropic.com/en/api/ip-addresses")
    print()

    # Run the secure example (Anthropic API only)
    await run_secure_agent()

    # Run with internal network access
    await run_with_internal_network()

    print()
    print("=" * 60)
    print("Security sandbox examples completed!")
    print()
    print("Use cases for network restrictions:")
    print("  - Running untrusted or user-provided code")
    print("  - Processing sensitive/confidential data")
    print("  - Compliance with data residency requirements")
    print("  - Defense against prompt injection attacks")
    print("  - Preventing data exfiltration")
    print()
    print("Best practice: Use cidr_allowlist with Anthropic API CIDR")
    print("to allow the agent to work while blocking other network access.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
