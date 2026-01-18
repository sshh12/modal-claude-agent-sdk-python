"""Tests for query() function and related utilities."""

from modal_agents_sdk import ModalAgentOptions
from modal_agents_sdk._utils import build_sdk_options, parse_stream_message


class TestBuildSdkOptions:
    """Tests for SDK options building."""

    def test_basic_options(self):
        """Test basic SDK options are included."""
        options = ModalAgentOptions()
        sdk_options = build_sdk_options(options)

        assert "cwd" in sdk_options
        assert sdk_options["cwd"] == "/workspace"

    def test_system_prompt(self):
        """Test system prompt option."""
        options = ModalAgentOptions(system_prompt="You are helpful")
        sdk_options = build_sdk_options(options)

        assert sdk_options["system_prompt"] == "You are helpful"

    def test_allowed_tools(self):
        """Test allowed tools option."""
        options = ModalAgentOptions(allowed_tools=["Read", "Write", "Bash"])
        sdk_options = build_sdk_options(options)

        assert sdk_options["allowed_tools"] == ["Read", "Write", "Bash"]

    def test_disallowed_tools(self):
        """Test disallowed tools option."""
        options = ModalAgentOptions(disallowed_tools=["Bash"])
        sdk_options = build_sdk_options(options)

        assert sdk_options["disallowed_tools"] == ["Bash"]

    def test_max_turns(self):
        """Test max turns option."""
        options = ModalAgentOptions(max_turns=5)
        sdk_options = build_sdk_options(options)

        assert sdk_options["max_turns"] == 5

    def test_permission_mode(self):
        """Test permission mode option."""
        options = ModalAgentOptions(permission_mode="bypassPermissions")
        sdk_options = build_sdk_options(options)

        assert sdk_options["permission_mode"] == "bypassPermissions"

    def test_model(self):
        """Test model option."""
        options = ModalAgentOptions(model="claude-sonnet-4-20250514")
        sdk_options = build_sdk_options(options)

        assert sdk_options["model"] == "claude-sonnet-4-20250514"

    def test_cwd_custom_path(self):
        """Test working directory option."""
        options = ModalAgentOptions(cwd="/custom/path")
        sdk_options = build_sdk_options(options)

        assert sdk_options["cwd"] == "/custom/path"

    def test_mcp_servers(self):
        """Test MCP servers option."""
        mcp_config = {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
            }
        }
        options = ModalAgentOptions(mcp_servers=mcp_config)
        sdk_options = build_sdk_options(options)

        assert sdk_options["mcp_servers"] == mcp_config

    def test_output_format(self):
        """Test output format option."""
        output_format = {"type": "json", "schema": {}}
        options = ModalAgentOptions(output_format=output_format)
        sdk_options = build_sdk_options(options)

        assert sdk_options["output_format"] == output_format

    def test_agents_config(self):
        """Test custom agents option."""
        agents_config = {"researcher": {"system_prompt": "You are a researcher"}}
        options = ModalAgentOptions(agents=agents_config)
        sdk_options = build_sdk_options(options)

        assert sdk_options["agents"] == agents_config

    def test_modal_options_not_included(self):
        """Test that Modal-specific options are not in SDK options."""
        options = ModalAgentOptions(
            gpu="A10G",
            memory=8192,
            timeout=1800,
            verbose=True,
        )
        sdk_options = build_sdk_options(options)

        # Modal options should not be passed to SDK
        assert "gpu" not in sdk_options
        assert "memory" not in sdk_options
        assert "timeout" not in sdk_options
        assert "verbose" not in sdk_options

    def test_none_values_not_included(self):
        """Test that None values are not included."""
        options = ModalAgentOptions(
            system_prompt=None,
            max_turns=None,
            model=None,
        )
        sdk_options = build_sdk_options(options)

        # None values should not be in the options (except cwd which has default)
        assert "system_prompt" not in sdk_options
        assert "max_turns" not in sdk_options
        assert "model" not in sdk_options
        assert "cwd" in sdk_options  # cwd always has a value


class TestParseStreamMessage:
    """Tests for parsing stream messages."""

    def test_valid_json(self):
        """Test parsing valid JSON."""
        line = '{"type": "assistant", "content": []}'
        result = parse_stream_message(line)

        assert result is not None
        assert result["type"] == "assistant"
        assert result["content"] == []

    def test_empty_line(self):
        """Test parsing empty line."""
        result = parse_stream_message("")
        assert result is None

        result = parse_stream_message("   ")
        assert result is None

    def test_invalid_json(self):
        """Test parsing invalid JSON."""
        result = parse_stream_message("not json")
        assert result is None

        result = parse_stream_message("{invalid}")
        assert result is None

    def test_line_with_whitespace(self):
        """Test parsing line with leading/trailing whitespace."""
        line = '  {"type": "user"}  \n'
        result = parse_stream_message(line)

        assert result is not None
        assert result["type"] == "user"

    def test_complex_message(self):
        """Test parsing complex message structure."""
        line = '{"type": "assistant", "content": [{"type": "text", "text": "Hello"}], "model": "claude"}'
        result = parse_stream_message(line)

        assert result is not None
        assert result["type"] == "assistant"
        assert len(result["content"]) == 1
        assert result["content"][0]["text"] == "Hello"
        assert result["model"] == "claude"
