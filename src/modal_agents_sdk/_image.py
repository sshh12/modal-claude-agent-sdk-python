"""ModalAgentImage class for customizing the sandbox container image."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import modal

from ._constants import DEFAULT_PYTHON_VERSION
from ._errors import ImageBuildError

if TYPE_CHECKING:
    from modal import Image


class ModalAgentImage:
    """A fluent builder for customizing the Modal sandbox image.

    The image includes the Claude Agent SDK Python package by default,
    which bundles all necessary dependencies for running Claude agents.

    Example:
        >>> image = (
        ...     ModalAgentImage.default()
        ...     .pip_install("pandas", "numpy")
        ...     .apt_install("ffmpeg")
        ... )
    """

    def __init__(self, _base_image: Image) -> None:
        """Initialize with a base Modal image.

        Args:
            _base_image: The underlying Modal image.
        """
        self._image = _base_image

    @classmethod
    def default(
        cls,
        python_version: str = DEFAULT_PYTHON_VERSION,
    ) -> Self:
        """Create the default image with Python and Claude Agent SDK.

        The image includes:
        - Python (specified version)
        - Git and essential tools
        - claude-agent-sdk package (which bundles the Claude Code CLI)

        Args:
            python_version: Python version to use (default: "3.11").

        Returns:
            A new ModalAgentImage instance.
        """
        base = (
            modal.Image.debian_slim(python_version=python_version)
            .apt_install("git", "ca-certificates", "curl")
            .pip_install("claude-agent-sdk>=0.1.20")
            .workdir("/workspace")
        )
        return cls(_base_image=base)

    @classmethod
    def from_registry(
        cls,
        tag: str,
        *,
        add_python: str | None = None,
        force_build: bool = False,
        secret: modal.Secret | None = None,
    ) -> Self:
        """Create an image from a Docker registry.

        Args:
            tag: The Docker image tag (e.g., "python:3.11-slim").
            add_python: Optional Python version to add.
            force_build: Force rebuild even if cached.
            secret: Secret for private registry authentication.

        Returns:
            A new ModalAgentImage instance.
        """
        kwargs: dict = {}
        if add_python:
            kwargs["add_python"] = add_python
        if force_build:
            kwargs["force_build"] = force_build
        if secret:
            kwargs["secret"] = secret

        base = modal.Image.from_registry(tag, **kwargs)
        return cls(_base_image=base)

    @classmethod
    def from_dockerfile(
        cls,
        path: str | Path,
        *,
        context_mount: modal.Mount | None = None,
        force_build: bool = False,
        add_python: str | None = None,
    ) -> Self:
        """Create an image from a Dockerfile.

        Args:
            path: Path to the Dockerfile.
            context_mount: Mount for the build context.
            force_build: Force rebuild even if cached.
            add_python: Optional Python version to add.

        Returns:
            A new ModalAgentImage instance.
        """
        kwargs: dict = {}
        if context_mount:
            kwargs["context_mount"] = context_mount
        if force_build:
            kwargs["force_build"] = force_build
        if add_python:
            kwargs["add_python"] = add_python

        base = modal.Image.from_dockerfile(str(path), **kwargs)
        return cls(_base_image=base)

    def pip_install(self, *packages: str, find_links: str | None = None) -> Self:
        """Install Python packages using pip.

        Args:
            *packages: Package names to install.
            find_links: Optional URL for finding packages.

        Returns:
            A new ModalAgentImage with the packages installed.
        """
        kwargs: dict = {}
        if find_links:
            kwargs["find_links"] = find_links

        new_image = self._image.pip_install(*packages, **kwargs)
        return self.__class__(_base_image=new_image)

    def apt_install(self, *packages: str) -> Self:
        """Install system packages using apt.

        Args:
            *packages: Package names to install.

        Returns:
            A new ModalAgentImage with the packages installed.
        """
        new_image = self._image.apt_install(*packages)
        return self.__class__(_base_image=new_image)

    def run_commands(self, *commands: str) -> Self:
        """Run shell commands in the image.

        Args:
            *commands: Shell commands to run.

        Returns:
            A new ModalAgentImage with the commands executed.
        """
        new_image = self._image.run_commands(*commands)
        return self.__class__(_base_image=new_image)

    def add_local_file(
        self,
        local_path: str | Path,
        remote_path: str | Path,
        *,
        copy: bool = False,
    ) -> Self:
        """Add a local file to the image.

        Args:
            local_path: Path to the local file.
            remote_path: Path in the image where the file will be placed.
            copy: If True, copy instead of mount.

        Returns:
            A new ModalAgentImage with the file added.
        """
        new_image = self._image.add_local_file(str(local_path), str(remote_path), copy=copy)
        return self.__class__(_base_image=new_image)

    def add_local_dir(
        self,
        local_path: str | Path,
        remote_path: str | Path,
        *,
        copy: bool = False,
    ) -> Self:
        """Add a local directory to the image.

        Args:
            local_path: Path to the local directory.
            remote_path: Path in the image where the directory will be placed.
            copy: If True, copy instead of mount.

        Returns:
            A new ModalAgentImage with the directory added.
        """
        new_image = self._image.add_local_dir(str(local_path), str(remote_path), copy=copy)
        return self.__class__(_base_image=new_image)

    def env(self, vars: dict[str, str]) -> Self:
        """Set environment variables in the image.

        Args:
            vars: Dictionary of environment variable names and values.

        Returns:
            A new ModalAgentImage with the environment variables set.
        """
        new_image = self._image.env(vars)
        return self.__class__(_base_image=new_image)

    def workdir(self, path: str | Path) -> Self:
        """Set the working directory in the image.

        Args:
            path: Path to set as the working directory.

        Returns:
            A new ModalAgentImage with the working directory set.
        """
        new_image = self._image.workdir(str(path))
        return self.__class__(_base_image=new_image)

    @property
    def modal_image(self) -> Image:
        """Get the underlying Modal image.

        Returns:
            The Modal Image object.
        """
        return self._image

    def _validate(self) -> None:
        """Validate that the image is properly configured.

        Raises:
            ImageBuildError: If the image is not properly configured.
        """
        if self._image is None:
            raise ImageBuildError("Image has not been properly initialized")
