#!/usr/bin/env python3
"""CLI tool to resume failed pipeline runs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))

from pipeline_state import PipelineState
import argparse

def main():
    parser = argparse.ArgumentParser(description="Resume failed pipeline runs")
    parser.add_argument("document_path", help="Path to document to resume")
    parser.add_argument("--clear", action="store_true", help="Clear state and restart")
    parser.add_argument("--status", action="store_true", help="Show status only")

    args = parser.parse_args()

    doc_path = Path(args.document_path)
    if not doc_path.exists():
        print(f"❌ Document not found: {doc_path}")
        sys.exit(1)

    state_manager = PipelineState()
    doc_id = state_manager._document_id_from_path(doc_path)

    if args.clear:
        state_manager.clear_state(doc_id)
        print(f"✅ State cleared for {doc_path.name}")
        sys.exit(0)

    if args.status:
        state = state_manager.load_state(doc_id)
        print(f"\n📊 Pipeline Status for {doc_path.name}")
        print(f"Document ID: {doc_id}")
        print(f"Status: {state['status']}")
        print(f"Completed passes: {len(state['passes_completed'])}")

        for pass_rec in state["passes_completed"]:
            status_icon = "✅" if pass_rec["status"] == "success" else "❌"
            duration = pass_rec.get("duration_seconds", 0)
            print(f"  {status_icon} {pass_rec['pass']} - {pass_rec['status']} ({duration:.1f}s)")

        if state_manager.can_resume(doc_id):
            resume_point = state_manager.get_resume_point(doc_id)
            print(f"\n🔄 Can resume from: {resume_point}")

        sys.exit(0)

    # Resume logic
    if not state_manager.can_resume(doc_id):
        print(f"❌ Cannot resume - pipeline not in resumable state")
        print(f"Use --status to see current state")
        sys.exit(1)

    resume_point = state_manager.get_resume_point(doc_id)
    print(f"🔄 Resuming pipeline from {resume_point}")
    print(f"\nTo resume, run your ingestion script with checkpoint support.")
    print(f"The pipeline will automatically skip completed passes.")

if __name__ == "__main__":
    main()
