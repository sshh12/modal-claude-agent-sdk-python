"""Tests for host-side tools functionality."""

import pytest

from modal_agents_sdk import (
    HostTool,
    HostToolServer,
    ModalAgentOptions,
    host_tool,
)
from modal_agents_sdk._host_tools import (
    HostToolDispatcher,
    _convert_input_schema,
    _python_type_to_json_schema,
    is_host_tool_request,
)


class TestHostToolDecorator:
    """Tests for @host_tool decorator."""

    def test_basic_decorator(self):
        """Test basic decorator usage."""

        @host_tool("get_value", "Get a value", {"key": str})
        async def get_value(args):
            return {"content": [{"type": "text", "text": args["key"]}]}

        assert isinstance(get_value, HostTool)
        assert get_value.name == "get_value"
        assert get_value.description == "Get a value"
        assert "properties" in get_value.input_schema
        assert "key" in get_value.input_schema["properties"]

    def test_decorator_with_full_schema(self):
        """Test decorator with full JSON Schema."""

        full_schema = {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL query"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["sql"],
        }

        @host_tool("query_db", "Query database", full_schema)
        async def query_db(args):
            return {"content": [{"type": "text", "text": "result"}]}

        assert query_db.input_schema == full_schema

    def test_decorator_sync_handler(self):
        """Test decorator with synchronous handler."""

        @host_tool("sync_tool", "A sync tool", {"value": int})
        def sync_tool(args):
            return {"content": [{"type": "text", "text": str(args["value"])}]}

        assert isinstance(sync_tool, HostTool)
        assert sync_tool.name == "sync_tool"


class TestHostTool:
    """Tests for HostTool dataclass."""

    def test_basic_construction(self):
        """Test basic construction of HostTool."""

        async def handler(args):
            return {"content": [{"type": "text", "text": "result"}]}

        tool = HostTool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"key": {"type": "string"}}},
            handler=handler,
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.handler == handler


class TestHostToolServer:
    """Tests for HostToolServer class."""

    def test_basic_construction(self):
        """Test basic construction of HostToolServer."""

        @host_tool("tool1", "First tool", {"a": str})
        async def tool1(args):
            return {"content": [{"type": "text", "text": "1"}]}

        @host_tool("tool2", "Second tool", {"b": int})
        async def tool2(args):
            return {"content": [{"type": "text", "text": "2"}]}

        server = HostToolServer(
            name="test-server",
            tools=[tool1, tool2],
            version="2.0.0",
        )

        assert server.name == "test-server"
        assert len(server.tools) == 2
        assert server.version == "2.0.0"

    def test_get_tool(self):
        """Test getting a tool by name."""

        @host_tool("my_tool", "My tool", {})
        async def my_tool(args):
            return {"content": []}

        server = HostToolServer(name="test", tools=[my_tool])

        assert server.get_tool("my_tool") is my_tool
        assert server.get_tool("nonexistent") is None

    def test_get_tool_definitions(self):
        """Test getting tool definitions for the agent."""

        @host_tool("get_secret", "Get a secret", {"key": str})
        async def get_secret(args):
            return {"content": [{"type": "text", "text": "secret"}]}

        server = HostToolServer(name="secrets", tools=[get_secret])
        definitions = server.get_tool_definitions()

        assert len(definitions) == 1
        assert definitions[0]["name"] == "get_secret"
        assert definitions[0]["description"] == "Get a secret"
        assert "inputSchema" in definitions[0]


