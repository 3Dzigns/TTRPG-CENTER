# n8n-nodes-pdf-slice (Local)

Slicing pages Xâ€“Y from an input PDF using [pdf-lib]; no external APIs.
Place the node in n8n and wire it like any transform node with a binary input.

**Inputs:**
- Binary Property: name that contains `application/pdf` (default: `data`)
- Start Page: integer (1-based)
- End Page: integer (1-based)

**Outputs:**
- Adds a binary property (default: `sliced`) holding the new PDF
- Adds `json.sliceInfo` metadata
