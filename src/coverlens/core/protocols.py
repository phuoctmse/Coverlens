"""The extension points: InputAdapter, Verifier, OutputWriter (no others)."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from coverlens.core.pack import PackConfig


@runtime_checkable
class InputAdapter[T](Protocol):
    """Reads one input file into core models."""

    def read(self, path: Path, pack: PackConfig) -> list[T]: ...
