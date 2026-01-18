"""Tests for error classes."""

import pytest

from modal_agents_sdk import (
    AgentExecutionError,
    CLINotInstalledError,
    ImageBuildError,
    MissingAPIKeyError,
    ModalAgentError,
    NetworkConfigurationError,
    ResourceError,
    SandboxCreationError,
    SandboxTerminatedError,
    SandboxTimeoutError,
    VolumeError,
)


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_all_errors_inherit_from_modal_agent_error(self):
        """Test that all custom errors inherit from ModalAgentError."""
        error_classes = [
            SandboxCreationError,
            SandboxTimeoutError,
            SandboxTerminatedError,
            ImageBuildError,
            VolumeError,
            ResourceError,
            CLINotInstalledError,
            AgentExecutionError,
            NetworkConfigurationError,
            MissingAPIKeyError,
        ]

        for error_class in error_classes:
            assert issubclass(error_class, ModalAgentError)
            assert issubclass(error_class, Exception)

    def test_modal_agent_error_is_base(self):
        """Test that ModalAgentError is the base exception."""
        error = ModalAgentError("test error")
        assert str(error) == "test error"
        assert isinstance(error, Exception)

    def test_sandbox_creation_error(self):
        """Test SandboxCreationError."""
        error = SandboxCreationError("Failed to create sandbox")
        assert str(error) == "Failed to create sandbox"
        assert isinstance(error, ModalAgentError)

    def test_sandbox_timeout_error(self):
        """Test SandboxTimeoutError."""
        error = SandboxTimeoutError("Execution timed out")
        assert str(error) == "Execution timed out"
        assert isinstance(error, ModalAgentError)

    def test_sandbox_terminated_error(self):
        """Test SandboxTerminatedError."""
        error = SandboxTerminatedError("Sandbox was terminated")
        assert str(error) == "Sandbox was terminated"
        assert isinstance(error, ModalAgentError)

    def test_image_build_error(self):
        """Test ImageBuildError."""
        error = ImageBuildError("Failed to build image")
        assert str(error) == "Failed to build image"
        assert isinstance(error, ModalAgentError)

    def test_volume_error(self):
        """Test VolumeError."""
        error = VolumeError("Volume mount failed")
        assert str(error) == "Volume mount failed"
        assert isinstance(error, ModalAgentError)

    def test_resource_error(self):
        """Test ResourceError."""
        error = ResourceError("GPU not available")
        assert str(error) == "GPU not available"
        assert isinstance(error, ModalAgentError)

    def test_cli_not_installed_error(self):
        """Test CLINotInstalledError."""
        error = CLINotInstalledError("CLI not found")
        assert str(error) == "CLI not found"
        assert isinstance(error, ModalAgentError)

    def test_agent_execution_error(self):
        """Test AgentExecutionError with exit code."""
        error = AgentExecutionError("Command failed", exit_code=1)
        assert str(error) == "Command failed"
        assert error.exit_code == 1
        assert isinstance(error, ModalAgentError)

    def test_agent_execution_error_no_exit_code(self):
        """Test AgentExecutionError without exit code."""
        error = AgentExecutionError("Unknown failure")
        assert str(error) == "Unknown failure"
        assert error.exit_code is None

    def test_network_configuration_error(self):
        """Test NetworkConfigurationError."""
        error = NetworkConfigurationError("block_network not supported")
        assert str(error) == "block_network not supported"
        assert isinstance(error, ModalAgentError)

    def test_missing_api_key_error(self):
        """Test MissingAPIKeyError."""
        error = MissingAPIKeyError("No API key configured")
        assert str(error) == "No API key configured"
        assert isinstance(error, ModalAgentError)


class TestErrorCatching:
    """Tests for catching errors with except blocks."""

    def test_catch_specific_error(self):
        """Test catching a specific error type."""
        with pytest.raises(SandboxTimeoutError):
            raise SandboxTimeoutError("timeout")

    def test_catch_base_error(self):
        """Test catching base ModalAgentError catches all custom errors."""
        with pytest.raises(ModalAgentError):
            raise SandboxCreationError("creation failed")

        with pytest.raises(ModalAgentError):
            raise ImageBuildError("build failed")

        with pytest.raises(ModalAgentError):
            raise AgentExecutionError("execution failed", exit_code=1)

    def test_error_handling_pattern(self):
        """Test typical error handling pattern."""

        def simulate_error(error_type: str):
            if error_type == "timeout":
                raise SandboxTimeoutError("timed out")
            elif error_type == "creation":
                raise SandboxCreationError("failed to create")
            elif error_type == "execution":
                raise AgentExecutionError("failed", exit_code=1)

        # Test specific handling
        try:
            simulate_error("timeout")
        except SandboxTimeoutError as e:
            assert "timed out" in str(e)

        # Test base class handling
        try:
            simulate_error("creation")
        except ModalAgentError as e:
            assert isinstance(e, SandboxCreationError)

        # Test exit code access
        try:
            simulate_error("execution")
        except AgentExecutionError as e:
            assert e.exit_code == 1
