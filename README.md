# Modal Agents SDK

> **Disclaimer**: This is an unofficial community package. It is not affiliated with, endorsed by, or associated with Anthropic or Modal in any way.

Run [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) agents in [Modal](https://modal.com) sandboxes.

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

See the `examples/` directory:

- `quick_start.py` - Basic usage
- `custom_image.py` - Image customization
- `gpu_compute.py` - GPU-enabled agent
- `persistent_storage.py` - Using volumes
- `multi_turn.py` - Multi-turn conversations
- `security_sandbox.py` - Network isolation
- `budget_control.py` - Cost tracking

## Development

```bash
git clone https://github.com/sshh12/modal-claude-agent-sdk-python
cd modal-claude-agent-sdk-python
pip install -e ".[dev]"

pytest          # Run tests
mypy src/       # Type checking
ruff check src/ # Linting
```

## License

MIT License - see [LICENSE](LICENSE) for details.
