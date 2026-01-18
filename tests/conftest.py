"""Pytest configuration and fixtures for Modal Agents SDK tests."""

import pytest


@pytest.fixture
def default_options():
    """Create default ModalAgentOptions for testing."""
    from modal_agents_sdk import ModalAgentOptions

    return ModalAgentOptions()


@pytest.fixture
def custom_options():
    """Create customized ModalAgentOptions for testing."""
    from modal_agents_sdk import ModalAgentOptions

    return ModalAgentOptions(
        system_prompt="You are a test assistant",
        allowed_tools=["Read", "Write"],
        max_turns=5,
        gpu="A10G",
        memory=8192,
        timeout=1800,
    )
