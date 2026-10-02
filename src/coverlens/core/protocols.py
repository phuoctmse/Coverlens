"""The extension points: InputAdapter, Verifier, OutputWriter (no others)."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from coverlens.core.models import Case, Requirement, Verdict
from coverlens.core.pack import PackConfig
from coverlens.core.report import Report


@runtime_checkable
class InputAdapter[T](Protocol):
    """Reads one input file into core models."""

    def read(self, path: Path, pack: PackConfig) -> list[T]: ...


@runtime_checkable
class Verifier(Protocol):
    """A Tier 2 or Tier 3 judge of one requirement against its candidate cases.

    Returns a verdict tagged with its own tier, or None to pass to the next tier.
    """

    def judge(
        self, requirement: Requirement, candidates: Sequence[Case]
    ) -> Verdict | None: ...


@runtime_checkable
class OutputWriter(Protocol):
    """Writes a finished report into a directory; returns the file written."""

    def write(self, report: Report, out_dir: Path) -> Path: ...
