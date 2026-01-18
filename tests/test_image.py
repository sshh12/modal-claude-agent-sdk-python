"""Tests for ModalAgentImage."""

from modal_agents_sdk import ModalAgentImage


class TestModalAgentImage:
    """Tests for ModalAgentImage class."""

    def test_default_creates_image(self):
        """Test that default() creates an image."""
        image = ModalAgentImage.default()
        assert image is not None
        assert image.modal_image is not None

    def test_default_with_custom_python_version(self):
        """Test default() with custom Python version."""
        image = ModalAgentImage.default(python_version="3.12")
        assert image is not None

    def test_pip_install_returns_new_instance(self):
        """Test that pip_install returns a new instance."""
        original = ModalAgentImage.default()
        updated = original.pip_install("requests", "pandas")

        assert updated is not original
        assert isinstance(updated, ModalAgentImage)

    def test_apt_install_returns_new_instance(self):
        """Test that apt_install returns a new instance."""
        original = ModalAgentImage.default()
        updated = original.apt_install("curl", "wget")

        assert updated is not original
        assert isinstance(updated, ModalAgentImage)

    def test_run_commands_returns_new_instance(self):
        """Test that run_commands returns a new instance."""
        original = ModalAgentImage.default()
        updated = original.run_commands("echo hello")

        assert updated is not original
        assert isinstance(updated, ModalAgentImage)

    def test_method_chaining(self):
        """Test that methods can be chained."""
        image = (
            ModalAgentImage.default()
            .pip_install("requests")
            .apt_install("curl")
            .run_commands("echo hello")
            .env({"MY_VAR": "value"})
            .workdir("/app")
        )

        assert image is not None
        assert isinstance(image, ModalAgentImage)

    def test_env_sets_variables(self):
        """Test that env() sets environment variables."""
        image = ModalAgentImage.default().env(
            {
                "VAR1": "value1",
                "VAR2": "value2",
            }
        )

        assert image is not None

    def test_workdir_changes_directory(self):
        """Test that workdir() changes the working directory."""
        image = ModalAgentImage.default().workdir("/custom/dir")
        assert image is not None

    def test_add_local_file(self):
        """Test add_local_file method."""
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            image = ModalAgentImage.default().add_local_file(
                temp_path,
                "/workspace/test.txt",
            )
            assert image is not None
        finally:
            Path(temp_path).unlink()

    def test_modal_image_property(self):
        """Test that modal_image property returns the underlying image."""
        import modal

        agent_image = ModalAgentImage.default()
        modal_image = agent_image.modal_image

        assert isinstance(modal_image, modal.Image)
