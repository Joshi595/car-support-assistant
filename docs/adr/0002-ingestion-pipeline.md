# ADR 0002: Ingestion: convert to Markdown, chunk by heading, index incrementally

**Status:** accepted (Phase 2)

## Context

The knowledge base now holds Markdown, HTML and PDF files in three markets and two languages, and will grow. The prototype parsed one custom text format, re-embedded everything when sections were added or removed, and missed edits inside a section.

## Decision

1. **Convert every format to Markdown** with `markitdown` (MIT). For HTML, only `<main>` is converted when present, which drops navigation and footers. Link URLs are removed and their text kept. PDF text loses its heading markup, so numbered heading lines ("3.1 AC charging") are promoted back to Markdown headings, and lines wrapped by the page layout are rejoined.
2. **Chunk by heading**, one chunk per section, each prefixed with its heading path (`Title › Section › Subsection`). This keeps the prototype's measured win: a fact such as "8 years" stays attached to *which* warranty it belongs to. Sections over 1,200 characters are split further on paragraph and sentence boundaries with 150 characters of overlap, and every piece keeps the prefix.
3. **Index incrementally with content hashes.** A document is re-processed only when the hash of its text, metadata, chunking settings and embedding model changes. Inside a changed document, chunks are matched by a hash of their text, so only new or edited chunks are embedded. Documents deleted from `data/` are removed with their chunks. Every change creates a new `kb_version`.
4. **Metadata comes from the path plus `data/catalog.toml`**, which holds only what the path cannot say (versions, models, source URLs, licences).

## Consequences

- A second ingest of an unchanged corpus takes about 3 seconds and embeds nothing. Editing one section re-embeds exactly one chunk (covered by an integration test).
- A full ingest of the current corpus (55 documents, 408 chunks) takes about 2.5 minutes with `qwen3-embedding:0.6b` on a laptop GPU.
- Tables in PDFs are extracted column by column, a pdfminer limitation. Their facts stay in the right section but lose row alignment. Tables in HTML and Markdown are preserved.
- Heading detection in PDFs relies on numbered headings, the usual convention in manuals. An unnumbered PDF becomes one titled section split by size, which still works but is less precise.
