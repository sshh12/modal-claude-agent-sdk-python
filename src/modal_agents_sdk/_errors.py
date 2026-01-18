"""Exception classes for Modal Agents SDK."""

from __future__ import annotations


class ModalAgentError(Exception):
    """Base exception for all Modal Agent SDK errors."""

    pass


class SandboxCreationError(ModalAgentError):
    """Failed to create Modal sandbox."""

    pass


class SandboxTimeoutError(ModalAgentError):
    """Sandbox execution timed out."""

    pass


class SandboxTerminatedError(ModalAgentError):
    """Sandbox was terminated unexpectedly."""

    pass


class ImageBuildError(ModalAgentError):
    """Failed to build Modal image."""

    pass


class VolumeError(ModalAgentError):
    """Error with Modal volume operations."""

    pass


class ResourceError(ModalAgentError):
    """Error allocating requested resources (GPU, memory, etc.)."""

    pass


class CLINotInstalledError(ModalAgentError):
    """Claude Code CLI is not installed in the sandbox image."""

    pass


class AgentExecutionError(ModalAgentError):
    """Error during agent execution."""

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class NetworkConfigurationError(ModalAgentError):
    """Invalid network configuration for agent execution."""

    pass
