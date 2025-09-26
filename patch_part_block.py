from pathlib import Path

path = Path("src_common/pass_b_logical_splitter.py")
text = path.read_text()
old = "                part_filename = f\"{self.job_id}_part_{part_number:02d}.pdf\"\n                part_path = parts_dir / part_filename\n                with part_path.open(\"wb\") as handle:\n                    writer.write(handle)\n\n                checksum = _sha256(part_path)\n                part_relative = part_path.relative_to(job_dir).as_posix()\n                section = self._section_for_page(part_start_page)\n                section_title = section.get('title') if section else f\"section-{part_number:02d}\"\n                section_id = section.get('section_id') if section else section_title\n\n                part_meta = SplitPart(\n                    doc_id=self.job_id,\n                    part_id=f\"{self.job_id}-part-{part_number:02d}\",\n                    section_id=section_id,\n"
new = "                part_filename = f\"{self.job_id}_part_{part_number:02d}.pdf\"\n                part_path = parts_dir / part_filename\n                with part_path.open(\"wb\") as handle:\n                    writer.write(handle)\n\n                checksum = _sha256(part_path)\n                part_relative = part_path.relative_to(job_dir).as_posix()\n                pages_label = f\"pages-{part_start_page}-{aligned_end}\"\n\n                part_meta = SplitPart(\n                    doc_id=self.job_id,\n                    part_id=f\"{self.job_id}-part-{part_number:02d}\",\n                    section_id=pages_label,\n"
if old not in text:
    raise SystemExit("expected block not found")
text = text.replace(old, new)
path.write_text(text)
