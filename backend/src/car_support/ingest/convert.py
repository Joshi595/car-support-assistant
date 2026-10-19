"""Convert any supported document to Markdown, so one heading-aware chunker handles every format."""

import io
import re
from pathlib import Path

from bs4 import BeautifulSoup
from markitdown import MarkItDown, StreamInfo

_markitdown = MarkItDown()
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
# A numbered heading on its own line in PDF text, e.g. "3. Charging" or "3.1 AC charging".
_PDF_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(?=\S*[^\W\d])(\S[^.!?:;]{0,70})$")


def to_markdown(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8")
    elif suffix == ".html":
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        content = soup.main or soup.body or soup  # skip site navigation and footers when the page marks them
        stream = io.BytesIO(str(content).encode("utf-8"))
        text = _markitdown.convert_stream(
            stream, stream_info=StreamInfo(extension=".html", charset="utf-8")
        ).text_content
    elif suffix in {".pdf", ".docx"}:
        text = _markitdown.convert(str(path)).text_content
        if suffix == ".pdf":
            text = pdf_text_to_markdown(text)
    else:
        raise ValueError(f"unsupported document type: {path}")
    return _LINK.sub(r"\1", text).strip()  # keep link text, drop URLs (noise for search and answers)


def pdf_text_to_markdown(text: str) -> str:
    """Recover structure from extracted PDF text: the first line becomes the title, numbered heading
    lines become headings, and lines wrapped by the page layout are joined back into paragraphs."""
    # ponytail: heading detection relies on numbered headings ("2.1 Title"), the convention of manuals.
    # Unnumbered PDFs still work: they become one titled section, split by size. Tables come out column by
    # column (a pdfminer limit); their facts stay in the right section but lose row alignment.
    text = text.replace("\f", "\n\n")  # page breaks
    paragraphs = [
        " ".join(line.strip() for line in p.splitlines()) for p in re.split(r"\n\s*\n", text.strip())
    ]
    out = []
    for i, para in enumerate(p for p in paragraphs if p):
        if i == 0:
            out.append(f"# {para}")
        elif m := _PDF_HEADING.match(para):
            out.append(f"{'#' * (m[1].count('.') + 2)} {para}")
        else:
            out.append(para)
    return "\n\n".join(out)
