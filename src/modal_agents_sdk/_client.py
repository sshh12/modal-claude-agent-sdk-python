"""ModalAgentClient for multi-turn conversations."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from ._options import ModalAgentOptions
from ._sandbox import SandboxManager
from ._types import Message

if TYPE_CHECKING:
    pass


class ModalAgentClient:
    """Client for multi-turn conversations with a Claude agent.

    The client maintains a persistent sandbox connection, allowing for
    multiple queries while preserving conversation context.

    Example:
        >>> async with ModalAgentClient(options=options) as client:
        ...     await client.query("First task")
        ...     async for msg in client.receive_response():
        ...         print(msg)
        ...
        ...     await client.query("Follow-up task")
        ...     async for msg in client.receive_response():
        ...         print(msg)
    """

    def __init__(self, options: ModalAgentOptions | None = None) -> None:
        """Initialize the client.

        Args:
            options: Optional configuration options. Uses defaults if not provided.
        """
        self.options = options or ModalAgentOptions()
        self._manager = SandboxManager(self.options)
        self._conversation_history: list[dict[str, Any]] = []
        self._pending_response: AsyncIterator[dict[str, Any]] | None = None
        self._is_connected = False
        self._session_id: str | None = None

    async def connect(self) -> None:
        """Establish connection to the sandbox.

        Creates the sandbox and prepares for queries.
        """
        if not self._is_connected:
            await self._manager.create_sandbox()
            self._is_connected = True

    async def disconnect(self) -> None:
        """Disconnect from the sandbox.

        Terminates the sandbox and cleans up resources.
        """
        if self._is_connected:
            await self._manager.commit_volumes()
            await self._manager.terminate()
            self._is_connected = False

    async def query(self, prompt: str) -> None:
        """Send a query to the agent.

        The response can be retrieved using receive_response().

        Args:
            prompt: The prompt to send to the agent.
        """
        if not self._is_connected:
            await self.connect()

        # Store the prompt for context
        self._conversation_history.append({"role": "user", "content": prompt})

        # Use session resumption for multi-turn conversations
        # The SDK's --resume flag maintains full conversation context
        self._pending_response = self._manager.execute_agent(
            prompt,
            resume=self._session_id,
        )

    def _build_conversation_prompt(self, new_prompt: str) -> str:
        """Build a prompt that includes conversation history.

        For now, we just use the new prompt. In a more sophisticated
        implementation, we might use the CLI's continue feature or
        format the conversation history.

        Args:
            new_prompt: The new prompt to send.

        Returns:
            The formatted prompt string.
        """
        # For multi-turn support, we could:
        # 1. Use --resume with conversation ID
        # 2. Format history into the prompt
        # 3. Use stdin for conversation continuation
        #
        # For now, we just send the new prompt
        return new_prompt

    async def receive_response(self) -> AsyncIterator[Message]:
        """Receive the response from the last query.

        Yields:
            Message objects from the agent response.

        Raises:
            RuntimeError: If no query has been sent.
        """
        if self._pending_response is None:
            raise RuntimeError("No pending response. Call query() first.")

        from ._query import _convert_to_message

        async for raw_message in self._pending_response:
            message = _convert_to_message(raw_message)

            # Capture session_id from ResultMessage for multi-turn
            if raw_message.get("subtype") in ("success", "error"):
                session_id = raw_message.get("session_id")
                if session_id:
                    self._session_id = session_id

            # Store assistant responses in history
            if raw_message.get("type") == "assistant":
                self._conversation_history.append({
                    "role": "assistant",
                    "content": raw_message.get("content", []),
                })
            yield message

        self._pending_response = None

    async def query_and_receive(self, prompt: str) -> AsyncIterator[Message]:
        """Send a query and receive the response in one call.

        This is a convenience method that combines query() and receive_response().

        Args:
            prompt: The prompt to send to the agent.

        Yields:
            Message objects from the agent response.
        """
        await self.query(prompt)
        async for message in self.receive_response():
            yield message

    def get_conversation_history(self) -> list[dict[str, Any]]:
        """Get the conversation history.

        Returns:
            List of conversation messages.
        """
        return list(self._conversation_history)

    def clear_history(self) -> None:
        """Clear the conversation history and reset session."""
        self._conversation_history = []
        self._session_id = None

    def export_history(self) -> str:
        """Export conversation history as JSON.

        Returns:
            JSON string of conversation history.
        """
        return json.dumps(self._conversation_history, indent=2)

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to a sandbox.

        Returns:
            True if connected, False otherwise.
        """
        return self._is_connected

    @property
    def session_id(self) -> str | None:
        """Get the current session ID.

        Returns:
            The session ID if a query has been made, None otherwise.
        """
        return self._session_id

    async def __aenter__(self) -> ModalAgentClient:
        """Enter async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        await self.disconnect()
