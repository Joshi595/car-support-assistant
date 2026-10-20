"""Build the production learning guide: join chapters/*.html with style.css and print to PDF.

    python docs/guide/build.py [--copy-to PATH]

Needs Microsoft Edge or Chrome (headless printing); set BROWSER to its path if it is not found.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATES = [
    os.environ.get("BROWSER", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/microsoft-edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def browser() -> str:
    for path in CANDIDATES:
        if path and Path(path).is_file():
            return path
    sys.exit("No Edge/Chrome found; set BROWSER to its executable.")


def html() -> str:
    chapters = "\n".join(p.read_text(encoding="utf-8") for p in sorted((HERE / "chapters").glob("*.html")))
    css = (HERE / "style.css").read_text(encoding="utf-8")
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        "<title>Car Support RAG: From Prototype to Production</title>"
        f"<style>{css}</style></head><body>\n{chapters}\n</body></html>\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "RAG_Production_Guide.pdf")
    parser.add_argument("--copy-to", type=Path, help="also copy the PDF here")
    args = parser.parse_args()

    source = HERE / "build" / "guide.html"
    source.parent.mkdir(exist_ok=True)
    source.write_text(html(), encoding="utf-8")
    with tempfile.TemporaryDirectory() as profile:  # a fresh profile: never touches the user's browser
        subprocess.run(  # noqa: S603 - a local browser binary and paths of this repo; no untrusted input
            [
                browser(),
                "--headless",
                "--disable-gpu",
                f"--user-data-dir={profile}",
                "--no-pdf-header-footer",
                f"--print-to-pdf={args.out}",
                source.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
    print(f"wrote {args.out} ({args.out.stat().st_size // 1024} KB)")
    if args.copy_to:
        shutil.copyfile(args.out, args.copy_to)
        print(f"copied to {args.copy_to}")


if __name__ == "__main__":
    main()
