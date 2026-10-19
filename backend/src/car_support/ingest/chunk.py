"""Split Markdown into retrieval chunks: one per section, prefixed with its heading path.

Each chunk starts with "Title › Section › Subsection" so that both keyword and vector search see what
a passage is about ("8 years" belongs to the *battery* warranty). Sections longer than `max_chars` are
split further on paragraph and sentence boundaries; every piece keeps the heading prefix.
"""

import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*$")
SEPARATOR = " › "


@dataclass(frozen=True)
class Chunk:
    heading_path: tuple[str, ...]  # starts with the document title
    body: str

    @property
    def text(self) -> str:
        return f"{SEPARATOR.join(self.heading_path)}\n{self.body}"


def title_of(markdown: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", markdown, re.M)
    return m[1].strip() if m else fallback


def chunk_markdown(markdown: str, title: str, max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars, chunk_overlap=overlap, separators=["\n\n", "\n", ". ", " ", ""]
    )
    sections: list[tuple[tuple[str, ...], list[str]]] = [((title,), [])]
    stack: list[tuple[int, str]] = []  # (level, heading) of the open headings below the title
    for line in markdown.splitlines():
        if m := _HEADING.match(line):
            level, heading = len(m[1]), m[2]
            if level == 1:  # the document title itself
                continue
            stack = [(lvl, h) for lvl, h in stack if lvl < level] + [(level, heading)]
            sections.append(((title, *(h for _, h in stack)), []))
        else:
            sections[-1][1].append(line)

    chunks: list[Chunk] = []
    for path, lines in sections:
        body = "\n".join(lines).strip()
        if not body:  # e.g. a "## Keys" heading directly followed by "### ..." questions
            continue
        pieces = splitter.split_text(body) if len(body) > max_chars else [body]
        chunks.extend(Chunk(path, piece) for piece in pieces)
    return chunks
