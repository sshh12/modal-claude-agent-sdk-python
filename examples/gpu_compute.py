"""GPU compute example - run agents with GPU acceleration."""

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
    """Run an agent with GPU access for ML workloads."""
    # Create image with PyTorch and CUDA support
    image = ModalAgentImage.default().pip_install(
        "torch",
        "torchvision",
        "transformers",
    )

    options = ModalAgentOptions(
        image=image,
        gpu="A10G",  # Request an A10G GPU
        memory=16384,  # 16 GB memory
        system_prompt="You are an ML assistant with GPU access. PyTorch is available.",
        secrets=[modal.Secret.from_name("anthropic-key")],
        timeout=1800,  # 30 minutes for longer ML tasks
    )

    print("Running GPU-enabled agent...")

    async for message in query(
        "Create a Python script that checks if CUDA is available, "
        "prints GPU information, and runs a simple tensor operation on the GPU. "
        "Save it as gpu_test.py and run it.",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            print(f"[{message.subtype}] Session started")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[assistant] {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}")
        elif isinstance(message, ResultMessage):
            print(f"[{message.subtype}] Completed in {message.num_turns} turns")


if __name__ == "__main__":
    asyncio.run(main())
