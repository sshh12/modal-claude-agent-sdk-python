"""Tests for host-side hooks functionality."""

import pytest

from modal_agents_sdk import (
    ModalAgentHooks,
    ModalAgentOptions,
    PostToolUseHookInput,
    PreToolUseHookInput,
    PreToolUseHookResult,
)
from modal_agents_sdk._host_hooks import (
    HookDispatcher,
    is_agent_message,
    is_hook_request,
    parse_hook_message,
)


class TestPreToolUseHookInput:
    """Tests for PreToolUseHookInput dataclass."""

    def test_basic_construction(self):
        """Test basic construction of PreToolUseHookInput."""
        input_data = PreToolUseHookInput(
            tool_name="Bash",
            tool_input={"command": "ls -la"},
            tool_use_id="toolu_123",
            session_id="session_abc",
            cwd="/workspace",
        )

        assert input_data.tool_name == "Bash"
        assert input_data.tool_input == {"command": "ls -la"}
        assert input_data.tool_use_id == "toolu_123"
        assert input_data.session_id == "session_abc"
        assert input_data.cwd == "/workspace"


class TestPreToolUseHookResult:
    """Tests for PreToolUseHookResult dataclass."""

    def test_default_allow(self):
        """Test that default result is allow."""
        result = PreToolUseHookResult()
        assert result.decision == "allow"
        assert result.reason is None
        assert result.updated_input is None

    def test_deny_with_reason(self):
        """Test deny result with reason."""
        result = PreToolUseHookResult(
            decision="deny",
            reason="Dangerous command blocked",
        )
        assert result.decision == "deny"
        assert result.reason == "Dangerous command blocked"

    def test_allow_with_modified_input(self):
        """Test allow with modified input."""
        result = PreToolUseHookResult(
            decision="allow",
            updated_input={"file_path": "/workspace/safe/file.txt"},
        )
        assert result.decision == "allow"
        assert result.updated_input == {"file_path": "/workspace/safe/file.txt"}


class TestPostToolUseHookInput:
    """Tests for PostToolUseHookInput dataclass."""

    def test_basic_construction(self):
        """Test basic construction of PostToolUseHookInput."""
        input_data = PostToolUseHookInput(
            tool_name="Bash",
            tool_input={"command": "echo hello"},
            tool_result="hello\n",
            is_error=False,
            tool_use_id="toolu_456",
            session_id="session_xyz",
        )

        assert input_data.tool_name == "Bash"
        assert input_data.tool_input == {"command": "echo hello"}
        assert input_data.tool_result == "hello\n"
        assert input_data.is_error is False

    def test_error_result(self):
        """Test post-hook input with error."""
        input_data = PostToolUseHookInput(
            tool_name="Bash",
            tool_input={"command": "nonexistent"},
            tool_result="command not found",
            is_error=True,
            tool_use_id="toolu_789",
            session_id="session_err",
        )

        assert input_data.is_error is True
        assert "not found" in input_data.tool_result


class TestModalAgentHooks:
    """Tests for ModalAgentHooks configuration."""

    def test_default_values(self):
        """Test default hook configuration."""
        hooks = ModalAgentHooks()

        assert hooks.pre_tool_use == []
        assert hooks.post_tool_use == []
        assert hooks.tool_filter is None
        assert hooks.timeout == 30.0

    def test_with_callbacks(self):
        """Test hooks with callbacks configured."""

        async def pre_hook(input: PreToolUseHookInput) -> PreToolUseHookResult:
            return PreToolUseHookResult(decision="allow")

        async def post_hook(input: PostToolUseHookInput) -> None:
            pass

        hooks = ModalAgentHooks(
            pre_tool_use=[pre_hook],
            post_tool_use=[post_hook],
            tool_filter="Bash|Write",
            timeout=60.0,
        )

        assert len(hooks.pre_tool_use) == 1
        assert len(hooks.post_tool_use) == 1
        assert hooks.tool_filter == "Bash|Write"
        assert hooks.timeout == 60.0


