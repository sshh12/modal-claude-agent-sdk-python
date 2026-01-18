# Modal Agents SDK

> **Disclaimer**: This is an unofficial community package. It is not affiliated with, endorsed by, or associated with Anthropic or Modal in any way.

Run [Claude Agent SDK](https://github.com/anthropics/claude-code/tree/main/packages/claude-agent-sdk) agents in [Modal](https://modal.com) sandboxes.

This package wraps the Claude Agent SDK to execute AI agents in secure, scalable Modal containers. It provides progressive complexity—simple usage mirrors the original Agent SDK, while advanced features expose Modal's full capabilities (GPU, volumes, image customization, etc.).

## Installation

```bash
pip install git+https://github.com/sshh12/modal-claude-agent-sdk-python.git
```

## Quick Start

```python
import asyncio
from modal_agents_sdk import query

async def main():
    async for message in query("Create a hello.txt file with 'Hello, World!'"):
        print(message)

asyncio.run(main())
```

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
| Multi-turn conversations | ✅ | ✅ |

## Configuration

### Prerequisites

1. **Modal account**: Sign up at [modal.com](https://modal.com)
2. **Modal CLI**: Install and authenticate
   ```bash
   pip install modal
   modal setup
   ```
3. **Anthropic API key**: Create a Modal secret with your API key
   ```bash
   modal secret create anthropic-key ANTHROPIC_API_KEY=sk-ant-...
   ```

### Basic Options

```python
from modal_agents_sdk import query, ModalAgentOptions
import modal

options = ModalAgentOptions(
    # Claude options
    system_prompt="You are a helpful coding assistant",
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    max_turns=10,
    model="claude-sonnet-4-20250514",

    # Modal options
    secrets=[modal.Secret.from_name("anthropic-key")],
    timeout=3600,
)

async for message in query("Refactor the utils.py file", options=options):
    print(message)
```

### GPU Compute

```python
options = ModalAgentOptions(
    gpu="A10G",  # or "H100", "A100-80GB:2", etc.
    memory=16384,  # 16 GB
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

### Persistent Storage

```python
import modal

# Create a volume for persistent data
data_volume = modal.Volume.from_name("my-project-data", create_if_missing=True)

options = ModalAgentOptions(
    volumes={"/data": data_volume},
    secrets=[modal.Secret.from_name("anthropic-key")],
)

# Files written to /data persist across sandbox executions
```

### Custom Image

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

### Network Restrictions

```python
# Block all network access
options = ModalAgentOptions(
    block_network=True,
    secrets=[modal.Secret.from_name("anthropic-key")],
)

# Allow specific CIDRs only
options = ModalAgentOptions(
    cidr_allowlist=["10.0.0.0/8", "192.168.1.0/24"],
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

## Multi-turn Conversations

Use `ModalAgentClient` for conversations that span multiple queries:

```python
from modal_agents_sdk import ModalAgentClient, ModalAgentOptions
import modal

options = ModalAgentOptions(
    secrets=[modal.Secret.from_name("anthropic-key")],
)

async with ModalAgentClient(options=options) as client:
    # First query
    await client.query("Create a Python project structure")
    async for msg in client.receive_response():
        print(msg)

    # Follow-up query (maintains context)
    await client.query("Now add a requirements.txt with common dependencies")
    async for msg in client.receive_response():
        print(msg)

    # Export conversation history
    print(client.export_history())
```

## MCP Servers

Configure external MCP servers for additional tools:

```python
options = ModalAgentOptions(
    mcp_servers={
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "..."},
        },
    },
    secrets=[modal.Secret.from_name("anthropic-key")],
)
```

## API Reference

### `query(prompt, *, options=None)`

Execute a single agent query in a Modal sandbox.

**Parameters:**
- `prompt` (str): The prompt to send to the agent
- `options` (ModalAgentOptions, optional): Configuration options

**Yields:** `Message` objects from the agent response

### `ModalAgentClient`

Client for multi-turn conversations.

**Methods:**
- `async connect()`: Establish connection to sandbox
- `async disconnect()`: Disconnect and cleanup
- `async query(prompt)`: Send a query
- `async receive_response()`: Receive response messages
- `async query_and_receive(prompt)`: Combined query and receive
- `get_conversation_history()`: Get conversation history
- `clear_history()`: Clear conversation history
- `export_history()`: Export history as JSON

### `ModalAgentOptions`

Configuration dataclass with the following fields:

**Claude Agent SDK Options:**
- `system_prompt`: System prompt for the agent
- `allowed_tools`: List of allowed tools
- `disallowed_tools`: List of disallowed tools
- `mcp_servers`: MCP server configurations
- `max_turns`: Maximum conversation turns
- `permission_mode`: Permission mode (`"acceptEdits"` by default)
- `cwd`: Working directory (default: `/workspace`)
- `model`: Model to use
- `output_format`: Output format configuration
- `agents`: Custom agent definitions
- `hooks`: Hooks for observability
- `can_use_tool`: Tool validation callback

**Modal Sandbox Options:**
- `image`: Custom `ModalAgentImage`
- `gpu`: GPU type (e.g., `"A10G"`, `"H100"`)
- `cpu`: CPU cores
- `memory`: Memory in MiB
- `timeout`: Execution timeout (default: 3600)
- `idle_timeout`: Idle timeout
- `volumes`: Volume mounts
- `network_file_systems`: NFS mounts
- `secrets`: Modal secrets
- `env`: Environment variables
- `block_network`: Block all network access
- `cidr_allowlist`: Allowed CIDR blocks
- `cloud`: Cloud provider (`"aws"` or `"gcp"`)
- `region`: Region(s) to run in
- `name`: Sandbox name
- `app`: Modal App instance
- `verbose`: Enable verbose logging

### `ModalAgentImage`

Fluent builder for customizing the sandbox container image.

**Class Methods:**
- `default(python_version="3.11", node_version="20")`: Create default image
- `from_registry(tag, ...)`: Create from Docker registry
- `from_dockerfile(path, ...)`: Create from Dockerfile

**Instance Methods:**
- `pip_install(*packages)`: Install Python packages
- `apt_install(*packages)`: Install system packages
- `run_commands(*commands)`: Run shell commands
- `add_local_file(local_path, remote_path)`: Add local file
- `add_local_dir(local_path, remote_path)`: Add local directory
- `env(vars)`: Set environment variables
- `workdir(path)`: Set working directory

## Error Handling

```python
from modal_agents_sdk import (
    query,
    ModalAgentError,
    SandboxCreationError,
    SandboxTimeoutError,
    SandboxTerminatedError,
    ImageBuildError,
    CLINotInstalledError,
    AgentExecutionError,
)

try:
    async for message in query("Do something", options=options):
        print(message)
except SandboxTimeoutError:
    print("Execution timed out")
except SandboxCreationError as e:
    print(f"Failed to create sandbox: {e}")
except AgentExecutionError as e:
    print(f"Agent failed with exit code {e.exit_code}: {e}")
except ModalAgentError as e:
    print(f"Error: {e}")
```

## Development

```bash
# Clone the repository
git clone https://github.com/sshh12/modal-claude-agent-sdk-python
cd modal-claude-agent-sdk-python

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run type checking
mypy src/

# Run linting
ruff check src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.
