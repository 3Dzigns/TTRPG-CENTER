
"""
pdf_splitter_code_node.py
---------------------------------
Paste the `run` function body into a LangFlow "Python Code" node.

Inputs expected from LangFlow:
  - file_bytes: bytes         # The entire PDF as bytes (from a Read File node)
  - start_page: int           # 1-based inclusive start page
  - end_page: int             # 1-based inclusive end page
  - original_filename: str    # (Optional) original file name for nicer output naming

Outputs back to LangFlow (as a dict):
  - bytes: split_bytes        # The split PDF as bytes
  - file_name: split_name     # Suggested output file name
  - mime_type: "application/pdf"

Notes:
  - Requires the 'pypdf' library (modern fork of PyPDF2). If not present, falls back to PyPDF2.
  - Pages are validated and clamped to the document bounds.
"""

import io

# Try pypdf first; fall back to PyPDF2 for environments that still use it.
try:
    from pypdf import PdfReader, PdfWriter
except Exception:  # pragma: no cover
    from PyPDF2 import PdfReader, PdfWriter  # type: ignore

def _sanitize_range(start_page: int, end_page: int, total_pages: int) -> tuple[int, int]:
    if start_page is None or end_page is None:
        raise ValueError("Both start_page and end_page must be provided.")
    if start_page < 1:
        start_page = 1
    if end_page > total_pages:
        end_page = total_pages
    if start_page > end_page:
        raise ValueError(f"start_page ({start_page}) cannot be greater than end_page ({end_page}).")
    return start_page, end_page

def run(file_bytes: bytes, start_page: int, end_page: int, original_filename: str | None = None) -> dict:
    if not isinstance(file_bytes, (bytes, bytearray)):
        raise TypeError("file_bytes must be raw bytes of a PDF.")

    pdf_stream = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_stream)

    total_pages = len(reader.pages)
    start_page, end_page = _sanitize_range(start_page, end_page, total_pages)

    writer = PdfWriter()
    # Convert to 0-based indices for the library
    for p in range(start_page - 1, end_page):
        writer.add_page(reader.pages[p])

    out_stream = io.BytesIO()
    writer.write(out_stream)
    writer.close()
    split_bytes = out_stream.getvalue()

    # Build a nice output name
    base = (original_filename or "document").rsplit(".", 1)[0]
    split_name = f"{base}_pages_{start_page}-{end_page}.pdf"

    return {
        "bytes": split_bytes,
        "file_name": split_name,
        "mime_type": "application/pdf",
        "page_count": end_page - start_page + 1,
        "start_page": start_page,
        "end_page": end_page,
        "total_pages": total_pages,
    }