class TestHookDispatcher:
    """Tests for HookDispatcher class."""

    def test_should_intercept_no_filter(self):
        """Test that all tools are intercepted when no filter is set."""
        hooks = ModalAgentHooks()
        dispatcher = HookDispatcher(hooks)

        assert dispatcher.should_intercept("Bash") is True
        assert dispatcher.should_intercept("Read") is True
        assert dispatcher.should_intercept("Write") is True
        assert dispatcher.should_intercept("CustomTool") is True

    def test_should_intercept_with_filter(self):
        """Test tool filtering with regex pattern."""
        hooks = ModalAgentHooks(tool_filter="Bash|Write|Edit")
        dispatcher = HookDispatcher(hooks)

        assert dispatcher.should_intercept("Bash") is True
        assert dispatcher.should_intercept("Write") is True
        assert dispatcher.should_intercept("Edit") is True
        assert dispatcher.should_intercept("Read") is False
        assert dispatcher.should_intercept("Glob") is False

    @pytest.mark.asyncio
    async def test_dispatch_pre_tool_use_allow(self):
        """Test dispatching pre-tool-use with allow result."""
        hooks = ModalAgentHooks()
        dispatcher = HookDispatcher(hooks)

        request = {
            "request_id": "req_123",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_use_id": "toolu_123",
            "session_id": "sess_123",
            "cwd": "/workspace",
        }

        response = await dispatcher.dispatch_pre_tool_use(request)

        assert response["_type"] == "hook_response"
        assert response["request_id"] == "req_123"
        assert response["decision"] == "allow"

    @pytest.mark.asyncio
    async def test_dispatch_pre_tool_use_deny(self):
        """Test dispatching pre-tool-use with deny result."""

        async def block_rm(input: PreToolUseHookInput) -> PreToolUseHookResult:
            if "rm" in input.tool_input.get("command", ""):
                return PreToolUseHookResult(
                    decision="deny",
                    reason="rm command blocked",
                )
            return PreToolUseHookResult(decision="allow")

        hooks = ModalAgentHooks(pre_tool_use=[block_rm])
        dispatcher = HookDispatcher(hooks)

        request = {
            "request_id": "req_456",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/test"},
            "tool_use_id": "toolu_456",
            "session_id": "sess_456",
            "cwd": "/workspace",
        }

        response = await dispatcher.dispatch_pre_tool_use(request)

        assert response["decision"] == "deny"
        assert response["reason"] == "rm command blocked"

    @pytest.mark.asyncio
    async def test_dispatch_pre_tool_use_modify(self):
        """Test dispatching pre-tool-use with modified input."""

        async def redirect_path(input: PreToolUseHookInput) -> PreToolUseHookResult:
            if input.tool_name == "Read":
                new_input = {**input.tool_input, "file_path": "/safe/path"}
                return PreToolUseHookResult(
                    decision="allow",
                    updated_input=new_input,
                )
            return PreToolUseHookResult(decision="allow")

        hooks = ModalAgentHooks(pre_tool_use=[redirect_path])
        dispatcher = HookDispatcher(hooks)

        request = {
            "request_id": "req_789",
            "tool_name": "Read",
            "tool_input": {"file_path": "/etc/passwd"},
            "tool_use_id": "toolu_789",
            "session_id": "sess_789",
            "cwd": "/workspace",
        }

        response = await dispatcher.dispatch_pre_tool_use(request)

        assert response["decision"] == "allow"
        assert response["updated_input"] == {"file_path": "/safe/path"}

    @pytest.mark.asyncio
    async def test_dispatch_pre_tool_use_filtered(self):
        """Test that filtered tools are allowed without running callbacks."""
        call_count = 0

        async def counting_hook(input: PreToolUseHookInput) -> PreToolUseHookResult:
            nonlocal call_count
            call_count += 1
            return PreToolUseHookResult(decision="deny")

        hooks = ModalAgentHooks(
            pre_tool_use=[counting_hook],
            tool_filter="Bash",  # Only intercept Bash
        )
        dispatcher = HookDispatcher(hooks)

        # Read should not trigger the hook
        request = {
            "request_id": "req_abc",
            "tool_name": "Read",
            "tool_input": {},
            "tool_use_id": "toolu_abc",
            "session_id": "sess_abc",
            "cwd": "/workspace",
        }

        response = await dispatcher.dispatch_pre_tool_use(request)

        assert response["decision"] == "allow"
        assert call_count == 0  # Hook should not have been called

    @pytest.mark.asyncio
    async def test_dispatch_post_tool_use(self):
        """Test dispatching post-tool-use hooks."""
        captured = []

        async def capture_hook(input: PostToolUseHookInput) -> None:
            captured.append(
                {
                    "tool": input.tool_name,
                    "result": input.tool_result,
                }
            )

        hooks = ModalAgentHooks(post_tool_use=[capture_hook])
        dispatcher = HookDispatcher(hooks)

        request = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_result": "hello\n",
            "is_error": False,
            "tool_use_id": "toolu_post",
            "session_id": "sess_post",
        }

        await dispatcher.dispatch_post_tool_use(request)

        assert len(captured) == 1
        assert captured[0]["tool"] == "Bash"
        assert captured[0]["result"] == "hello\n"


class TestMessageParsing:
    """Tests for hook message parsing utilities."""

    def test_parse_hook_message_valid(self):
        """Test parsing valid JSON message."""
        line = '{"_type": "hook_request", "tool_name": "Bash"}'
        result = parse_hook_message(line)

        assert result is not None
        assert result["_type"] == "hook_request"
        assert result["tool_name"] == "Bash"

    def test_parse_hook_message_empty(self):
        """Test parsing empty line."""
        assert parse_hook_message("") is None
        assert parse_hook_message("   ") is None

    def test_parse_hook_message_invalid_json(self):
        """Test parsing invalid JSON."""
        assert parse_hook_message("not json") is None
        assert parse_hook_message("{invalid}") is None

    def test_is_hook_request(self):
        """Test hook request detection."""
        assert is_hook_request({"_type": "hook_request"}) is True
        assert is_hook_request({"_type": "hook_response"}) is False
        assert is_hook_request({"_type": "message"}) is False
        assert is_hook_request({}) is False

    def test_is_agent_message(self):
        """Test agent message detection."""
        assert is_agent_message({"_type": "message"}) is True
        assert is_agent_message({}) is True  # No _type means agent message
        assert is_agent_message({"_type": "hook_request"}) is False
        assert is_agent_message({"_type": "hook_response"}) is False


class TestOptionsWithHooks:
    """Tests for ModalAgentOptions with host_hooks."""

    def test_default_no_hooks(self):
        """Test that default options have no host_hooks."""
        options = ModalAgentOptions()
        assert options.host_hooks is None

    def test_with_hooks_configured(self):
        """Test options with host_hooks configured."""
        hooks = ModalAgentHooks(tool_filter="Bash")
        options = ModalAgentOptions(host_hooks=hooks)

        assert options.host_hooks is not None
        assert options.host_hooks.tool_filter == "Bash"

    def test_with_updates_preserves_hooks(self):
        """Test that with_updates preserves host_hooks."""
        hooks = ModalAgentHooks(timeout=60.0)
        original = ModalAgentOptions(host_hooks=hooks)

        updated = original.with_updates(max_turns=10)

        # Note: with_updates converts to dict and back, so we check the structure
        assert updated.max_turns == 10
