#!/usr/bin/env python3
"""Debug end of JavaScript extraction."""

import re
from pathlib import Path

def debug_end_of_js():
    """Debug the end of JavaScript extraction."""

    # Read the HTML file
    html_file = Path(__file__).parent.parent / "templates" / "admin_dashboard.html"
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Extract JavaScript content
    pattern = r'{% block extra_scripts %}(.*?){% endblock %}'
    match = re.search(pattern, html_content, re.DOTALL)
    scripts_block = match.group(1)

    script_pattern = r'<script[^>]*>(.*?)</script>'
    script_matches = re.findall(script_pattern, scripts_block, re.DOTALL)
    js_content = '\n'.join(script_matches)

    lines = js_content.split('\n')

    print(f"Total JS lines: {len(lines)}")
    print("\nLast 10 lines of JavaScript:")
    for i, line in enumerate(lines[-10:], len(lines)-9):
        html_line = i + 296
        print(f"HTML:{html_line:4d} JS:{i:3d}: {repr(line)}")

    print(f"\nLast 50 characters of JS content:")
    print(repr(js_content[-50:]))

if __name__ == "__main__":
    debug_end_of_js()