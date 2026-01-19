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
import sys
import threading
import uuid
from dataclasses import asdict, is_dataclass

# Lock for synchronized stdout writes to prevent interleaved output
_stdout_lock = threading.Lock()

# Response handling - thread-safe dict with asyncio Events for cross-thread signaling
_response_events: dict[str, asyncio.Event] = {}
_response_data: dict[str, dict] = {}
_response_lock = threading.Lock()


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
    emit messages concurrently. Includes a small delay to ensure Modal's
    stdout streaming handles each line correctly.
    """
    import time

    output = {"_type": msg_type, **data}
    # Encode to bytes and write to raw stdout to bypass buffering issues
    output_bytes = (json.dumps(output) + chr(10)).encode("utf-8")

    with _stdout_lock:
        sys.stdout.buffer.write(output_bytes)
        sys.stdout.buffer.flush()
        # Force sync to OS to ensure data is truly flushed
        try:
            os.fsync(sys.stdout.fileno())
        except (OSError, AttributeError):
            pass  # fsync may not be supported on all platforms
        # Small delay (50ms) to prevent rapid-fire writes that Modal might not
        # handle well - this fixes intermittent line loss in stdout streaming
        time.sleep(0.05)


def emit_agent_message(message):
    """Emit a regular agent message."""
    serialized = serialize_message(message)
    emit_message("message", serialized)


class StdinResponseReader:
    """Reads responses from stdin and signals waiting coroutines.

    Uses asyncio Events for efficient cross-thread signaling instead of
    file-based polling.
    """

    def __init__(self):
        self._running = False
        self._thread = None
        self._loop = None
        self._responses_received = 0

    def start(self, loop):
        if self._running:
            return
        self._running = True
        self._loop = loop
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        sys.stderr.write("[StdinReader] Started\\n")
        sys.stderr.flush()

    def _reader_loop(self):
        sys.stderr.write("[StdinReader] Reader loop started\\n")
        sys.stderr.flush()
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    sys.stderr.write("[StdinReader] EOF on stdin\\n")
                    sys.stderr.flush()
                    break
                line = line.strip()
                if not line:
                    continue

                sys.stderr.write(f"[StdinReader] Got line: {line[:60]}...\\n")
                sys.stderr.flush()

                response = json.loads(line)
                request_id = response.get("request_id")
                if not request_id:
                    sys.stderr.write("[StdinReader] No request_id in response\\n")
                    sys.stderr.flush()
                    continue

                self._responses_received += 1
                sys.stderr.write(f"[StdinReader] Response #{self._responses_received} for {request_id}\\n")
                sys.stderr.flush()

                # Store response and signal the waiting coroutine
                with _response_lock:
                    _response_data[request_id] = response
                    event = _response_events.get(request_id)
                    has_event = event is not None

                sys.stderr.write(f"[StdinReader] Event exists: {has_event}\\n")
                sys.stderr.flush()

                if event and self._loop:
                    # Signal the event from the event loop thread
                    self._loop.call_soon_threadsafe(event.set)
                    sys.stderr.write(f"[StdinReader] Event signaled for {request_id}\\n")
                    sys.stderr.flush()

            except json.JSONDecodeError as e:
                sys.stderr.write(f"[StdinReader] JSON decode error: {e}\\n")
                sys.stderr.flush()
                continue
            except Exception as e:
                sys.stderr.write(f"[StdinReader] Exception: {e}\\n")
                sys.stderr.flush()
                pass

    def stop(self):
        self._running = False
        sys.stderr.write(f"[StdinReader] Stopped, received {self._responses_received} responses\\n")
        sys.stderr.flush()


def register_response_event(request_id: str) -> asyncio.Event:
    """Register an event to be signaled when a response arrives."""
    event = asyncio.Event()
    with _response_lock:
        _response_events[request_id] = event
    return event


def get_response(request_id: str) -> dict | None:
    """Get and remove a response by request_id."""
    with _response_lock:
        _response_events.pop(request_id, None)
        return _response_data.pop(request_id, None)


class HostToolProxy:
    """Proxy that forwards tool calls to the host machine."""

    def __init__(self, server_name, tool_definitions, timeout=60.0):
        self.server_name = server_name
        self.tool_definitions = tool_definitions
        self.timeout = timeout

    async def call_tool(self, tool_name, tool_input, tool_use_id=""):
        """Call a host-side tool and return the result."""
        request_id = str(uuid.uuid4())

        sys.stderr.write(f"[HostToolProxy] call_tool: {tool_name}, request_id={request_id}\\n")
        sys.stderr.flush()

        # Register event BEFORE emitting to avoid race condition
        event = register_response_event(request_id)

        # Emit the tool request to host
        sys.stderr.write(f"[HostToolProxy] Emitting request for {tool_name}\\n")
        sys.stderr.flush()

        emit_message("host_tool_request", {
            "request_id": request_id,
            "server_name": self.server_name,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_use_id": tool_use_id,
        })

        # Small delay to ensure stdout propagates through Modal's streaming
        await asyncio.sleep(0.1)

        sys.stderr.write(f"[HostToolProxy] Request emitted, waiting for response...\\n")
        sys.stderr.flush()

        # Wait for response
        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout)
            response = get_response(request_id)
            sys.stderr.write(f"[HostToolProxy] Got response for {tool_name}\\n")
            sys.stderr.flush()
        except asyncio.TimeoutError:
            sys.stderr.write(f"[HostToolProxy] TIMEOUT for {tool_name}\\n")
            sys.stderr.flush()
            with _response_lock:
                _response_events.pop(request_id, None)
                _response_data.pop(request_id, None)
            response = None

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

        # Register event BEFORE emitting to avoid race condition
        event = register_response_event(request_id)

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

        # Wait for response
        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout)
            response = get_response(request_id)
        except asyncio.TimeoutError:
            with _response_lock:
                _response_events.pop(request_id, None)
                _response_data.pop(request_id, None)
            response = None

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

    # Start stdin reader if we have host tools or hooks (needed for bidirectional communication)
    reader = None
    if host_tools_config or enable_hooks:
        reader = StdinResponseReader()
        reader.start(asyncio.get_event_loop())

    try:
        # Use ClaudeSDKClient for streaming mode (supports hooks and host tools)
        from claude_agent_sdk import ClaudeSDKClient
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                emit_agent_message(message)
    finally:
        if reader:
            reader.stop()


if __name__ == "__main__":
    asyncio.run(main())
'''
