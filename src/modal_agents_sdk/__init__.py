"""Modal Agents SDK - Run Claude agents in Modal sandboxes.

This package provides a simple interface for running Claude Agent SDK agents
in Modal sandboxes, combining Claude's powerful AI capabilities with Modal's
scalable cloud infrastructure.

Example:
    >>> from modal_agents_sdk import query, AssistantMessage, TextBlock
    >>> async for message in query("Create a hello.txt file"):
    ...     if isinstance(message, AssistantMessage):
    ...         for block in message.content:
    ...             if isinstance(block, TextBlock):
    ...                 print(block.text)

    >>> from modal_agents_sdk import query, ModalAgentOptions
    >>> options = ModalAgentOptions(
    ...     system_prompt="You are a helpful assistant",
    ...     gpu="A10G",
    ... )
    >>> async for message in query("Analyze this data", options=options):
    ...     print(message)
"""

from ._client import ModalAgentClient
from ._errors import (
    AgentExecutionError,
    CLINotInstalledError,
    ImageBuildError,
    ModalAgentError,
    NetworkConfigurationError,
    ResourceError,
    SandboxCreationError,
    SandboxTerminatedError,
    SandboxTimeoutError,
    VolumeError,
)
from ._image import ModalAgentImage
from ._options import ModalAgentOptions
from ._query import query
from ._types import (
    AssistantMessage,
    ContentBlock,
    Message,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    convert_message,
)

__version__ = "0.1.0"

__all__ = [
    # Main API
    "query",
    "ModalAgentClient",
    "ModalAgentOptions",
    "ModalAgentImage",
    # Errors
    "ModalAgentError",
    "SandboxCreationError",
    "SandboxTimeoutError",
    "SandboxTerminatedError",
    "ImageBuildError",
    "VolumeError",
    "ResourceError",
    "CLINotInstalledError",
    "AgentExecutionError",
    "NetworkConfigurationError",
    # Types (re-exported from claude-agent-sdk)
    "Message",
    "AssistantMessage",
    "UserMessage",
    "SystemMessage",
    "ResultMessage",
    "StreamEvent",
    "ContentBlock",
    "TextBlock",
    "ThinkingBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    # Utilities
    "convert_message",
]
