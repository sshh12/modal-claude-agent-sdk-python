"""The query() function for simple agent execution."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from ._options import ModalAgentOptions
from ._sandbox import SandboxManager
from ._types import Message, convert_message

if TYPE_CHECKING:
    pass


async def query(
    prompt: str,
    *,
    options: ModalAgentOptions | None = None,
) -> AsyncIterator[Message]:
    """Execute a Claude agent query in a Modal sandbox.

    This is the simplest way to run an agent. The function creates a sandbox,
    executes the query, and streams the results.

    Args:
        prompt: The prompt to send to the agent.
        options: Optional configuration options. Uses defaults if not provided.

    Yields:
        Message objects from the agent response (AssistantMessage, SystemMessage,
        ResultMessage, etc.). Use isinstance() to check message types.

    Example:
        >>> from modal_agents_sdk import AssistantMessage, TextBlock
        >>> async for message in query("Create a hello.txt file"):
        ...     if isinstance(message, AssistantMessage):
        ...         for block in message.content:
        ...             if isinstance(block, TextBlock):
        ...                 print(block.text)

        >>> options = ModalAgentOptions(
        ...     system_prompt="You are a helpful assistant",
        ...     gpu="A10G",
        ... )
        >>> async for message in query("Analyze this data", options=options):
        ...     print(message)
    """
    if options is None:
        options = ModalAgentOptions()

    manager = SandboxManager(options)

    try:
        async with manager:
            async for raw_message in manager.execute_agent(prompt):
                # Convert raw dict to proper Message type
                yield convert_message(raw_message)
    finally:
        # Ensure cleanup happens
        await manager.terminate()


def _convert_to_message(raw: dict[str, Any]) -> Message:
    """Convert a raw message dict to a Message type.

    This is a wrapper around convert_message for backward compatibility.

    Args:
        raw: Raw message dictionary from agent output.

    Returns:
        Typed Message object.
    """
    return convert_message(raw)
