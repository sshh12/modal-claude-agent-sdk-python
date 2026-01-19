# Modal Agents SDK

> **Disclaimer**: This is an unofficial community package. It is not affiliated with, endorsed by, or associated with Anthropic or Modal in any way.

Run [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) agents in [Modal](https://modal.com) sandboxes.

This package wraps the Claude Agent SDK to execute AI agents in secure, scalable Modal containers. It provides progressive complexity—simple usage mirrors the original Agent SDK, while advanced features expose Modal's full capabilities (GPU, volumes, image customization, etc.).

## Features

| Feature | modal-agents-sdk | claude-agent-sdk |
|---------|-----------------|------------------|
| Sandboxed execution | ✅ Modal containers | ❌ Local only |
| GPU support | ✅ A10G, H100, A100, etc. | ❌ |
| Persistent storage | ✅ Modal Volumes | ❌ |
| Custom images | ✅ Docker/Dockerfile | ❌ |
| Network isolation | ✅ Configurable | ❌ |
| Auto-scaling | ✅ Built-in | ❌ |
| Built-in tools | ✅ Read, Write, Bash, etc. | ✅ |
| MCP servers | ✅ | ✅ |
| Host-side hooks | ✅ Intercept tool calls | ✅ |
| Host-side tools | ✅ Run on local machine | ✅ |
| Multi-turn conversations | ✅ | ✅ |

## Installation

```bash
pip install modal-agents-sdk
```

### Prerequisites

1. **Modal account**: Sign up at [modal.com](https://modal.com)
2. **Modal CLI**: Install and authenticate
   ```bash
   pip install modal
   modal setup
   ```
3. **Anthropic API key**: Create a Modal secret
   ```bash
   modal secret create anthropic-key ANTHROPIC_API_KEY=sk-ant-...
   ```

## Quick Start

```python
import asyncio
from modal_agents_sdk import query

async def main():
    async for message in query("What is 2 + 2?"):
        print(message)

asyncio.run(main())
```

## Basic Usage: `query()`

`query()` is an async function for querying Claude in a Modal sandbox. It returns an `AsyncIterator` of response messages.

```python
from modal_agents_sdk import query, ModalAgentOptions, AssistantMessage, TextBlock
import modal

# Simple query
async for message in query(prompt="Hello Claude"):
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text)

# With options
options = ModalAgentOptions(
    system_prompt="You are a helpful assistant",
    max_turns=3,
    secrets=[modal.Secret.from_name("anthropic-key")],
)

async for message in query(prompt="Tell me a joke", options=options):
    print(message)
```

## Using Tools

```python
options = ModalAgentOptions(
    allowed_tools=["Read", "Write", "Bash"],
    permission_mode="acceptEdits",  # auto-accept file edits
    secrets=[modal.Secret.from_name("anthropic-key")],
)

async for message in query(prompt="Create a hello.py file", options=options):
    pass
```

## Working Directory

```python
from pathlib import Path

options = ModalAgentOptions(
    cwd="/workspace/myproject",  # or Path("/workspace/myproject")
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

## GPU Compute

```python
options = ModalAgentOptions(
    gpu="A10G",  # or "H100", "A100-80GB:2", etc.
    memory=16384,  # 16 GB
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

## Persistent Storage

```python
import modal

data_volume = modal.Volume.from_name("my-data", create_if_missing=True)

options = ModalAgentOptions(
    volumes={"/data": data_volume},
    secrets=[modal.Secret.from_name("anthropic-key")],
)

# Files written to /data persist across sandbox executions
```

## Custom Image

```python
from modal_agents_sdk import ModalAgentImage

image = (
    ModalAgentImage.default()
    .pip_install("pandas", "numpy", "scikit-learn")
    .apt_install("ffmpeg")
    .run_commands("npm install -g typescript")
)

options = ModalAgentOptions(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

## Network Restrictions

The agent requires network access to call the Anthropic API. Use `cidr_allowlist` to restrict access while allowing the API:

```python
# Anthropic API CIDR (required): 160.79.104.0/23
# Source: https://docs.anthropic.com/en/api/ip-addresses

options = ModalAgentOptions(
    cidr_allowlist=["160.79.104.0/23"],  # Anthropic API only
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

**Note:** `block_network=True` is not supported as it would prevent API calls.

## `ModalAgentClient`

`ModalAgentClient` supports multi-turn conversations:

```python
from modal_agents_sdk import ModalAgentClient, ModalAgentOptions
import modal

options = ModalAgentOptions(
    secrets=[modal.Secret.from_name("anthropic-key")],
)

async with ModalAgentClient(options=options) as client:
    await client.query("Create a Python project structure")
    async for msg in client.receive_response():
        print(msg)

    # Follow-up (maintains context)
    await client.query("Now add a requirements.txt")
    async for msg in client.receive_response():
        print(msg)
```

## MCP Servers

```python
options = ModalAgentOptions(
    mcp_servers={
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
        },
    },
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

## Host-Side Hooks

Intercept and control tool calls from your local machine while the agent runs in the sandbox:

```python
from modal_agents_sdk import (
    ModalAgentHooks,
    PreToolUseHookInput,
    PreToolUseHookResult,
    ModalAgentOptions,
)

async def block_dangerous_commands(input: PreToolUseHookInput) -> PreToolUseHookResult:
    """Block dangerous bash commands before execution."""
    if input.tool_name == "Bash" and "rm -rf" in input.tool_input.get("command", ""):
        return PreToolUseHookResult(
            decision="deny",
            reason="Blocked dangerous command",
        )
    return PreToolUseHookResult(decision="allow")

hooks = ModalAgentHooks(
    pre_tool_use=[block_dangerous_commands],
    tool_filter="Bash|Write|Edit",  # Only intercept these tools
)

options = ModalAgentOptions(
    host_hooks=hooks,
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

## Host-Side Tools

Define custom tools that run on your local machine but can be called by the agent in the sandbox:

```python
from modal_agents_sdk import host_tool, HostToolServer, ModalAgentOptions
import os

@host_tool(
    name="get_secret",
    description="Retrieve a secret from local environment",
    input_schema={"key": str},
)
async def get_secret(args):
    """Access local environment variables not available in sandbox."""
    value = os.environ.get(args["key"], "")
    return {"content": [{"type": "text", "text": f"Secret value: {value}"}]}

server = HostToolServer(name="local-tools", tools=[get_secret])

options = ModalAgentOptions(
    host_tools=[server],
    secrets=[modal.Secret.from_name("anthropic-key")],
)

# Agent can now call get_secret to access your local environment
async for message in query("Get the DATABASE_URL secret", options=options):
    print(message)
```

### Modal Functions as Tools

Expose deployed Modal functions as host tools to offload compute-intensive work to separate Modal containers:

```python
# modal_compute_functions.py - Deploy separately with: modal deploy modal_compute_functions.py
import modal

app = modal.App("agent-compute-tools")

@app.function()
def compute_fibonacci(n: int) -> dict:
    def fib(x): return x if x <= 1 else fib(x-1) + fib(x-2)
    return {"fibonacci": fib(n), "n": n}
```

```python
# main.py - Run after deploying the Modal function
import modal
from modal_agents_sdk import HostTool, HostToolServer, ModalAgentOptions, query

async def fibonacci_handler(args: dict) -> dict:
    func = modal.Function.from_name("agent-compute-tools", "compute_fibonacci")
    result = await func.remote.aio(n=args["n"])
    import json
    return {"content": [{"type": "text", "text": json.dumps(result)}]}

tool = HostTool(
    name="compute_fibonacci",
    description="Compute the nth Fibonacci number",
    input_schema={"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]},
    handler=fibonacci_handler,
)

server = HostToolServer(name="compute-tools", tools=[tool])
options = ModalAgentOptions(host_tools=[server], secrets=[modal.Secret.from_name("anthropic-key")])

async for message in query("Calculate fibonacci(20)", options=options):
    print(message)
```

## Types

See `src/modal_agents_sdk/_types.py` for complete type definitions. Key types are re-exported from `claude-agent-sdk`:

- `AssistantMessage`, `UserMessage`, `SystemMessage`, `ResultMessage` - Message types
- `TextBlock`, `ToolUseBlock`, `ToolResultBlock`, `ThinkingBlock` - Content blocks

## Error Handling

```python
from modal_agents_sdk import (
    ModalAgentError,        # Base error
    SandboxCreationError,   # Failed to create sandbox
    SandboxTimeoutError,    # Execution timed out
    SandboxTerminatedError, # Sandbox terminated
    ImageBuildError,        # Image build failed
    CLINotInstalledError,   # claude-agent-sdk not in image
    AgentExecutionError,    # Agent execution failed
)

try:
    async for message in query(prompt="Hello", options=options):
        pass
except SandboxTimeoutError:
    print("Execution timed out")
except AgentExecutionError as e:
    print(f"Agent failed: exit code {e.exit_code}")
```

## Examples

See the `examples/` directory for complete working examples:

### Getting Started
- `quick_start.py` - Basic usage with message type handling
- `multi_turn.py` - Multi-turn conversations with `ModalAgentClient`

### Infrastructure & Resources
- `custom_image.py` - Custom container images with pip/apt packages
- `gpu_compute.py` - GPU-enabled agents (A10G, CUDA, PyTorch)
- `resource_limits.py` - CPU, memory, and timeout configuration
- `cloud_region.py` - Cloud provider and region selection (AWS, GCP)

### Storage & Persistence
- `persistent_storage.py` - Using Modal volumes for data persistence
- `network_file_system.py` - NFS for shared storage across sandboxes
- `ephemeral_volume_upload.py` - Upload local files to sandbox
- `multi_turn_snapshots.py` - Multi-turn conversations with sandbox snapshots between turns
- `session_resume.py` - Persist conversation state across runs

### Security & Monitoring
- `security_sandbox.py` - Network isolation with CIDR allowlist
- `hooks.py` - Host-side hooks for security, monitoring, and tool interception
- `budget_control.py` - Cost tracking and budget limits

### Advanced Features
- `model_selection.py` - Choose Claude models (Haiku, Sonnet, Opus)
- `extended_thinking.py` - Complex reasoning with visible thought process
- `structured_output.py` - JSON responses with defined schemas
- `multi_agent.py` - Define specialized sub-agents for delegation
- `programmatic_subagents.py` - Custom agents with `AgentDefinition`
- `host_tools.py` - Custom tools that run on host machine
- `host_modal_functions_as_tools.py` - Use deployed Modal functions as agent tools

### Integrations
- `tunnel_web_app.py` - Build and expose web servers via encrypted tunnels

## Development

```bash
git clone https://github.com/sshh12/modal-claude-agent-sdk-python
cd modal-claude-agent-sdk-python
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run checks manually
pytest          # Run tests
mypy src/       # Type checking
ruff check src/ # Linting
ruff format src/ tests/  # Format code
```

## License

MIT License - see [LICENSE](LICENSE) for details.
