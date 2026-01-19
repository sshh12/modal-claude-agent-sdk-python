"""Host-side tools for Modal Agents SDK.

This module implements custom tools that run on the host machine but can be
called by the Claude agent running inside the Modal sandbox. It extends the
existing bidirectional stdin/stdout protocol (used for hooks) to also support
tool execution.

Example:
    >>> @host_tool("get_secret", "Retrieve a secret from the host", {"key": str})
    ... async def get_secret(args):
    ...     import os
    ...     value = os.environ.get(args["key"], "")
    ...     return {"content": [{"type": "text", "text": f"Secret: {value}"}]}
    ...
    >>> server = HostToolServer(name="local-tools", tools=[get_secret])
    >>> options = ModalAgentOptions(host_tools=[server])
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar, get_type_hints

# Type alias for tool handler return type
ToolResult = dict[str, Any]
ToolHandler = Callable[[dict[str, Any]], ToolResult | Awaitable[ToolResult]]

T = TypeVar("T", bound=ToolHandler)


@dataclass
class HostTool:
    """A host-side tool that can be called by the agent in the sandbox.

    Host tools execute on the host machine, allowing access to local resources
    like environment variables, local databases, or file systems that are not
    available inside the Modal sandbox.

    Attributes:
        name: The name of the tool (used in API calls).
        description: Human-readable description of what the tool does.
        input_schema: JSON Schema for the tool's input parameters.
        handler: Async or sync function that executes the tool.
    """

    name: str
    """Name of the tool (e.g., 'get_secret', 'query_db')."""

    description: str
    """Human-readable description of what the tool does."""

    input_schema: dict[str, Any]
    """JSON Schema describing the tool's input parameters."""

    handler: ToolHandler
    """Function that executes the tool. Takes a dict of args and returns a result dict."""


def _python_type_to_json_schema(python_type: type | str) -> dict[str, Any]:
    """Convert a Python type annotation to JSON Schema.

    Args:
        python_type: A Python type like str, int, bool, or a type string.

    Returns:
        JSON Schema type definition.
    """
    type_mapping = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
        "str": {"type": "string"},
        "int": {"type": "integer"},
        "float": {"type": "number"},
        "bool": {"type": "boolean"},
        "list": {"type": "array"},
        "dict": {"type": "object"},
    }

    if python_type in type_mapping:
        return type_mapping[python_type]

    # Handle string type names
    if isinstance(python_type, str) and python_type in type_mapping:
        return type_mapping[python_type]

    # Default to string for unknown types
    return {"type": "string"}


def _convert_input_schema(schema: dict[str, Any] | type) -> dict[str, Any]:
    """Convert a simplified schema to full JSON Schema.

    Args:
        schema: Either a full JSON Schema dict or a simplified {name: type} dict.

    Returns:
        Full JSON Schema with type, properties, and required fields.
    """
    # If it's already a full JSON Schema, return as-is
    if isinstance(schema, dict) and "type" in schema:
        return schema

    # Convert simplified {name: type} format to JSON Schema
    if isinstance(schema, dict):
        properties = {}
        required = []

        for name, type_hint in schema.items():
            if isinstance(type_hint, dict):
                # Already a JSON Schema property definition
                properties[name] = type_hint
            else:
                properties[name] = _python_type_to_json_schema(type_hint)
            required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    # Default empty schema
    return {"type": "object", "properties": {}}


def host_tool(
    name: str,
    description: str,
    input_schema: dict[str, Any] | None = None,
) -> Callable[[T], HostTool]:
    """Decorator to create a host-side tool.

    Use this decorator to define tools that run on the host machine but can
    be called by the Claude agent running inside the Modal sandbox.

    Args:
        name: The name of the tool (used in API calls).
        description: Human-readable description of what the tool does.
        input_schema: Schema for input parameters. Can be:
            - A simplified dict like {"key": str, "value": int}
            - A full JSON Schema dict
            - None to infer from function signature

    Returns:
        A decorator that creates a HostTool from the function.

    Example:
        >>> @host_tool("get_secret", "Get a secret from environment", {"key": str})
        ... async def get_secret(args):
        ...     value = os.environ.get(args["key"], "")
        ...     return {"content": [{"type": "text", "text": f"Secret: {value}"}]}
    """

    def decorator(func: T) -> HostTool:
        # Determine input schema
        if input_schema is not None:
            schema = _convert_input_schema(input_schema)
        else:
            # Try to infer from type hints
            try:
                hints = get_type_hints(func)
                # Look for 'args' parameter type hint
                if "args" in hints and hasattr(hints["args"], "__annotations__"):
                    schema = _convert_input_schema(hints["args"].__annotations__)
                else:
                    schema = {"type": "object", "properties": {}}
            except Exception:
                schema = {"type": "object", "properties": {}}

        return HostTool(
            name=name,
            description=description,
            input_schema=schema,
            handler=func,
        )

    return decorator


