"""Sandbox management for Modal Agents SDK."""

from __future__ import annotations

import json
import os
import warnings
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import modal

from ._constants import RUNNER_SCRIPT
from ._errors import (
    AgentExecutionError,
    CLINotInstalledError,
    MissingAPIKeyError,
    NetworkConfigurationError,
    SandboxCreationError,
    SandboxTerminatedError,
    SandboxTimeoutError,
)
from ._host_hooks import HookDispatcher, is_agent_message, is_hook_request, parse_hook_message
from ._host_tools import HostToolDispatcher, is_host_tool_request
from ._image import ModalAgentImage
from ._utils import build_sdk_options, parse_stream_message

if TYPE_CHECKING:
    from ._host_hooks import ModalAgentHooks
    from ._host_tools import HostToolServer
    from ._options import ModalAgentOptions


class SandboxManager:
    """Manages the lifecycle of Modal sandboxes for agent execution."""

    def __init__(self, options: ModalAgentOptions) -> None:
        """Initialize the sandbox manager.

        Args:
            options: Configuration options for the sandbox.
        """
        self.options = options
        self._sandbox: modal.Sandbox | None = None
        self._app: modal.App | None = None
        self._using_local_api_key: bool = False

    def _get_image(self) -> modal.Image:
        """Get the Modal image to use for the sandbox.

        Returns:
            The Modal image.
        """
        if self.options.image is not None:
            return self.options.image.modal_image
        return ModalAgentImage.default().modal_image

    def _validate_network_config(self) -> None:
        """Validate network configuration is compatible with agent execution.

        Raises:
            NetworkConfigurationError: If block_network=True is set.
        """
        if self.options.block_network:
            raise NetworkConfigurationError(
                "block_network=True is not supported because the agent needs network access "
                "to call the Anthropic API. Use cidr_allowlist instead to restrict network "
                "access while allowing the Anthropic API.\n\n"
                "Required CIDR for Anthropic API: 160.79.104.0/23\n"
                "Source: https://docs.anthropic.com/en/api/ip-addresses\n\n"
                "Example:\n"
                "  options = ModalAgentOptions(\n"
                '      cidr_allowlist=["160.79.104.0/23"],  # Anthropic API only\n'
                "      ...\n"
                "  )"
            )

    def _validate_api_key_config(self) -> str | None:
        """Validate API key configuration and return local key if needed.

        Returns:
            The local ANTHROPIC_API_KEY if it should be used, None otherwise.

        Raises:
            MissingAPIKeyError: If no API key is configured anywhere.
        """
        # Check if secrets are provided
        has_secrets = bool(self.options.secrets)

        # Check if ANTHROPIC_API_KEY is explicitly set in env options
        has_env_key = self.options.env and "ANTHROPIC_API_KEY" in self.options.env

        # If secrets or explicit env key provided, assume user knows what they're doing
        if has_secrets or has_env_key:
            return None

        # Check for local environment variable
        local_api_key = os.environ.get("ANTHROPIC_API_KEY")

        if local_api_key:
            # Warn user and suggest creating a proper Modal secret
            warnings.warn(
                "\n"
                "Using ANTHROPIC_API_KEY from local environment.\n"
                "For production use, create a Modal secret instead:\n\n"
                "  modal secret create anthropic-key ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY\n\n"
                "Then pass it to ModalAgentOptions:\n\n"
                "  options = ModalAgentOptions(\n"
                '      secrets=[modal.Secret.from_name("anthropic-key")],\n'
                "  )\n",
                UserWarning,
                stacklevel=4,
            )
            self._using_local_api_key = True
            return local_api_key

        # No API key found anywhere
        raise MissingAPIKeyError(
            "No Anthropic API key configured.\n\n"
            "Option 1: Create a Modal secret (recommended):\n"
            "  modal secret create anthropic-key ANTHROPIC_API_KEY=sk-ant-...\n\n"
            "  options = ModalAgentOptions(\n"
            '      secrets=[modal.Secret.from_name("anthropic-key")],\n'
            "  )\n\n"
            "Option 2: Set the environment variable locally:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    def _build_sandbox_kwargs(self) -> dict[str, Any]:
        """Build keyword arguments for sandbox creation.

        Returns:
            Dictionary of sandbox configuration options.

        Raises:
            NetworkConfigurationError: If network config is incompatible.
            MissingAPIKeyError: If no API key is configured.
        """
        # Validate configurations
        self._validate_network_config()
        local_api_key = self._validate_api_key_config()

        kwargs: dict[str, Any] = {
            "image": self._get_image(),
            "timeout": self.options.timeout,
        }

        if self.options.gpu:
            kwargs["gpu"] = self.options.gpu
        if self.options.cpu:
            kwargs["cpu"] = self.options.cpu
        if self.options.memory:
            kwargs["memory"] = self.options.memory
        if self.options.idle_timeout:
            kwargs["idle_timeout"] = self.options.idle_timeout

        # Volumes
        if self.options.volumes:
            kwargs["volumes"] = {str(k): v for k, v in self.options.volumes.items()}

        # Network file systems
        if self.options.network_file_systems:
            kwargs["network_file_systems"] = {
                str(k): v for k, v in self.options.network_file_systems.items()
            }

        # Secrets
        if self.options.secrets:
            kwargs["secrets"] = self.options.secrets

        # Environment variables - merge local API key if needed
        env_vars: dict[str, str] = {}
        if self.options.env:
            env_vars.update(self.options.env)
        if local_api_key:
            env_vars["ANTHROPIC_API_KEY"] = local_api_key

        # Encrypted ports for tunnel support
        # Note: encrypted_ports is required for environment variables to work in Modal
        if self.options.encrypted_ports:
            kwargs["encrypted_ports"] = self.options.encrypted_ports
        elif env_vars:
            kwargs["encrypted_ports"] = []  # Required for env to work

        if env_vars:
            kwargs["environment"] = env_vars

        # Network restrictions
        if self.options.block_network:
            kwargs["block_network"] = True
        elif self.options.cidr_allowlist:
            kwargs["cidr_allowlist"] = self.options.cidr_allowlist

        # Cloud/region
        if self.options.cloud:
            kwargs["cloud"] = self.options.cloud
        if self.options.region:
            kwargs["region"] = self.options.region

        return kwargs

    async def create_sandbox(self) -> modal.Sandbox:
        """Create and start a new Modal sandbox.

        Returns:
            The created sandbox.

        Raises:
            SandboxCreationError: If sandbox creation fails.
        """
        try:
            if self.options.verbose:
                print("Looking up Modal app...", flush=True)

            # Get or create the app
            if self.options.app:
                self._app = self.options.app
            else:
                # Use App.lookup for running outside Modal containers
                app_name = self.options.name or "modal-agents-sdk"
                self._app = await modal.App.lookup.aio(app_name, create_if_missing=True)

            if self.options.verbose:
                print(f"Got app: {self._app}", flush=True)

            kwargs = self._build_sandbox_kwargs()
            kwargs["app"] = self._app

            if self.options.verbose:
                print(f"Creating sandbox with options: {kwargs}", flush=True)

            self._sandbox = await modal.Sandbox.create.aio(**kwargs)

            if self.options.verbose:
                print(f"Sandbox created: {self._sandbox}", flush=True)

            return self._sandbox

        except Exception as e:
            raise SandboxCreationError(f"Failed to create sandbox: {e}") from e

    async def execute_agent(
        self,
        prompt: str,
        resume: str | None = None,
        host_hooks: ModalAgentHooks | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the Claude agent in the sandbox using the Python SDK.

        This method runs a Python script inside the sandbox that uses the
        claude-agent-sdk package to execute the agent query.

        Args:
            prompt: The prompt to send to the agent.
            resume: Optional session ID to resume a previous conversation.
            host_hooks: Optional hooks configuration for host-side interception.

        Yields:
            Parsed message dictionaries from the agent.

        Raises:
            CLINotInstalledError: If claude-agent-sdk is not installed.
            AgentExecutionError: If agent execution fails.
            SandboxTimeoutError: If execution times out.
            SandboxTerminatedError: If sandbox is terminated unexpectedly.
        """
        # Check if host_hooks or host_tools are configured
        hooks_config = host_hooks or getattr(self.options, "host_hooks", None)
        host_tools_config = getattr(self.options, "host_tools", None)

        if hooks_config is not None or host_tools_config is not None:
            # Use streaming mode with hook/tool interception
            async for message in self._execute_with_host_features(
                prompt, resume, hooks_config, host_tools_config
            ):
                yield message
            return

        # Standard execution without hooks
        if self._sandbox is None:
            await self.create_sandbox()
            assert self._sandbox is not None

        # Build SDK options as JSON
        sdk_options = build_sdk_options(self.options, resume=resume)
        options_json = json.dumps(sdk_options)

        # Command to execute the runner script
        # We use python -c to execute the script inline
        full_command = [
            "python",
            "-c",
            RUNNER_SCRIPT,
            options_json,
            prompt,
        ]

        if self.options.verbose:
            print(f"Executing runner script with options: {sdk_options}", flush=True)
            print(f"Prompt: {prompt}", flush=True)

        try:
            # Execute the command
            if self.options.verbose:
                print("Starting exec...", flush=True)
            process = await self._sandbox.exec.aio(*full_command)
            if self.options.verbose:
                print("Exec started, waiting for completion...", flush=True)

            # Wait for completion first
            await process.wait.aio()
            exit_code = process.returncode

            if self.options.verbose:
                print(f"Process completed with exit code: {exit_code}", flush=True)

            if exit_code == 1:
                # Check if it's a module not found error
                stderr_content = process.stderr.read()
                if "ModuleNotFoundError" in stderr_content and "claude_agent_sdk" in stderr_content:
                    raise CLINotInstalledError(
                        "claude-agent-sdk package not found. Make sure 'claude-agent-sdk' "
                        "is installed in the sandbox image."
                    )

            # Read all stdout
            stdout_content = process.stdout.read()
            if self.options.verbose:
                print(f"Stdout length: {len(stdout_content)} bytes", flush=True)
                # Debug: show first 500 chars of raw stdout
                print(f"Stdout preview: {stdout_content[:500]}", flush=True)

            # Parse and yield messages
            for line in stdout_content.split("\n"):
                if self.options.verbose and line.strip():
                    print(f"Processing line: {line[:100]}...", flush=True)

                parsed_msg = parse_stream_message(line)
                if parsed_msg is not None:
                    # Strip the _type wrapper if present (from emit_agent_message)
                    if parsed_msg.get("_type") == "message":
                        parsed_msg = {k: v for k, v in parsed_msg.items() if k != "_type"}
                    yield parsed_msg

            # Always show stderr in verbose mode
            stderr_content = process.stderr.read()
            if self.options.verbose and stderr_content:
                print(f"Stderr: {stderr_content[:2000]}", flush=True)

            if exit_code != 0:
                raise AgentExecutionError(
                    f"Agent execution failed with exit code {exit_code}: {stderr_content}",
                    exit_code=exit_code,
                )

        except TimeoutError as e:
            raise SandboxTimeoutError(f"Sandbox execution timed out: {e}") from e
        except modal.exception.SandboxTerminatedError as e:
            raise SandboxTerminatedError(f"Sandbox was terminated: {e}") from e

    async def _execute_with_host_features(
        self,
        prompt: str,
        resume: str | None,
        hooks: ModalAgentHooks | None,
        host_tools: list[HostToolServer] | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute agent with bidirectional hook and tool interception.

        This method uses streaming stdout/stdin communication to allow
        host-side hooks to intercept tool calls and host-side tools to
        be executed on the host machine.

        Args:
            prompt: The prompt to send to the agent.
            resume: Optional session ID to resume.
            hooks: Optional hook configuration with callbacks.
            host_tools: Optional list of host-side tool servers.

        Yields:
            Parsed message dictionaries from the agent.
        """
        if self._sandbox is None:
            await self.create_sandbox()
            assert self._sandbox is not None

        # Build SDK options as JSON
        sdk_options = build_sdk_options(self.options, resume=resume)

        # Add MCP tool names to allowed_tools for host tools
        if host_tools:
            allowed_tools = list(sdk_options.get("allowed_tools", []))
            for server in host_tools:
                for tool in server.tools:
                    # MCP tools are named with pattern: mcp__{server_name}__{tool_name}
                    mcp_tool_name = f"mcp__{server.name}__{tool.name}"
                    if mcp_tool_name not in allowed_tools:
                        allowed_tools.append(mcp_tool_name)
            sdk_options["allowed_tools"] = allowed_tools

            # Include host tools config in the options JSON
            sdk_options["_host_tools"] = [
                {
                    "name": server.name,
                    "version": server.version,
                    "tools": server.get_tool_definitions(),
                }
                for server in host_tools
            ]

        # Include hooks flag in options
        if hooks:
            sdk_options["_enable_hooks"] = True

        options_json = json.dumps(sdk_options)

        # Command to execute the runner script
        full_command = [
            "python",
            "-c",
            RUNNER_SCRIPT,
            options_json,
            prompt,
        ]

        if self.options.verbose:
            print(f"Executing with host features, options: {sdk_options}", flush=True)
            print(f"Prompt: {prompt}", flush=True)
            if host_tools:
                print(f"Host tools: {[s.name for s in host_tools]}", flush=True)

        # Create dispatchers
        hook_dispatcher = HookDispatcher(hooks) if hooks else None
        tool_dispatcher = HostToolDispatcher(host_tools) if host_tools else None

        try:
            if self.options.verbose:
                print("Starting exec with host features...", flush=True)

            # Start the process (don't wait for completion - we stream)
            process = await self._sandbox.exec.aio(*full_command)

            if self.options.verbose:
                print("Exec started, streaming output...", flush=True)

            # Stream stdout line by line and handle hooks/tools
            async for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                if self.options.verbose:
                    print(f"Received line: {line[:100]}...", flush=True)

                # Parse the message
                message = parse_hook_message(line)
                if message is None:
                    continue

                if is_hook_request(message) and hook_dispatcher:
                    # Handle hook request
                    hook_event = message.get("hook_event", "")

                    if hook_event == "PreToolUse":
                        # Dispatch to pre-tool-use hooks and send response
                        response = await hook_dispatcher.dispatch_pre_tool_use(message)
                        response_json = json.dumps(response) + "\n"

                        if self.options.verbose:
                            print(f"Sending hook response: {response_json.strip()}", flush=True)

                        # Write response to process stdin
                        process.stdin.write(response_json.encode())
                        await process.stdin.drain.aio()

                    elif hook_event == "PostToolUse":
                        # Fire-and-forget post-tool-use hooks
                        await hook_dispatcher.dispatch_post_tool_use(message)

                elif is_host_tool_request(message) and tool_dispatcher:
                    # Handle host tool request
                    if self.options.verbose:
                        tool_name = message.get("tool_name", "")
                        server_name = message.get("server_name", "")
                        print(f"Dispatching host tool: {server_name}:{tool_name}", flush=True)

                    response = await tool_dispatcher.dispatch(message)
                    response_json = json.dumps(response) + "\n"

                    if self.options.verbose:
                        is_error = response.get("is_error", False)
                        print(f"Sending tool response (error={is_error})", flush=True)

                    # Write response to process stdin
                    process.stdin.write(response_json.encode())
                    await process.stdin.drain.aio()

                elif is_agent_message(message):
                    # Extract the actual message content (remove _type wrapper)
                    if "_type" in message:
                        # The actual message data is the rest of the dict
                        actual_message = {k: v for k, v in message.items() if k != "_type"}
                    else:
                        actual_message = message
                    yield actual_message

            # Wait for process to complete
            await process.wait.aio()
            exit_code = process.returncode

            if self.options.verbose:
                print(f"Process completed with exit code: {exit_code}", flush=True)

            if exit_code == 1:
                # Check if it's a module not found error
                stderr_content = process.stderr.read()
                if "ModuleNotFoundError" in stderr_content:
                    if "claude_agent_sdk" in stderr_content:
                        raise CLINotInstalledError(
                            "claude-agent-sdk package not found. Make sure 'claude-agent-sdk' "
                            "is installed in the sandbox image."
                        )

            stderr_content = process.stderr.read()
            if self.options.verbose and stderr_content:
                print(f"Stderr: {stderr_content[:2000]}", flush=True)

            if exit_code != 0:
                raise AgentExecutionError(
                    f"Agent execution failed with exit code {exit_code}: {stderr_content}",
                    exit_code=exit_code,
                )

        except TimeoutError as e:
            raise SandboxTimeoutError(f"Sandbox execution timed out: {e}") from e
        except modal.exception.SandboxTerminatedError as e:
            raise SandboxTerminatedError(f"Sandbox was terminated: {e}") from e

    async def terminate(self) -> None:
        """Terminate the sandbox and cleanup resources."""
        if self._sandbox is not None:
            try:
                await self._sandbox.terminate.aio()
            except Exception:
                pass  # Ignore errors during cleanup
            finally:
                self._sandbox = None

    def tunnels(self) -> dict[int, Any]:
        """Get tunnel URLs for exposed ports.

        Returns:
            Dictionary mapping port numbers to Tunnel objects.
            Each Tunnel has a .url attribute with the HTTPS tunnel URL.

        Raises:
            RuntimeError: If sandbox has not been created.
        """
        if self._sandbox is None:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")
        return self._sandbox.tunnels()

    @property
    def sandbox(self) -> modal.Sandbox | None:
        """Get the underlying Modal sandbox object.

        Returns:
            The Modal sandbox or None if not created.
        """
        return self._sandbox

    async def commit_volumes(self) -> None:
        """Commit any changes to mounted volumes."""
        if self.options.volumes:
            for volume in self.options.volumes.values():
                if hasattr(volume, "commit"):
                    try:
                        await volume.commit.aio()
                    except Exception:
                        pass  # Ignore commit errors

    async def __aenter__(self) -> SandboxManager:
        """Enter async context manager."""
        await self.create_sandbox()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        await self.commit_volumes()
        await self.terminate()
