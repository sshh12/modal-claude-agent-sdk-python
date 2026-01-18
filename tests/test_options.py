"""Tests for ModalAgentOptions."""

from modal_agents_sdk import ModalAgentOptions
from modal_agents_sdk._constants import (
    DEFAULT_ALLOWED_TOOLS,
    DEFAULT_CWD,
    DEFAULT_PERMISSION_MODE,
    DEFAULT_TIMEOUT,
)


class TestModalAgentOptions:
    """Tests for ModalAgentOptions dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        options = ModalAgentOptions()

        assert options.system_prompt is None
        assert options.allowed_tools == list(DEFAULT_ALLOWED_TOOLS)
        assert options.disallowed_tools == []
        assert options.mcp_servers == {}
        assert options.max_turns is None
        assert options.permission_mode == DEFAULT_PERMISSION_MODE
        assert options.cwd == DEFAULT_CWD
        assert options.model is None
        assert options.image is None
        assert options.gpu is None
        assert options.cpu is None
        assert options.memory is None
        assert options.timeout == DEFAULT_TIMEOUT
        assert options.volumes == {}
        assert options.secrets == []
        assert options.block_network is False
        assert options.verbose is False

    def test_custom_values(self):
        """Test that custom values are set correctly."""
        options = ModalAgentOptions(
            system_prompt="Test prompt",
            allowed_tools=["Read", "Write"],
            max_turns=10,
            gpu="H100",
            memory=16384,
            timeout=7200,
            block_network=True,
            verbose=True,
        )

        assert options.system_prompt == "Test prompt"
        assert options.allowed_tools == ["Read", "Write"]
        assert options.max_turns == 10
        assert options.gpu == "H100"
        assert options.memory == 16384
        assert options.timeout == 7200
        assert options.block_network is True
        assert options.verbose is True

    def test_with_updates(self):
        """Test the with_updates method."""
        original = ModalAgentOptions(
            system_prompt="Original",
            max_turns=5,
        )

        updated = original.with_updates(
            system_prompt="Updated",
            gpu="A10G",
        )

        # Original should be unchanged
        assert original.system_prompt == "Original"
        assert original.gpu is None

        # Updated should have new values
        assert updated.system_prompt == "Updated"
        assert updated.max_turns == 5  # Preserved
        assert updated.gpu == "A10G"  # New value

    def test_mutable_defaults_are_independent(self):
        """Test that mutable defaults don't share state."""
        options1 = ModalAgentOptions()
        options2 = ModalAgentOptions()

        options1.allowed_tools.append("CustomTool")
        options1.volumes["/data"] = "volume"

        # options2 should not be affected
        assert "CustomTool" not in options2.allowed_tools
        assert "/data" not in options2.volumes

    def test_permission_mode_values(self):
        """Test valid permission mode values."""
        for mode in ["default", "acceptEdits", "bypassPermissions"]:
            options = ModalAgentOptions(permission_mode=mode)
            assert options.permission_mode == mode

    def test_cwd_as_path(self):
        """Test that cwd can be a Path object."""
        from pathlib import Path

        options = ModalAgentOptions(cwd=Path("/custom/path"))
        assert options.cwd == Path("/custom/path")