@dataclass
class HostToolServer:
    """A server that groups related host-side tools together.

    Similar to MCP servers, a HostToolServer groups tools that share a common
    purpose or access pattern. Tools from multiple servers can be used together.

    Attributes:
        name: Unique name for this tool server.
        tools: List of HostTool instances provided by this server.
        version: Version string for the server (default: "1.0.0").

    Example:
        >>> @host_tool("get_secret", "Get secret", {"key": str})
        ... async def get_secret(args):
        ...     return {"content": [{"type": "text", "text": os.environ.get(args["key"], "")}]}
        ...
        >>> server = HostToolServer(name="secrets", tools=[get_secret])
    """

    name: str
    """Unique name for this tool server."""

    tools: list[HostTool] = field(default_factory=list)
    """List of tools provided by this server."""

    version: str = "1.0.0"
    """Version string for the server."""

    def get_tool(self, name: str) -> HostTool | None:
        """Get a tool by name.

        Args:
            name: The name of the tool to retrieve.

        Returns:
            The HostTool if found, None otherwise.
        """
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions in a format suitable for the agent.

        Returns:
            List of tool definition dicts with name, description, and inputSchema.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in self.tools
        ]


class HostToolDispatcher:
    """Dispatches tool requests from the sandbox to host-side handlers.

    This class handles routing tool requests from the sandbox to the
    appropriate host-side tool handlers and returning their results.
    """

    def __init__(self, servers: list[HostToolServer]) -> None:
        """Initialize the tool dispatcher.

        Args:
            servers: List of HostToolServer instances containing tools.
        """
        self.servers = servers
        # Build lookup map for quick tool resolution
        self._tool_map: dict[str, tuple[HostToolServer, HostTool]] = {}
        for server in servers:
            for tool in server.tools:
                # Key by "server_name:tool_name" for uniqueness
                key = f"{server.name}:{tool.name}"
                self._tool_map[key] = (server, tool)
                # Also allow lookup by just tool name if unique
                if tool.name not in self._tool_map:
                    self._tool_map[tool.name] = (server, tool)

    def get_tool(self, server_name: str, tool_name: str) -> HostTool | None:
        """Get a tool by server and tool name.

        Args:
            server_name: The name of the server.
            tool_name: The name of the tool.

        Returns:
            The HostTool if found, None otherwise.
        """
        key = f"{server_name}:{tool_name}"
        if key in self._tool_map:
            return self._tool_map[key][1]
        return None

    async def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool request to the appropriate handler.

        Args:
            request: Tool request dictionary from the sandbox containing:
                - request_id: Unique ID for this request
                - server_name: Name of the server
                - tool_name: Name of the tool
                - tool_input: Input parameters for the tool
                - tool_use_id: Claude's tool use ID

        Returns:
            Tool response dictionary containing:
                - _type: "host_tool_response"
                - request_id: Same as input request_id
                - content: Tool result content
                - is_error: Whether the tool execution failed
        """
        request_id = request.get("request_id", str(uuid.uuid4()))
        server_name = request.get("server_name", "")
        tool_name = request.get("tool_name", "")
        tool_input = request.get("tool_input", {})

        # Find the tool
        tool = self.get_tool(server_name, tool_name)
        if tool is None:
            return {
                "_type": "host_tool_response",
                "request_id": request_id,
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: Tool '{tool_name}' not found in server '{server_name}'",
                    }
                ],
                "is_error": True,
            }

        try:
            # Execute the tool handler
            result = tool.handler(tool_input)
            if asyncio.iscoroutine(result):
                result = await result

            # Normalize result format
            if isinstance(result, dict):
                if "content" in result:
                    content = result["content"]
                else:
                    # Wrap raw dict result in text content
                    import json

                    content = [{"type": "text", "text": json.dumps(result)}]
            elif isinstance(result, str):
                content = [{"type": "text", "text": result}]
            else:
                content = [{"type": "text", "text": str(result)}]

            return {
                "_type": "host_tool_response",
                "request_id": request_id,
                "content": content,
                "is_error": False,
            }

        except Exception as e:
            return {
                "_type": "host_tool_response",
                "request_id": request_id,
                "content": [{"type": "text", "text": f"Error executing tool: {e!s}"}],
                "is_error": True,
            }


def is_host_tool_request(message: dict[str, Any]) -> bool:
    """Check if a message is a host tool request.

    Args:
        message: Parsed message dictionary.

    Returns:
        True if this is a host tool request that needs handling.
    """
    return message.get("_type") == "host_tool_request"


__all__ = [
    "HostTool",
    "HostToolDispatcher",
    "HostToolServer",
    "host_tool",
    "is_host_tool_request",
]
