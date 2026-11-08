"""Load the quantforge Academy curriculum from Markdown files with YAML front matter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

__all__ = ["Chapter", "Question", "Source", "load_curriculum", "LEVELS", "PASS_MARK"]

CONTENT_DIR = Path(__file__).parent / "content"
PASS_MARK = 0.8   # share of correct answers needed for a certificate

LEVELS = {
    1: "Market Foundations",
    2: "Risk & Statistics",
    3: "Portfolio Construction",
    4: "Derivatives",
    5: "Advanced Risk & Econometrics",
    6: "Capstone",
    7: "Quant Programming",
}

_WIDGET = re.compile(r"\{\{widget:([a-z0-9_]+)\}\}")


@dataclass(frozen=True)
class Source:
    title: str
    by: str
    url: str = ""


@dataclass(frozen=True)
class Question:
    q: str
    options: tuple[str, ...]
    answer: int
    why: str


@dataclass(frozen=True)
class Chapter:
    id: int
    level: int
    level_name: str
    title: str
    minutes: int
    objectives: tuple[str, ...]
    widgets: tuple[str, ...]
    sources: tuple[Source, ...]
    quiz: tuple[Question, ...]
    body: str = field(repr=False)

    @property
    def slug(self) -> str:
        return f"ch{self.id:02d}"

    def blocks(self) -> list[tuple[str, str]]:
        """Split the body into ``("md", text)`` and ``("widget", name)`` blocks, in order."""
        out, pos = [], 0
        for m in _WIDGET.finditer(self.body):
            if m.start() > pos:
                out.append(("md", self.body[pos:m.start()]))
            out.append(("widget", m.group(1)))
            pos = m.end()
        if pos < len(self.body):
            out.append(("md", self.body[pos:]))
        return out


def _parse(path: Path) -> Chapter:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path.name}: missing front matter")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front)
    quiz = tuple(Question(q["q"], tuple(q["options"]), int(q["answer"]), q["why"])
                 for q in meta.get("quiz", []))
    for i, q in enumerate(quiz):
        if not 0 <= q.answer < len(q.options):
            raise ValueError(f"{path.name}: question {i + 1} has an invalid answer index")
    return Chapter(
        id=int(meta["id"]), level=int(meta["level"]), level_name=meta["level_name"],
        title=meta["title"], minutes=int(meta.get("minutes", 20)),
        objectives=tuple(meta.get("objectives", [])), widgets=tuple(meta.get("widgets", [])),
        sources=tuple(Source(s["title"], s["by"], s.get("url", "") or "")
                      for s in meta.get("sources", [])),
        quiz=quiz, body=body.strip(),
    )


@lru_cache(maxsize=1)
def load_curriculum() -> tuple[Chapter, ...]:
    chapters = tuple(sorted((_parse(p) for p in CONTENT_DIR.glob("*.md")), key=lambda c: c.id))
    ids = [c.id for c in chapters]
    if ids != list(range(1, len(ids) + 1)):
        raise ValueError(f"chapter ids must be 1..n without gaps, got {ids}")
    return chapters
