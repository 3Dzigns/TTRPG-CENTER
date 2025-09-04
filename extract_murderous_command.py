#!/usr/bin/env python3
"""Extract Murderous Command chunks from the parsed PDF data."""

import json

def extract_murderous_command_chunks():
    """Extract and display chunks containing 'Murderous Command'."""
    
    with open('artifacts/test/test_job_pass_a_chunks.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    matches = [chunk for chunk in data['chunks'] if 'murderous command' in chunk['content'].lower()]
    
    print(f"Found {len(matches)} chunks containing 'Murderous Command':\n")
    
    for i, chunk in enumerate(matches):
        print(f"{'='*60}")
        print(f"CHUNK {i+1} - ID: {chunk['id']}")
        print(f"{'='*60}")
        print(f"Page: {chunk['metadata']['page']}")
        print(f"Section: {chunk['metadata']['section']}")
        print(f"Chunk Type: {chunk['metadata']['chunk_type']}")
        print(f"Element ID: {chunk['metadata']['element_id']}")
        print(f"\nCONTENT:")
        print("-" * 40)
        print(chunk['content'])
        print("\n")

if __name__ == "__main__":
    extract_murderous_command_chunks()