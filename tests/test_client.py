"""Tests for ModalAgentClient."""

import pytest

from modal_agents_sdk import ModalAgentClient, ModalAgentOptions


class TestModalAgentClient:
    """Tests for ModalAgentClient class."""

    def test_init_with_default_options(self):
        """Test client initialization with default options."""
        client = ModalAgentClient()

        assert client.options is not None
        assert isinstance(client.options, ModalAgentOptions)
        assert client.is_connected is False

    def test_init_with_custom_options(self):
        """Test client initialization with custom options."""
        options = ModalAgentOptions(
            system_prompt="Test",
            max_turns=5,
        )
        client = ModalAgentClient(options=options)

        assert client.options.system_prompt == "Test"
        assert client.options.max_turns == 5
        assert client.is_connected is False

    def test_conversation_history_initially_empty(self):
        """Test that conversation history is empty initially."""
        client = ModalAgentClient()
        history = client.get_conversation_history()

        assert history == []

    def test_clear_history(self):
        """Test clearing conversation history."""
        client = ModalAgentClient()

        # Manually add some history for testing
        client._conversation_history = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": "response"},
        ]

        assert len(client.get_conversation_history()) == 2

        client.clear_history()

        assert len(client.get_conversation_history()) == 0

    def test_export_history_json(self):
        """Test exporting history as JSON."""
        import json

        client = ModalAgentClient()
        client._conversation_history = [
            {"role": "user", "content": "hello"},
        ]

        exported = client.export_history()

        # Should be valid JSON
        parsed = json.loads(exported)
        assert len(parsed) == 1
        assert parsed[0]["role"] == "user"
        assert parsed[0]["content"] == "hello"

    def test_get_conversation_history_returns_copy(self):
        """Test that get_conversation_history returns a copy."""
        client = ModalAgentClient()
        client._conversation_history = [{"role": "user", "content": "test"}]

        history = client.get_conversation_history()
        history.append({"role": "assistant", "content": "new"})

        # Original should be unchanged
        assert len(client._conversation_history) == 1

    def test_receive_response_without_query_raises(self):
        """Test that receive_response raises without a prior query."""
        client = ModalAgentClient()

        with pytest.raises(RuntimeError, match="No pending response"):
            # Can't iterate without calling query first
            async def try_receive():
                async for _ in client.receive_response():
                    pass

            import asyncio

            asyncio.get_event_loop().run_until_complete(try_receive())

    def test_is_connected_property(self):
        """Test is_connected property."""
        client = ModalAgentClient()

        assert client.is_connected is False

        # Manually set for testing
        client._is_connected = True
        assert client.is_connected is True

        client._is_connected = False
        assert client.is_connected is False
