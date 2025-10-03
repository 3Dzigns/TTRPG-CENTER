#!/usr/bin/env python
"""Archive Completed Bugs and Features"""

import os
import json
import shutil
import pathlib
from datetime import datetime

def archive_completed_items():
    """Archive completed bugs and features to archives/ directory"""

    stamp = datetime.now().strftime("%Y%m%d")
    dest_bugs = pathlib.Path(f"archives/bugs/{stamp}")
    dest_features = pathlib.Path(f"archives/features/{stamp}")

    dest_bugs.mkdir(parents=True, exist_ok=True)
    dest_features.mkdir(parents=True, exist_ok=True)

    archived_count = 0
    skipped_count = 0

    # Archive completed features
    features_dir = pathlib.Path("features")
    if features_dir.exists():
        for f in features_dir.glob("FR-*.json"):
            try:
                data = json.loads(f.read_text())
                status = data.get('status', '').lower()

                if status in ['done', 'closed', 'resolved', 'rejected', 'completed']:
                    # Create destination directory
                    item_id = f.stem
                    dest_dir = dest_features / item_id
                    dest_dir.mkdir(exist_ok=True)

                    # Copy file
                    shutil.copy2(f, dest_dir / f.name)

                    # Create archive metadata
                    archive_meta = {
                        "archived_at": datetime.now().isoformat(),
                        "source": str(f),
                        "status": status,
                        "title": data.get('title', 'Unknown'),
                        "reason": f"Status: {status}"
                    }
                    (dest_dir / "archive.json").write_text(json.dumps(archive_meta, indent=2))

                    # Create stub pointer in original location
                    stub = {
                        "moved_to": str(dest_dir),
                        "archived_at": datetime.now().isoformat(),
                        "original_status": status
                    }
                    f.write_text(json.dumps(stub, indent=2))

                    print(f"Archived: {f} -> {dest_dir}")
                    archived_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                print(f"Error processing {f}: {e}")

    # Archive completed bug resolution documents
    docs_bugs = pathlib.Path("docs/bugs")
    if docs_bugs.exists():
        for f in docs_bugs.glob("BUG-*.md"):
            try:
                content = f.read_text().lower()
                # Check if resolved/completed
                if any(term in content for term in ['status: resolved', 'status: completed', 'status: closed', 'resolution:', 'fixed']):
                    item_id = f.stem
                    dest_dir = dest_bugs / item_id
                    dest_dir.mkdir(exist_ok=True)

                    # Copy file
                    shutil.copy2(f, dest_dir / f.name)

                    # Create archive metadata
                    archive_meta = {
                        "archived_at": datetime.now().isoformat(),
                        "source": str(f),
                        "type": "bug_resolution",
                        "reason": "Completed/resolved bug documentation"
                    }
                    (dest_dir / "archive.json").write_text(json.dumps(archive_meta, indent=2))

                    # Create stub pointer
                    stub_path = f.with_suffix('.archived.md')
                    stub_path.write_text(f"# Archived\n\nThis document has been archived to: `{dest_dir}`\n")

                    print(f"Archived: {f} -> {dest_dir}")
                    archived_count += 1
            except Exception as e:
                print(f"Error processing {f}: {e}")

    # Also check root-level bug resolution files
    root = pathlib.Path(".")
    for f in root.glob("BUG-*-RESOLUTION.md"):
        try:
            item_id = f.stem
            dest_dir = dest_bugs / item_id
            dest_dir.mkdir(exist_ok=True)

            shutil.copy2(f, dest_dir / f.name)

            archive_meta = {
                "archived_at": datetime.now().isoformat(),
                "source": str(f),
                "type": "bug_resolution",
                "reason": "Root-level bug resolution document"
            }
            (dest_dir / "archive.json").write_text(json.dumps(archive_meta, indent=2))

            # Remove original after archiving
            f.unlink()

            print(f"Archived and removed: {f} -> {dest_dir}")
            archived_count += 1
        except Exception as e:
            print(f"Error processing {f}: {e}")

    # Summary report
    summary = {
        "archived_date": stamp,
        "total_archived": archived_count,
        "total_skipped": skipped_count,
        "bug_archives": str(dest_bugs),
        "feature_archives": str(dest_features)
    }

    pathlib.Path("docs/cleanup/archive-summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n=== Archive Summary ===")
    print(f"Date: {stamp}")
    print(f"Items archived: {archived_count}")
    print(f"Items skipped: {skipped_count}")
    print(f"Bug archives: {dest_bugs}")
    print(f"Feature archives: {dest_features}")

    return summary

if __name__ == '__main__':
    archive_completed_items()
