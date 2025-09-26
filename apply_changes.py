from pathlib import Path

path = Path("src_common/pass_b_logical_splitter.py")
text = path.read_text()

text = text.replace("from typing import List, Optional, Dict, Any\n", "from typing import List, Optional, Dict, Any\n")

text = text.replace(
    "class SplitPart:\n    \"\"\"Metadata for a generated PDF part.\"\"\"\n\n    doc_id: str\n    part_id: str\n    section_id: str\n    page_start: int\n",
    "class SplitPart:\n    \"\"\"Metadata for a generated PDF part.\"\"\"\n\n    doc_id: str\n    part_id: str\n    section_id: Optional[str]\n    page_start: int\n"
)

text = text.replace(
    "section = self._section_for_page(part_start_page)\n                section_title = section.get('title') if section else f\"section-{part_number:02d}\"\n                section_id = section.get('section_id') if section else section_title\n\n                part_meta = SplitPart(\n                    doc_id=self.job_id,\n                    part_id=f\"{self.job_id}-part-{part_number:02d}\",\n                    section_id=section_id,\n",
    "                pages_label = f\"pages-{part_start_page}-{aligned_end}\"\n\n                part_meta = SplitPart(\n                    doc_id=self.job_id,\n                    part_id=f\"{self.job_id}-part-{part_number:02d}\",\n                    section_id=pages_label,\n"
)

text = text.replace(
    "section = self._section_for_page(part_start_page)\n                section_title = section.get('title') if section else f\"section-{part_number:02d}\"\n                section_id = section.get('section_id') if section else section_title\n\n                part_meta = SplitPart",
    "pages_label = f\"pages-{part_start_page}-{aligned_end}\"\n\n                part_meta = SplitPart"
)

text = text.replace(
    "                        \"section_id\": section_id,\n                        \"section_title\": section_title,\n",
    "                        \"section_id\": part_meta.section_id,\n                        \"section_title\": None,\n"
)

text = text.replace(
    "                self._log_job(\n                    \"Pass B boundary adjust: part=\"\n                    f\"{part_number}, requested_end={proposed_end}, aligned_end={aligned_end}, \"\n                    f\"mode={mode}, lightweight={lightweight}\"\n                )\n\n                part_started_at = time.perf_counter()\n                writer = PdfWriter()\n                for page_number in range(part_start_page - 1, aligned_end):\n                    writer.add_page(reader.pages[page_number])\n\n                part_filename = f\"{self.job_id}_part_{part_number:02d}.pdf\"\n                part_path = parts_dir / part_filename\n                with part_path.open(\"wb\") as handle:\n                    writer.write(handle)\n\n                checksum = _sha256(part_path)\n                part_relative = part_path.relative_to(job_dir).as_posix()\n                section = self._section_for_page(part_start_page)\n                section_title = section.get('title') if section else f\"section-{part_number:02d}\"\n                section_id = section.get('section_id') if section else section_title\n\n                part_meta = SplitPart(",
    "                self._log_job(\n                    \"Pass B boundary adjust: part=\"\n                    f\"{part_number}, requested_end={proposed_end}, aligned_end={aligned_end}, \"\n                    f\"mode={mode}, lightweight={lightweight}\"\n                )\n\n                part_started_at = time.perf_counter()\n                writer = PdfWriter()\n                for page_number in range(part_start_page - 1, aligned_end):\n                    writer.add_page(reader.pages[page_number])\n\n                part_filename = f\"{self.job_id}_part_{part_number:02d}.pdf\"\n                part_path = parts_dir / part_filename\n                with part_path.open(\"wb\") as handle:\n                    writer.write(handle)\n\n                checksum = _sha256(part_path)\n                part_relative = part_path.relative_to(job_dir).as_posix()\n                pages_label = f\"pages-{part_start_page}-{aligned_end}\"\n\n                part_meta = SplitPart("
)

text = text.replace(
    "                        \"section_id\": section_id,\n                        \"section_title\": section_title,\n",
    "                        \"section_id\": part_meta.section_id,\n                        \"section_title\": None,\n"
)

text = text.replace(
    "                self._log_job(\n                    \"Pass B part=\"\n                    f\"{part_number}, pages={part_meta.page_start}-{part_meta.page_end}, \"\n                    f\"section_id={section_id}, section_title={section_title}, \"\n                    f\"size_bytes={part_meta.size_bytes}, path={part_relative}\"\n                )\n\n                part_index += 1\n",
    "                self._log_job(\n                    \"Pass B part=\"\n                    f\"{part_number}, pages={part_meta.page_start}-{part_meta.page_end}, "
                    f\"size_bytes={part_meta.size_bytes}, path={part_relative}\"\n                )\n\n                part_index += 1\n"
)

text = text.replace(
    "                    {\n                        \"part_id\": None,\n                        \"page_start\": section[\"page_start\"],\n                        \"page_end\": section[\"page_end\"],\n                        \"section_id\": section.get(\"section_id\"),\n                        \"section_title\": section.get(\"title\"),\n                    }\n                )\n",
    "                    {\n                        \"part_id\": None,\n                        \"page_start\": section[\"page_start\"],\n                        \"page_end\": section[\"page_end\"],\n                        \"section_id\": f\"pages-{section['page_start']}-{section['page_end']}\",\n                        \"section_title\": None,\n                    }\n                )\n"
)

text = text.replace(
    "            self._log_job(\n                \"Pass B section catalog reused: sections=\"\n                f\"{len(self.section_catalog)}, mode={mode}\"\n            )\n\n        split_index_path = pass_dir / \"split_index.json\"\n",
    "            self._log_job(\n                \"Pass B section catalog reused: sections=\"\n                f\"{len(self.section_catalog)}, mode={mode}\"\n            )\n\n        split_index_path = pass_dir / \"split_index.json\"\n"
)

text = text.replace(
    "    def _section_for_page(self, page: int) -> Optional[Dict[str, Any]]:\n        \"\"\"Return catalog entry that contains the given page.\"\"\"\n        if not self.section_catalog:\n            return None\n        for section in self.section_catalog:\n            if section['page_start'] <= page <= section['page_end']:\n                return section\n        return self.section_catalog[-1]\n\n    def _section_title_for_page(self, page: int) -> str:\n        section = self._section_for_page(page)\n        if section:\n            return section.get('title', f\"section-{page:04d}\")\n        return f\"section-{page:04d}\"\n\n\n",
    "    def _section_for_page(self, page: int) -> Optional[Dict[str, Any]]:\n        \"\"\"Return catalog entry that contains the given page.\"\"\"\n        if not self.section_catalog:\n            return None\n        for section in self.section_catalog:\n            if section['page_start'] <= page <= section['page_end']:\n                return section\n        return None\n\n\n"
)

path.write_text(text)