class TestHostToolDispatcher:
    """Tests for HostToolDispatcher class."""

    def test_construction(self):
        """Test dispatcher construction."""

        @host_tool("tool1", "Tool 1", {})
        async def tool1(args):
            return {"content": []}

        server = HostToolServer(name="server1", tools=[tool1])
        dispatcher = HostToolDispatcher([server])

        assert dispatcher.get_tool("server1", "tool1") is tool1

    def test_get_tool_by_name(self):
        """Test getting tool by server and tool name."""

        @host_tool("tool_a", "Tool A", {})
        async def tool_a(args):
            return {"content": []}

        @host_tool("tool_b", "Tool B", {})
        async def tool_b(args):
            return {"content": []}

        server1 = HostToolServer(name="server1", tools=[tool_a])
        server2 = HostToolServer(name="server2", tools=[tool_b])
        dispatcher = HostToolDispatcher([server1, server2])

        assert dispatcher.get_tool("server1", "tool_a") is tool_a
        assert dispatcher.get_tool("server2", "tool_b") is tool_b
        assert dispatcher.get_tool("server1", "tool_b") is None

    @pytest.mark.asyncio
    async def test_dispatch_success(self):
        """Test successful tool dispatch."""

        @host_tool("echo", "Echo the input", {"message": str})
        async def echo_tool(args):
            return {"content": [{"type": "text", "text": args["message"]}]}

        server = HostToolServer(name="test", tools=[echo_tool])
        dispatcher = HostToolDispatcher([server])

        request = {
            "request_id": "req_123",
            "server_name": "test",
            "tool_name": "echo",
            "tool_input": {"message": "hello world"},
            "tool_use_id": "toolu_456",
        }

        response = await dispatcher.dispatch(request)

        assert response["_type"] == "host_tool_response"
        assert response["request_id"] == "req_123"
        assert response["is_error"] is False
        assert len(response["content"]) == 1
        assert response["content"][0]["text"] == "hello world"

    @pytest.mark.asyncio
    async def test_dispatch_tool_not_found(self):
        """Test dispatch when tool doesn't exist."""
        server = HostToolServer(name="test", tools=[])
        dispatcher = HostToolDispatcher([server])

        request = {
            "request_id": "req_789",
            "server_name": "test",
            "tool_name": "nonexistent",
            "tool_input": {},
            "tool_use_id": "toolu_abc",
        }

        response = await dispatcher.dispatch(request)

        assert response["is_error"] is True
        assert "not found" in response["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_dispatch_sync_handler(self):
        """Test dispatch with synchronous handler."""

        @host_tool("sync_echo", "Sync echo", {"msg": str})
        def sync_echo(args):
            return {"content": [{"type": "text", "text": args["msg"]}]}

        server = HostToolServer(name="sync", tools=[sync_echo])
        dispatcher = HostToolDispatcher([server])

        request = {
            "request_id": "req_sync",
            "server_name": "sync",
            "tool_name": "sync_echo",
            "tool_input": {"msg": "sync message"},
            "tool_use_id": "toolu_sync",
        }

        response = await dispatcher.dispatch(request)

        assert response["is_error"] is False
        assert response["content"][0]["text"] == "sync message"

    @pytest.mark.asyncio
    async def test_dispatch_handler_error(self):
        """Test dispatch when handler raises an error."""

        @host_tool("error_tool", "Tool that errors", {})
        async def error_tool(args):
            raise ValueError("Something went wrong")

        server = HostToolServer(name="err", tools=[error_tool])
        dispatcher = HostToolDispatcher([server])

        request = {
            "request_id": "req_err",
            "server_name": "err",
            "tool_name": "error_tool",
            "tool_input": {},
            "tool_use_id": "toolu_err",
        }

        response = await dispatcher.dispatch(request)

        assert response["is_error"] is True
        assert "Something went wrong" in response["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_dispatch_string_result(self):
        """Test dispatch with string result."""

        @host_tool("str_tool", "Returns string", {})
        async def str_tool(args):
            return "plain string result"

        server = HostToolServer(name="str", tools=[str_tool])
        dispatcher = HostToolDispatcher([server])

        request = {
            "request_id": "req_str",
            "server_name": "str",
            "tool_name": "str_tool",
            "tool_input": {},
            "tool_use_id": "toolu_str",
        }

        response = await dispatcher.dispatch(request)

        assert response["is_error"] is False
        assert response["content"][0]["text"] == "plain string result"


class TestSchemaConversion:
    """Tests for schema conversion utilities."""

    def test_python_type_to_json_schema(self):
        """Test Python type to JSON Schema conversion."""
        assert _python_type_to_json_schema(str) == {"type": "string"}
        assert _python_type_to_json_schema(int) == {"type": "integer"}
        assert _python_type_to_json_schema(float) == {"type": "number"}
        assert _python_type_to_json_schema(bool) == {"type": "boolean"}
        assert _python_type_to_json_schema(list) == {"type": "array"}
        assert _python_type_to_json_schema(dict) == {"type": "object"}

    def test_python_type_string_names(self):
        """Test conversion with string type names."""
        assert _python_type_to_json_schema("str") == {"type": "string"}
        assert _python_type_to_json_schema("int") == {"type": "integer"}

    def test_convert_simple_schema(self):
        """Test converting simplified schema format."""
        simple = {"key": str, "count": int}
        result = _convert_input_schema(simple)

        assert result["type"] == "object"
        assert "key" in result["properties"]
        assert result["properties"]["key"]["type"] == "string"
        assert "count" in result["properties"]
        assert result["properties"]["count"]["type"] == "integer"
        assert set(result["required"]) == {"key", "count"}

    def test_convert_full_schema_passthrough(self):
        """Test that full JSON Schema is passed through."""
        full = {
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        }
        result = _convert_input_schema(full)
        assert result == full


class TestMessageTypeHelpers:
    """Tests for message type helper functions."""

    def test_is_host_tool_request(self):
        """Test host tool request detection."""
        assert is_host_tool_request({"_type": "host_tool_request"}) is True
        assert is_host_tool_request({"_type": "host_tool_response"}) is False
        assert is_host_tool_request({"_type": "hook_request"}) is False
        assert is_host_tool_request({"_type": "message"}) is False
        assert is_host_tool_request({}) is False


class TestOptionsWithHostTools:
    """Tests for ModalAgentOptions with host_tools."""

    def test_default_no_host_tools(self):
        """Test that default options have no host_tools."""
        options = ModalAgentOptions()
        assert options.host_tools is None

    def test_with_host_tools_configured(self):
        """Test options with host_tools configured."""

        @host_tool("test_tool", "Test", {})
        async def test_tool(args):
            return {"content": []}

        server = HostToolServer(name="test", tools=[test_tool])
        options = ModalAgentOptions(host_tools=[server])

        assert options.host_tools is not None
        assert len(options.host_tools) == 1
        assert options.host_tools[0].name == "test"

    def test_with_updates_preserves_host_tools(self):
        """Test that with_updates handles host_tools."""

        @host_tool("tool", "Tool", {})
        async def tool(args):
            return {"content": []}

        server = HostToolServer(name="server", tools=[tool])
        original = ModalAgentOptions(host_tools=[server])

        updated = original.with_updates(max_turns=10)

        assert updated.max_turns == 10
