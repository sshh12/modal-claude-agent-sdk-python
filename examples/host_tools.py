"""Host-side tools example - define custom tools that run on the host machine.

This example demonstrates the host-side tools feature that allows defining
custom tools that run on your local machine but can be called by the Claude
agent running inside a Modal sandbox.

Features demonstrated:
1. Defining host tools with the @host_tool decorator
2. Creating a HostToolServer to group related tools
3. Accessing local resources (environment variables, files)
4. Using host tools with ModalAgentOptions

Use cases for host tools:
- Accessing secrets/credentials from local environment
- Querying local databases
- Reading local configuration files
- Executing local scripts or binaries
- Interacting with local services
"""

import asyncio
import json
import os
from pathlib import Path

import modal

from modal_agents_sdk import (
    AssistantMessage,
    HostToolServer,
    ModalAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    host_tool,
    query,
)

# Define host tools using the @host_tool decorator
# Each tool runs on the HOST machine, not in the sandbox


@host_tool(
    name="get_env_var",
    description="Get an environment variable from the host machine",
    input_schema={"name": str},
)
async def get_env_var(args: dict) -> dict:
    """Get an environment variable from the host.

    This tool runs on the host machine and can access local environment
    variables that are not available inside the Modal sandbox.
    """
    name = args.get("name", "")
    value = os.environ.get(name, "")

    if value:
        return {"content": [{"type": "text", "text": f"Environment variable {name}={value}"}]}
    else:
        return {"content": [{"type": "text", "text": f"Environment variable {name} not found"}]}


@host_tool(
    name="read_local_file",
    description="Read a file from the host machine's filesystem",
    input_schema={"path": str, "max_lines": int},
)
async def read_local_file(args: dict) -> dict:
    """Read a file from the host's local filesystem.

    This tool can access files on your local machine that are not
    mounted in the Modal sandbox.
    """
    path = args.get("path", "")
    max_lines = args.get("max_lines", 50)

    try:
        file_path = Path(path).expanduser().resolve()

        # Security check - only allow reading certain directories
        # In production, you'd want more robust path validation
        allowed_prefixes = [Path.home(), Path.cwd()]
        if not any(str(file_path).startswith(str(p)) for p in allowed_prefixes):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Access denied: {path} is outside allowed directories",
                    }
                ],
                "is_error": True,
            }

        if not file_path.exists():
            return {
                "content": [{"type": "text", "text": f"File not found: {path}"}],
                "is_error": True,
            }

        if not file_path.is_file():
            return {"content": [{"type": "text", "text": f"Not a file: {path}"}], "is_error": True}

        with open(file_path) as f:
            lines = f.readlines()[:max_lines]
            content = "".join(lines)

        return {"content": [{"type": "text", "text": content}]}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error reading file: {e}"}], "is_error": True}


@host_tool(
    name="get_local_config",
    description="Get configuration from a local JSON config file",
    input_schema={"config_path": str, "key": str},
)
async def get_local_config(args: dict) -> dict:
    """Read a specific key from a local JSON configuration file.

    Useful for accessing application configuration that's stored
    on the host machine.
    """
    config_path = args.get("config_path", "")
    key = args.get("key", "")

    try:
        path = Path(config_path).expanduser().resolve()

        if not path.exists():
            return {
                "content": [{"type": "text", "text": f"Config file not found: {config_path}"}],
                "is_error": True,
            }

        with open(path) as f:
            config = json.load(f)

        if key:
            # Support nested keys like "database.host"
            value = config
            for k in key.split("."):
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return {
                        "content": [{"type": "text", "text": f"Key '{key}' not found in config"}],
                        "is_error": True,
                    }
            return {"content": [{"type": "text", "text": f"{key}={json.dumps(value)}"}]}
        else:
            return {"content": [{"type": "text", "text": json.dumps(config, indent=2)}]}

    except json.JSONDecodeError as e:
        return {"content": [{"type": "text", "text": f"Invalid JSON: {e}"}], "is_error": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "is_error": True}


@host_tool(
    name="list_local_directory",
    description="List files in a directory on the host machine",
    input_schema={"path": str, "pattern": str},
)
async def list_local_directory(args: dict) -> dict:
    """List files in a local directory, optionally filtered by pattern.

    This allows the agent to discover what files are available on
    the host machine.
    """
    path = args.get("path", ".")
    pattern = args.get("pattern", "*")

    try:
        dir_path = Path(path).expanduser().resolve()

        if not dir_path.exists():
            return {
                "content": [{"type": "text", "text": f"Directory not found: {path}"}],
                "is_error": True,
            }

        if not dir_path.is_dir():
            return {
                "content": [{"type": "text", "text": f"Not a directory: {path}"}],
                "is_error": True,
            }

        files = list(dir_path.glob(pattern))[:100]  # Limit to 100 results
        file_list = "\n".join(str(f.relative_to(dir_path)) for f in sorted(files))

        return {
            "content": [
                {"type": "text", "text": f"Files in {path} matching '{pattern}':\n{file_list}"}
            ]
        }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "is_error": True}


# Create a server to group related tools
local_tools_server = HostToolServer(
    name="local-tools",
    tools=[get_env_var, read_local_file, get_local_config, list_local_directory],
    version="1.0.0",
)


async def main():
    """Run an agent with host-side tools for local resource access."""

    # Configure options with host tools
    options = ModalAgentOptions(
        host_tools=[local_tools_server],
        secrets=[modal.Secret.from_name("anthropic-key")],
        system_prompt=(
            "You are a helpful assistant with access to tools that can read "
            "information from the user's local machine. Use the host tools to "
            "help the user access local files, environment variables, and "
            "configuration. Be careful to respect file permissions and only "
            "access what the user asks for."
        ),
        max_turns=10,
    )

    print("Host-Side Tools Example")
    print("=" * 60)
    print("This example demonstrates tools that run on your local machine")
    print("while the agent runs in a Modal sandbox.")
    print()
    print("Available host tools:")
    for tool in local_tools_server.tools:
        print(f"  - {tool.name}: {tool.description}")
    print("=" * 60)
    print()

    # Example prompt that uses host tools
    prompt = (
        "Please help me explore my local environment. "
        "1. Check if the HOME environment variable is set. "
        "2. List the files in my current directory. "
        "Summarize what you find."
    )

    print(f"Prompt: {prompt}\n")
    print("-" * 60)

    async for message in query(prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text[:300] + "..." if len(block.text) > 300 else block.text
                    print(f"[Assistant] {text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[Tool Call] {block.name}: {str(block.input)[:100]}...")
                elif isinstance(block, ToolResultBlock):
                    content = (
                        block.content if isinstance(block.content, str) else str(block.content)
                    )
                    preview = content[:100] + "..." if len(content) > 100 else content
                    status = "ERROR" if block.is_error else "OK"
                    print(f"[Tool Result] [{status}] {preview}")

        elif isinstance(message, ResultMessage):
            print(f"\n[{message.subtype}] Completed in {message.num_turns} turns")


if __name__ == "__main__":
    asyncio.run(main())
