"""Cloud and region selection example - control where your agent runs.

This example demonstrates how to specify cloud provider and region for
sandbox execution. This is useful for:

- Compliance requirements: Data must stay in certain geographic regions
  (e.g., GDPR requires EU data to stay in EU regions)
- Latency optimization: Run close to your users or data sources
- Cost optimization: Some regions have lower pricing than others
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


async def run_with_aws_region():
    """Run an agent on AWS in a specific region.

    AWS regions follow the pattern: us-east-1, us-west-2, eu-west-1, etc.
    """
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        cloud="aws",
        region="us-east-1",  # Northern Virginia - typically lowest latency for US East
    )

    print("Running agent on AWS us-east-1...")
    print("-" * 50)

    async for message in query(
        "Print the current cloud environment info by running: "
        "echo 'Cloud: AWS' && echo 'Region: us-east-1' && date",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[assistant] {block.text[:200]}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}")
                elif isinstance(block, ToolResultBlock):
                    result = block.content[:100] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")
        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


async def run_with_gcp_region():
    """Run an agent on GCP in a specific region.

    GCP regions follow the pattern: us-central1, us-east1, europe-west1, etc.
    """
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        cloud="gcp",
        region="us-central1",  # Iowa - good central US location
    )

    print("\nRunning agent on GCP us-central1...")
    print("-" * 50)

    async for message in query(
        "Print the current cloud environment info by running: "
        "echo 'Cloud: GCP' && echo 'Region: us-central1' && date",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[assistant] {block.text[:200]}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}")
                elif isinstance(block, ToolResultBlock):
                    result = block.content[:100] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")
        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


async def run_with_multiple_regions():
    """Run an agent with multiple region options.

    When you specify multiple regions, Modal will select the best available
    region based on current capacity and your requirements. This is useful
    for maximizing availability and reducing queue times.
    """
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        cloud="aws",
        # Provide multiple regions for flexibility - Modal picks the best one
        region=["us-east-1", "us-west-2"],
    )

    print("\nRunning agent with multi-region flexibility (AWS us-east-1 or us-west-2)...")
    print("-" * 50)

    async for message in query(
        "Create a simple Python script that prints 'Hello from flexible region deployment!' "
        "and save it as hello_region.py, then run it.",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[assistant] {block.text[:200]}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}")
                elif isinstance(block, ToolResultBlock):
                    result = block.content[:100] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")
        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


async def run_for_eu_compliance():
    """Example: Run in EU region for GDPR compliance.

    When processing data subject to GDPR or other regional data protection
    regulations, you may need to ensure all processing happens within
    specific geographic boundaries.
    """
    options = ModalAgentOptions(
        secrets=[modal.Secret.from_name("anthropic-key")],
        cloud="aws",
        region="eu-west-1",  # Ireland - common choice for EU compliance
        system_prompt="You are processing EU user data. Ensure all operations complete within this session.",
    )

    print("\nRunning agent in EU region for compliance...")
    print("-" * 50)

    async for message in query(
        "Create a file called eu_data_processed.txt with the content "
        "'Data processed in EU region for GDPR compliance' and confirm the file was created.",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[assistant] {block.text[:200]}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool_use] {block.name}")
                elif isinstance(block, ToolResultBlock):
                    result = block.content[:100] if isinstance(block.content, str) else "..."
                    print(f"[tool_result] {result}")
        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


async def main():
    """Run all cloud/region examples.

    Common use cases for cloud and region selection:

    1. Compliance Requirements:
       - GDPR: Use eu-west-1, eu-central-1, or other EU regions
       - Data sovereignty: Ensure data stays within national boundaries
       - Industry regulations: Healthcare, finance may have location requirements

    2. Latency Optimization:
       - Run close to your users for faster response times
       - Run close to your data sources (databases, APIs)
       - Use multiple regions for global distribution

    3. Cost Optimization:
       - Some regions have lower compute costs
       - Consider data transfer costs between regions
       - Balance cost vs latency for your use case

    Available clouds:
       - "aws": Amazon Web Services
       - "gcp": Google Cloud Platform

    Common AWS regions:
       - us-east-1: N. Virginia (often cheapest, most capacity)
       - us-west-2: Oregon
       - eu-west-1: Ireland
       - eu-central-1: Frankfurt
       - ap-northeast-1: Tokyo

    Common GCP regions:
       - us-central1: Iowa
       - us-east1: South Carolina
       - europe-west1: Belgium
       - asia-east1: Taiwan
    """
    # Run a single example by default
    await run_with_aws_region()

    # Uncomment to run additional examples:
    # await run_with_gcp_region()
    # await run_with_multiple_regions()
    # await run_for_eu_compliance()


if __name__ == "__main__":
    asyncio.run(main())
