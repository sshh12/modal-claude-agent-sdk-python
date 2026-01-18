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
RUNNER_SCRIPT = '''
import asyncio
import json
import os
import sys
from dataclasses import asdict, is_dataclass


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


async def main():
    from claude_agent_sdk import query, ClaudeAgentOptions

    # Parse options and prompt from command line
    options_json = sys.argv[1]
    prompt = sys.argv[2]
    options_dict = json.loads(options_json)

    # Change to working directory
    cwd = options_dict.pop("cwd", "/workspace")
    os.chdir(cwd)

    # Build ClaudeAgentOptions from the filtered dict
    options = ClaudeAgentOptions(**options_dict)

    # Run query and output messages as JSON lines
    async for message in query(prompt=prompt, options=options):
        serialized = serialize_message(message)
        print(json.dumps(serialized), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
'''
