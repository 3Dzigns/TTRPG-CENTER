from pathlib import Path

path = Path("src_common/pass_b_logical_splitter.py")
text = path.read_text()
old = "                logger.info(\n                    \"pass_b_part_emitted\",\n                    extra={\n                        \"job_id\": self.job_id,\n                        \"part_index\": part_number,\n                        \"page_start\": part_meta.page_start,\n                        \"page_end\": part_meta.page_end,\n                        \"size_bytes\": part_meta.size_bytes,\n                        \"duration_ms\": part_duration_ms,\n                        \"section_id\": section_id,\n                        \"section_title\": section_title,\n                    },\n                )\n                self._log_job(\n                    \"Pass B part=\"\n                    f\"{part_number}, pages={part_meta.page_start}-{part_meta.page_end}, \"\n                    f\"size_bytes={part_meta.size_bytes}, path={part_relative}\"\n                )\n"
new = "                logger.info(\n                    \"pass_b_part_emitted\",\n                    extra={\n                        \"job_id\": self.job_id,\n                        \"part_index\": part_number,\n                        \"page_start\": part_meta.page_start,\n                        \"page_end\": part_meta.page_end,\n                        \"size_bytes\": part_meta.size_bytes,\n                        \"duration_ms\": part_duration_ms,\n                        \"pages_label\": part_meta.section_id,\n                    },\n                )\n                self._log_job(\n                    \"Pass B part=\"\n                    f\"{part_number}, pages={part_meta.page_start}-{part_meta.page_end}, \"\n                    f\"size_bytes={part_meta.size_bytes}, path={part_relative}\"\n                )\n"
if old not in text:
    raise SystemExit("part emitted extra block not found")
text = text.replace(old, new)
path.write_text(text)
