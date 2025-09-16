#!/usr/bin/env python3
"""Count backticks specifically."""

import re
from pathlib import Path

def count_backticks():
    """Count all backticks in the JavaScript."""

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

    total_backticks = 0
    for line_num, line in enumerate(lines, 1):
        html_line = line_num + 296
        backtick_count = line.count('`')
        if backtick_count > 0:
            total_backticks += backtick_count
            safe_line = line.strip().encode('ascii', 'replace').decode('ascii')
            print(f"HTML:{html_line:4d} JS:{line_num:3d} - {backtick_count} backticks: {safe_line}")

    print(f"\nTotal backticks: {total_backticks}")
    print(f"Should be even: {'YES' if total_backticks % 2 == 0 else 'NO'}")

if __name__ == "__main__":
    count_backticks()