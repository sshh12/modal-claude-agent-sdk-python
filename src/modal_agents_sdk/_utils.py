"""Internal utilities for Modal Agents SDK."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._options import ModalAgentOptions


def build_sdk_options(
    options: ModalAgentOptions,
    resume: str | None = None,
) -> dict[str, Any]:
    """Build options dictionary for the Claude Agent SDK.

    This creates a dictionary that can be passed to ClaudeAgentOptions
    inside the runner script.

    Args:
        options: The ModalAgentOptions instance.
        resume: Optional session ID to resume a previous conversation.

    Returns:
        Dictionary of SDK options.
    """
    sdk_options: dict[str, Any] = {}

    # Resume session for multi-turn conversations
    # The resume parameter takes precedence over options.resume
    if resume:
        sdk_options["resume"] = resume
    elif options.resume:
        sdk_options["resume"] = options.resume

    # Working directory (handled specially by runner script)
    sdk_options["cwd"] = str(options.cwd) if options.cwd else "/workspace"

    # System prompt
    if options.system_prompt:
        sdk_options["system_prompt"] = options.system_prompt

    # Tools configuration
    if options.allowed_tools:
        sdk_options["allowed_tools"] = options.allowed_tools

    if options.disallowed_tools:
        sdk_options["disallowed_tools"] = options.disallowed_tools

    # Max turns
    if options.max_turns is not None:
        sdk_options["max_turns"] = options.max_turns

    # Permission mode
    if options.permission_mode:
        sdk_options["permission_mode"] = options.permission_mode

    # Model
    if options.model:
        sdk_options["model"] = options.model

    # MCP servers configuration
    if options.mcp_servers:
        sdk_options["mcp_servers"] = options.mcp_servers

    # Output format
    if options.output_format:
        sdk_options["output_format"] = options.output_format

    # Custom agents - convert dataclass instances to dicts for JSON serialization
    if options.agents:
        agents_dict = {}
        for name, agent_def in options.agents.items():
            if is_dataclass(agent_def) and not isinstance(agent_def, type):
                # Convert dataclass to dict, filtering out None values
                agents_dict[name] = {k: v for k, v in asdict(agent_def).items() if v is not None}
            else:
                # Already a dict or other serializable type
                agents_dict[name] = agent_def
        sdk_options["agents"] = agents_dict

    # Note: hooks and can_use_tool are not serializable, so they're not included
    # These would need special handling if required

    return sdk_options


def parse_stream_message(line: str) -> dict[str, Any] | None:
    """Parse a line from the streaming JSON output.

    Args:
        line: A line from the runner script output.

    Returns:
        Parsed JSON object or None if line is empty/invalid.
    """
    line = line.strip()
    if not line:
        return None

    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None
