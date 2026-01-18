# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Modal Agents SDK is an unofficial Python wrapper that enables execution of Claude Agent SDK agents in Modal sandboxes. It bridges Claude's agentic capabilities with Modal's scalable cloud infrastructure (GPU support, volumes, custom images, network isolation).

## Commands

```bash
# Development setup
pip install -e ".[dev]"
pre-commit install

# Testing
pytest                              # Run all tests
pytest tests/test_query.py -v       # Run single test file
pytest tests/test_query.py::test_name -v  # Run single test

# Linting and formatting
ruff check src/ tests/              # Lint
ruff check src/ tests/ --fix        # Lint with auto-fix
ruff format src/ tests/             # Format
mypy src/                           # Type checking
```

## Architecture

```
src/modal_agents_sdk/
├── __init__.py      # Public API exports
├── _query.py        # query() - simple one-off queries (async generator)
├── _client.py       # ModalAgentClient - multi-turn conversations with session mgmt
├── _sandbox.py      # SandboxManager - Modal sandbox lifecycle, output streaming
├── _options.py      # ModalAgentOptions dataclass (30+ config fields)
├── _image.py        # ModalAgentImage - fluent builder for container images
├── _errors.py       # Exception hierarchy (ModalAgentError base)
├── _types.py        # Type re-exports from claude-agent-sdk + convert_message()
├── _utils.py        # Internal utilities
└── _constants.py    # Default constants and embedded RUNNER_SCRIPT
```

### Key Data Flow

1. User calls `query()` or `ModalAgentClient.query()` with prompt + options
2. `SandboxManager` creates Modal sandbox with configured image/secrets/volumes
3. Embedded `RUNNER_SCRIPT` (Python code in `_constants.py`) executes inside sandbox
4. `claude-agent-sdk` runs the agent, streaming JSON messages to stdout
5. `SandboxManager` captures JSON lines and yields raw dicts
6. `convert_message()` converts raw dicts to typed Message objects

### Public API

- `query(prompt, options)` - Async generator for one-off queries
- `ModalAgentClient(options)` - Context manager for multi-turn conversations
- `ModalAgentOptions` - Dataclass combining Claude Agent SDK options (system_prompt, allowed_tools, mcp_servers) with Modal sandbox options (gpu, memory, volumes, secrets, cidr_allowlist)
- `ModalAgentImage` - Builder pattern: `.default().pip_install().apt_install().run_commands()`

### Important Constraints

- `block_network=True` is not supported (agent needs API access)
- Network isolation uses `cidr_allowlist` - Anthropic API CIDR: `160.79.104.0/23`
- Anthropic API key must be passed via Modal secrets (default: `anthropic-key`)

## Code Style

- Line length: 100 characters
- Target Python: 3.10+
- All modules use async/await patterns
- Internal modules prefixed with underscore (`_sandbox.py`)
- Type hints throughout, mypy checked
