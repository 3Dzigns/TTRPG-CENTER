from pathlib import Path

path = Path("src_common/pass_b_logical_splitter.py")
text = path.read_text()
old = "                self._log_job(\n                    \"Pass B part=\"\n                    f\"{part_number}, pages={part_meta.page_start}-{part_meta.page_end}, \"\n                    f\"section_id={section_id}, section_title={section_title}, \"\n                    f\"size_bytes={part_meta.size_bytes}, path={part_relative}\"\n                )\n"
new = "                self._log_job(\n                    \"Pass B part=\"\n                    f\"{part_number}, pages={part_meta.page_start}-{part_meta.page_end}, \"\n                    f\"size_bytes={part_meta.size_bytes}, path={part_relative}\"\n                )\n"
if old not in text:
    raise SystemExit("part log block not found")
text = text.replace(old, new)
path.write_text(text)
