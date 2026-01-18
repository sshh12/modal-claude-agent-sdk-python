"""ModalAgentOptions dataclass for configuring agent execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ._constants import (
    DEFAULT_ALLOWED_TOOLS,
    DEFAULT_CWD,
    DEFAULT_TIMEOUT,
)

if TYPE_CHECKING:
    from ._image import ModalAgentImage


@dataclass
class ModalAgentOptions:
    """Configuration options for running Claude agents in Modal sandboxes.

    This combines options from the Claude Agent SDK with Modal-specific options
    for sandbox configuration.

    Example:
        >>> options = ModalAgentOptions(
        ...     system_prompt="You are a helpful assistant",
        ...     allowed_tools=["Read", "Write", "Bash"],
        ...     gpu="A10G",
        ...     memory=8192,
        ... )
    """

    # === Claude Agent SDK Options ===

    system_prompt: str | None = None
    """System prompt to prepend to the conversation."""

    allowed_tools: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_TOOLS))
    """List of tools the agent is allowed to use."""

    disallowed_tools: list[str] = field(default_factory=list)
    """List of tools the agent is explicitly not allowed to use."""

    mcp_servers: dict[str, Any] = field(default_factory=dict)
    """MCP server configurations. Keys are server names, values are config dicts."""

    max_turns: int | None = None
    """Maximum number of conversation turns. None means unlimited."""

    permission_mode: Literal["default", "acceptEdits", "bypassPermissions"] = "acceptEdits"
    """Permission mode for tool execution. Defaults to 'acceptEdits' for sandboxed execution."""

    can_use_tool: Callable[[str, dict[str, Any]], bool] | None = None
    """Optional callback to validate tool usage. Returns True if tool use is allowed."""

    hooks: dict[str, list[dict[str, Any]]] | None = None
    """Hooks for observability and custom behavior."""

    cwd: str | Path = DEFAULT_CWD
    """Working directory for the agent. Defaults to '/workspace'."""

    model: str | None = None
    """Model to use for the agent (e.g., 'claude-sonnet-4-20250514')."""

    output_format: dict[str, Any] | None = None
    """Output format configuration for structured responses."""

    agents: dict[str, dict[str, Any]] | None = None
    """Custom agent definitions for multi-agent scenarios."""

    # === Modal Sandbox Options ===

    image: ModalAgentImage | None = None
    """Custom container image. Uses default image if not provided."""

    gpu: str | None = None
    """GPU type to use (e.g., 'A10G', 'H100', 'A100-80GB:2')."""

    cpu: float | None = None
    """Number of CPU cores to allocate."""

    memory: int | None = None
    """Memory allocation in MiB."""

    timeout: int = DEFAULT_TIMEOUT
    """Sandbox execution timeout in seconds. Defaults to 3600 (1 hour)."""

    idle_timeout: int | None = None
    """Sandbox idle timeout in seconds. Sandbox terminates after this period of inactivity."""

    volumes: dict[str | Path, Any] = field(default_factory=dict)
    """Volumes to mount. Keys are mount paths, values are modal.Volume objects."""

    network_file_systems: dict[str | Path, Any] = field(default_factory=dict)
    """Network file systems to mount. Keys are mount paths, values are modal.NetworkFileSystem objects."""

    secrets: list[Any] = field(default_factory=list)
    """List of modal.Secret objects to inject into the sandbox."""

    env: dict[str, str] | None = None
    """Environment variables to set in the sandbox."""

    block_network: bool = False
    """If True, block all network access from the sandbox."""

    cidr_allowlist: list[str] | None = None
    """List of CIDR blocks to allow network access to."""

    cloud: str | None = None
    """Cloud provider to run on ('aws' or 'gcp')."""

    region: str | list[str] | None = None
    """Region(s) to run in."""

    name: str | None = None
    """Optional name for the sandbox."""

    app: Any | None = None
    """Modal App to use. Creates a new one if not provided."""

    verbose: bool = False
    """If True, enable verbose logging."""

    def with_updates(self, **kwargs: Any) -> ModalAgentOptions:
        """Create a new options instance with updated values.

        Args:
            **kwargs: Option values to update.

        Returns:
            A new ModalAgentOptions instance with the updates applied.
        """
        from dataclasses import asdict

        current = asdict(self)
        current.update(kwargs)
        return ModalAgentOptions(**current)
