from pathlib import Path

path = Path("src_common/pass_b_logical_splitter.py")
text = path.read_text()
old = "                split_plan.append(\n                    {\n                        \"part_id\": part_meta.part_id,\n                        \"page_start\": part_meta.page_start,\n                        \"page_end\": part_meta.page_end,\n                        \"section_id\": section_id,\n                        \"section_title\": section_title,\n                    }\n                )\n"
new = "                split_plan.append(\n                    {\n                        \"part_id\": part_meta.part_id,\n                        \"page_start\": part_meta.page_start,\n                        \"page_end\": part_meta.page_end,\n                        \"section_id\": part_meta.section_id,\n                        \"section_title\": None,\n                    }\n                )\n"
if old not in text:
    raise SystemExit("split_plan block not found")
text = text.replace(old, new)
path.write_text(text)
