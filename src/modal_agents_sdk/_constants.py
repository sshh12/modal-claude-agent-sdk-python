"""Default constants for Modal Agents SDK."""

from __future__ import annotations

# Default tools that are allowed in the sandbox
DEFAULT_ALLOWED_TOOLS: list[str] = [
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
]

# Default working directory in the sandbox
DEFAULT_CWD = "/workspace"

# Default timeout for sandbox execution (1 hour)
DEFAULT_TIMEOUT = 3600

# Default permission mode for sandboxed execution
DEFAULT_PERMISSION_MODE = "acceptEdits"

# Default Python version for the sandbox image
DEFAULT_PYTHON_VERSION = "3.11"

# Runner script that executes inside the Modal sandbox
# This script uses the claude-agent-sdk Python package to run the agent
# Supports optional host-side hooks via stdin/stdout protocol when --hooks flag is passed
RUNNER_SCRIPT = '''
import asyncio
import json
import os
import shutil
import sys
import threading
import time
import uuid
from dataclasses import asdict, is_dataclass

# Lock for synchronized stdout writes to prevent interleaved output
_stdout_lock = threading.Lock()

# File-based response queue constants
RESPONSE_DIR = "/tmp/responses"
POLL_INTERVAL = 0.05  # 50ms


def serialize_message(message):
    """Serialize a message to a JSON-compatible dict."""
    if is_dataclass(message):
        return asdict(message)
    elif hasattr(message, "model_dump"):
        return message.model_dump()
    elif hasattr(message, "__dict__"):
        return message.__dict__
    else:
        return {"raw": str(message)}


def emit_message(msg_type, data):
    """Emit a message to stdout for the host to receive.

    Uses a lock to ensure atomic writes when multiple coroutines
    emit messages concurrently.
    """
    output = {"_type": msg_type, **data}
    # Encode to bytes and write to raw stdout to bypass buffering issues
    output_bytes = (json.dumps(output) + chr(10)).encode("utf-8")
    with _stdout_lock:
        sys.stdout.buffer.write(output_bytes)
        sys.stdout.buffer.flush()
        # Force OS-level flush to ensure data reaches the host
        os.fsync(sys.stdout.buffer.fileno())


def emit_agent_message(message):
    """Emit a regular agent message."""
    serialized = serialize_message(message)
    emit_message("message", serialized)


class StdinToFileWriter:
    """Simple stdin reader that writes responses to files.

    This replaces the complex StdinRouter with a simpler approach:
    - Reads JSON from stdin
    - Writes each response to a file named {request_id}.json
    - Uses atomic write (temp file + rename) for reliability
    """

    def __init__(self):
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        os.makedirs(RESPONSE_DIR, exist_ok=True)
        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _reader_loop(self):
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                response = json.loads(line)
                request_id = response.get("request_id")
                if not request_id:
                    continue

                # Atomic write: temp file + rename
                temp_path = f"{RESPONSE_DIR}/.{request_id}.tmp"
                final_path = f"{RESPONSE_DIR}/{request_id}.json"

                with open(temp_path, "w") as f:
                    json.dump(response, f)
                    f.flush()
                    os.fsync(f.fileno())

                os.rename(temp_path, final_path)
            except json.JSONDecodeError:
                continue
            except Exception:
                pass

    def stop(self):
        self._running = False


async def poll_for_response(request_id: str, timeout: float = 60.0) -> dict | None:
    """Poll for a response file and return its contents.

    Args:
        request_id: The unique ID of the request to wait for
        timeout: Maximum time to wait in seconds

    Returns:
        The response dict if found, None if timeout
    """
    response_path = f"{RESPONSE_DIR}/{request_id}.json"
    start_time = time.time()

    while time.time() - start_time < timeout:
        if os.path.exists(response_path):
            try:
                with open(response_path, "r") as f:
                    response = json.load(f)
                os.remove(response_path)
                return response
            except (json.JSONDecodeError, OSError):
                pass  # File incomplete or error, retry
        await asyncio.sleep(POLL_INTERVAL)

    return None


class HostToolProxy:
    """Proxy that forwards tool calls to the host machine."""

    def __init__(self, server_name, tool_definitions, timeout=60.0):
        self.server_name = server_name
        self.tool_definitions = tool_definitions
        self.timeout = timeout

    async def call_tool(self, tool_name, tool_input, tool_use_id=""):
        """Call a host-side tool and return the result."""
        request_id = str(uuid.uuid4())

        # Emit the tool request to host
        emit_message("host_tool_request", {
            "request_id": request_id,
            "server_name": self.server_name,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_use_id": tool_use_id,
        })

        # Poll for response file (replaces StdinRouter.register_and_wait)
        response = await poll_for_response(request_id, timeout=self.timeout)

        if response is None:
            return {
                "content": [{"type": "text", "text": "Timeout waiting for host tool response"}],
                "is_error": True,
            }

        if response.get("_type") != "host_tool_response":
            return {
                "content": [{"type": "text", "text": f"Invalid response type from host: {response.get('_type')}"}],
                "is_error": True,
            }

        return {
            "content": response.get("content", []),
            "is_error": response.get("is_error", False),
        }


def create_host_tool_mcp_server(proxy):
    """Create an MCP server that proxies calls to the host.

    This creates tool definitions that the claude-agent-sdk can use,
    with handlers that forward calls to the host via the HostToolProxy.
    """
    from claude_agent_sdk import tool, create_sdk_mcp_server

    sdk_tools = []
    for tool_def in proxy.tool_definitions:
        tool_name = tool_def["name"]
        tool_desc = tool_def.get("description", "")
        input_schema = tool_def.get("inputSchema", {"type": "object", "properties": {}})

        # Create a closure to capture the tool name
        def make_handler(name):
            async def handler(args):
                # Call the host-side tool via stdin/stdout protocol
                result = await proxy.call_tool(name, args)

                # Return in Anthropic content block format
                content = result.get("content", [])
                is_error = result.get("is_error", False)

                return {
                    "type": "tool_result",
                    "content": content if content else [{"type": "text", "text": "No content returned"}],
                    "is_error": is_error,
                }
            return handler

        # Create the tool using claude-agent-sdk's tool decorator
        sdk_tool = tool(
            name=tool_name,
            description=tool_desc,
            input_schema=input_schema,
        )(make_handler(tool_name))
        sdk_tools.append(sdk_tool)

    return create_sdk_mcp_server(name=proxy.server_name, tools=sdk_tools)


class HookProxy:
    """Proxy that sends hook requests to host and waits for responses."""

    def __init__(self, session_id, cwd, timeout=30.0):
        self.session_id = session_id
        self.cwd = cwd
        self.timeout = timeout

    async def pre_tool_use(self, tool_name, tool_input, tool_use_id):
        """Called before a tool is used. Returns (decision, reason, updated_input)."""
        request_id = str(uuid.uuid4())

        # Emit hook request
        emit_message("hook_request", {
            "request_id": request_id,
            "hook_event": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_use_id": tool_use_id,
            "session_id": self.session_id,
            "cwd": self.cwd,
        })

        # Poll for response file (replaces StdinRouter.register_and_wait)
        response = await poll_for_response(request_id, timeout=self.timeout)
        if response is None:
            # Timeout - allow by default
            return ("allow", None, None)

        if response.get("_type") != "hook_response":
            return ("allow", None, None)

        decision = response.get("decision", "allow")
        reason = response.get("reason")
        updated_input = response.get("updated_input")
        return (decision, reason, updated_input)

    async def post_tool_use(self, tool_name, tool_input, tool_result, is_error, tool_use_id):
        """Called after a tool is used. Fire-and-forget notification."""
        emit_message("hook_request", {
            "request_id": str(uuid.uuid4()),
            "hook_event": "PostToolUse",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_result": str(tool_result)[:10000],  # Truncate large results
            "is_error": is_error,
            "tool_use_id": tool_use_id,
            "session_id": self.session_id,
        })


def create_hooks_dict(hook_proxy):
    """Create hooks dict for the claude-agent-sdk.

    Returns a dict mapping event names to lists of HookMatcher objects.

    Note: This relies on claude-agent-sdk's hook feature, which requires
    bidirectional communication with the Claude Code CLI. The hooks will
    only fire if the CLI version supports them.
    """
    from claude_agent_sdk.types import HookMatcher

    async def pre_tool_use_hook(hook_input, tool_use_id, context):
        """Pre-tool-use hook that proxies to host."""
        tool_name = hook_input.get("tool_name", "")
        tool_input_data = hook_input.get("tool_input", {})

        decision, reason, updated_input = await hook_proxy.pre_tool_use(
            tool_name, tool_input_data, tool_use_id or ""
        )
        if decision == "deny":
            # Return with permissionDecision='deny' to block the tool
            return {
                "reason": reason or "Blocked by host hook",
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason or "Blocked by host hook",
                }
            }
        elif updated_input is not None:
            # Return modified input via hookSpecificOutput
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "toolInput": updated_input,
                }
            }
        # Allow - return empty dict
        return {}

    async def post_tool_use_hook(hook_input, tool_use_id, context):
        """Post-tool-use hook that proxies to host."""
        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input", {})
        tool_response = hook_input.get("tool_response", "")
        # tool_use_id is passed as second parameter, not from hook_input

        # Determine if error
        is_error = False
        result_str = str(tool_response)

        await hook_proxy.post_tool_use(
            tool_name, tool_input, result_str, is_error, tool_use_id
        )
        return {}

    # Create matchers for each hook type
    # The matcher regex ".*" matches all tools (host-side filtering in HookDispatcher)
    pre_matcher = HookMatcher(
        matcher=".*",
        hooks=[pre_tool_use_hook],
    )
    post_matcher = HookMatcher(
        matcher=".*",
        hooks=[post_tool_use_hook],
    )

    # Return dict mapping event names to matchers
    return {
        "PreToolUse": [pre_matcher],
        "PostToolUse": [post_matcher],
    }


async def main():
    from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

    # Parse options and prompt from command line
    # Format: python -c RUNNER_SCRIPT <options_json> <prompt>
    options_json = sys.argv[1]
    prompt = sys.argv[2]

    options_dict = json.loads(options_json)

    # Extract special fields from options
    cwd = options_dict.pop("cwd", "/workspace")
    enable_hooks = options_dict.pop("_enable_hooks", False)
    host_tools_config = options_dict.pop("_host_tools", None)

    os.chdir(cwd)

    # Convert agents dicts to AgentDefinition instances
    if "agents" in options_dict:
        agents_dict = options_dict["agents"]
        options_dict["agents"] = {
            name: AgentDefinition(**agent_def) if isinstance(agent_def, dict) else agent_def
            for name, agent_def in agents_dict.items()
        }

    # Set up hooks if enabled
    session_id = options_dict.get("resume", str(uuid.uuid4()))
    if enable_hooks:
        hook_proxy = HookProxy(session_id=session_id, cwd=cwd)
        hooks_dict = create_hooks_dict(hook_proxy)
        options_dict["hooks"] = hooks_dict

    # Set up host tools if provided
    mcp_servers = options_dict.get("mcp_servers", {})
    if host_tools_config:
        for server_config in host_tools_config:
            server_name = server_config["name"]
            tool_defs = server_config.get("tools", [])

            # Create proxy and MCP server for each host tool server
            proxy = HostToolProxy(
                server_name=server_name,
                tool_definitions=tool_defs,
                timeout=60.0,
            )
            mcp_server = create_host_tool_mcp_server(proxy)
            mcp_servers[server_name] = mcp_server

        options_dict["mcp_servers"] = mcp_servers

    # Build ClaudeAgentOptions from the filtered dict
    options = ClaudeAgentOptions(**options_dict)

    # Start file writer if we have host tools or hooks (needed for bidirectional communication)
    writer = None
    if host_tools_config or enable_hooks:
        writer = StdinToFileWriter()
        writer.start()

    try:
        # Use ClaudeSDKClient for streaming mode (supports hooks and host tools)
        from claude_agent_sdk import ClaudeSDKClient
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                emit_agent_message(message)
    finally:
        if writer:
            writer.stop()
            # Cleanup response directory
            shutil.rmtree(RESPONSE_DIR, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
'''
