"""Custom image example - customize the sandbox container."""

import asyncio

import modal

from modal_agents_sdk import (
    AssistantMessage,
    ModalAgentImage,
    ModalAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    query,
)


async def main():
    """Run an agent with a custom image containing data science tools."""
    # Create a custom image with additional packages
    image = (
        ModalAgentImage.default()
        .pip_install(
            "pandas",
            "numpy",
            "matplotlib",
            "scikit-learn",
        )
        .apt_install("graphviz")
    )

    options = ModalAgentOptions(
        image=image,
        system_prompt="You are a data science assistant. Use pandas and numpy for analysis.",
        secrets=[modal.Secret.from_name("anthropic-key")],
    )

    print("Running data analysis agent...")

    async for message in query(
        "Create a simple Python script that generates random data with numpy "
        "and calculates basic statistics with pandas. Save it as analysis.py",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[assistant] {block.text[:300]}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}")
        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


if __name__ == "__main__":
    asyncio.run(main())
