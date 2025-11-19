
# LangFlow: 3‑Node "Split PDF by Page Range" Flow

This guide shows how to build a minimal LangFlow pipeline with **three nodes**:
1) **Read File** – loads your source PDF
2) **Python Code** – splits by page range **X to Y**
3) **Write File** – saves the new PDF chunk

> Works great for quick page‑range extraction (e.g., chapters or sections) and keeps the file in‑memory between nodes.

---

## Prereqs
- LangFlow 1.3.x+
- The container/venv needs `pypdf` (recommended) or `PyPDF2` installed.
  - In Docker, you can set an env var or exec into the container and run:
    ```bash
    pip install pypdf
    ```

---

## Build the Flow

**A. Read File node**
- Add a **Read File** (or similar "File -> bytes" loader) node.
- Configure:
  - **Path**: point to your PDF on disk
  - **Output**: ensure it provides **bytes** and **file name** (many file nodes output both).

**B. Python Code node (the splitter)**
- Add a **Python Code** node.
- Inputs (create these fields if needed):
  - `file_bytes` (bytes) – connect from Read File’s bytes output
  - `start_page` (int) – set a default (e.g., 1)
  - `end_page` (int) – set a default (e.g., 10)
  - `original_filename` (str) – connect from Read File file name (optional)
- Open the code editor and paste the **`run`** function from `pdf_splitter_code_node.py`.
  - Make sure the node is set to call `run(...)` and return its dict output.

**C. Write File node**
- Add a **Write File** (or similar sink) node.
- Wire inputs:
  - **bytes** → from Python node’s `bytes`
  - **file name** → from Python node’s `file_name`
  - **MIME** → `application/pdf` (or from Python node’s `mime_type`)
- Set **Output Directory** to where you want the file saved.

**D. Run**
- Set `start_page` and `end_page` on the Python node.
- Execute. You should get an output like: `yourfile_pages_5-22.pdf` in the chosen folder.

---

## Notes & Tips
- Pages are **1‑based** in the UI; internally converted to 0‑based for the PDF library.
- The splitter clamps ranges to the document bounds and raises a clear error if start > end.
- You can duplicate the Python node with different ranges to create multiple outputs in one flow.
- If you plan to reuse this frequently, consider packaging it as a **Custom Component** and mounting it into LangFlow’s `components` folder.

---

## Troubleshooting
- **Module not found: pypdf** → `pip install pypdf` (fallback to `PyPDF2` if needed)
- **Permission issues writing file** → ensure your output directory is a writable volume inside Docker.
- **Wrong pages extracted** → confirm your `start_page`/`end_page` are 1‑based and within the doc’s page count.
