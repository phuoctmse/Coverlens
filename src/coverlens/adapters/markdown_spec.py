"""Reads a markdown spec of stories and their acceptance criteria.

Expected shape:

    ## <story id> <story title>
    - **<story id>.<suffix>** <requirement text>

Every requirement must sit under its own story heading.
"""

import re
from pathlib import Path

from coverlens.core.models import Requirement
from coverlens.core.pack import PackConfig

STORY_RE = re.compile(r"^##\s+(?P<id>\S+)\s+\S")
REQUIREMENT_RE = re.compile(r"^\s*[-*]\s+\*\*(?P<id>[^*\s]+)\*\*\s+(?P<text>.+?)\s*$")


class SpecError(ValueError):
    """The spec is missing, unreadable or malformed."""


def parse_spec(text: str, source: str = "<spec>") -> list[Requirement]:
    story: str | None = None
    requirements: list[Requirement] = []
    seen: set[str] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        if heading := STORY_RE.match(line):
            story = heading["id"]
            continue
        item = REQUIREMENT_RE.match(line)
        if item is None:
            continue
        req_id = item["id"]
        where = f"{source}:{line_no}"
        if story is None:
            raise SpecError(f"{where}: requirement {req_id} is not under a story")
        if not req_id.startswith(f"{story}."):
            raise SpecError(f"{where}: requirement {req_id} is not in story {story}")
        if req_id in seen:
            raise SpecError(f"{where}: duplicate requirement {req_id}")
        seen.add(req_id)
        requirements.append(Requirement(id=req_id, parent_id=story, text=item["text"]))
    if not requirements:
        raise SpecError(f"{source}: no requirements found")
    return requirements


class MarkdownSpecAdapter:
    """InputAdapter for the markdown spec. The format needs no pack settings."""

    def read(self, path: Path, pack: PackConfig) -> list[Requirement]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SpecError(f"{path}: cannot read spec: {exc}") from exc
        return parse_spec(text, source=str(path))
