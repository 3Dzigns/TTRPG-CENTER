#!/usr/bin/env python3
"""
Queue Management Utility

Provides commands to clear, inspect, and manage the processing queue.
Useful for recovery after failures or when needing to reset the queue state.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src_common.processing_queue import ProcessingQueue


def clear_queue(env: str) -> None:
    """Clear all items from the processing queue"""
    project_root = Path(__file__).resolve().parents[1]
    queue_state_file = project_root / "artifacts" / "ingest" / env / ".." / "queue_state" / "processing_queue.json"
    
    queue = ProcessingQueue(state_file=queue_state_file)
    result = queue.clear_queue()
    
    print(f"Queue cleared: {result['cleared_count']} items removed")


def status_queue(env: str) -> None:
    """Show current queue status and items"""
    project_root = Path(__file__).resolve().parents[1]
    queue_state_file = project_root / "artifacts" / "ingest" / env / ".." / "queue_state" / "processing_queue.json"
    
    queue = ProcessingQueue(state_file=queue_state_file)
    status = queue.get_status()
    items = queue.peek_queue()
    
    print(f"Queue Status: {status['total_documents']} items (capacity: {status['capacity']})")
    print()
    
    if items:
        print("Queued Documents:")
        for i, item in enumerate(items, 1):
            path_name = Path(item['path']).name
            print(f"  {i}. {item['job_id']} - {path_name} (priority: {item['priority']})")
    else:
        print("Queue is empty")


def remove_failed(env: str, failed_paths: List[str]) -> None:
    """Remove specific failed documents from queue"""
    project_root = Path(__file__).resolve().parents[1]
    queue_state_file = project_root / "artifacts" / "ingest" / env / ".." / "queue_state" / "processing_queue.json"
    
    queue = ProcessingQueue(state_file=queue_state_file)
    result = queue.remove_failed_documents(failed_paths)
    
    print(f"Removed {result['removed_count']} failed documents")
    print(f"Queue now contains {result['remaining_count']} items")


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Manage processing queue")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"], help="Environment")
    
    subparsers = parser.add_subparsers(dest="command", help="Queue management commands")
    
    # Clear command
    subparsers.add_parser("clear", help="Clear all items from queue")
    
    # Status command
    subparsers.add_parser("status", help="Show queue status and items")
    
    # Remove failed command
    remove_parser = subparsers.add_parser("remove-failed", help="Remove failed documents from queue")
    remove_parser.add_argument("paths", nargs="+", help="Paths to remove from queue")
    
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == "clear":
            clear_queue(args.env)
        elif args.command == "status":
            status_queue(args.env)
        elif args.command == "remove-failed":
            remove_failed(args.env, args.paths)
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))