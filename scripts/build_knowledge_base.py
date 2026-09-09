#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "knowledge_base"
PDF_DIR = KB_DIR / "pdfs"
INDEX_FILE = KB_DIR / "index.json"

BOOKS = (
    {
        "id": "think-python-2e",
        "title": "Think Python 2e",
        "url": "https://greenteapress.com/thinkpython2/thinkpython2.pdf",
        "license": "CC BY-NC 3.0",
    },
    {
        "id": "dive-into-deep-learning",
        "title": "Dive into Deep Learning",
        "url": "https://d2l.ai/d2l-en.pdf",
        "license": "See the book's own license and attribution page",
    },
    {
        "id": "stanford-cs229-lecture-1",
        "title": "Stanford CS229 Lecture 1",
        "url": "https://cs229.stanford.edu/notes2021spring/notes2021spring/lecture1.pdf",
        "license": "For personal educational use; retain the original source link",
    },
)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def download(book: dict[str, str], path: Path) -> None:
    if path.exists() and path.stat().st_size > 50_000:
        return
    request = Request(book["url"], headers={"User-Agent": "qq-ai-knowledge-bot-local-kb/1.0"})
    with urlopen(request, timeout=45) as response:
        path.write_bytes(response.read())


def extract(book: dict[str, str], pdf_path: Path) -> list[dict[str, object]]:
    reader = PdfReader(str(pdf_path))
    chunks = []
    pages_per_chunk = 6
    for start in range(0, len(reader.pages), pages_per_chunk):
        page_text = "\n".join(reader.pages[index].extract_text() or "" for index in range(start, min(start + pages_per_chunk, len(reader.pages))))
        text = clean(page_text)
        if len(text) < 500:
            continue
        chunks.append(
            {
                "book_id": book["id"],
                "book_title": book["title"],
                "license": book["license"],
                "source_url": book["url"],
                "page_start": start + 1,
                "page_end": min(start + pages_per_chunk, len(reader.pages)),
                "text": text[:14000],
            }
        )
    return chunks


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    chunks = []
    for book in BOOKS:
        pdf_path = PDF_DIR / f"{book['id']}.pdf"
        print(f"下载/读取：{book['title']}")
        try:
            download(book, pdf_path)
            book_chunks = extract(book, pdf_path)
        except Exception as exc:
            print(f"  跳过：{type(exc).__name__}: {exc}")
            continue
        print(f"  页数片段：{len(book_chunks)}")
        chunks.extend(book_chunks)
    INDEX_FILE.write_text(json.dumps({"version": 1, "chunks": chunks}, ensure_ascii=False), encoding="utf-8")
    print(f"知识库完成：{INDEX_FILE}，共 {len(chunks)} 个片段")


if __name__ == "__main__":
    main()
