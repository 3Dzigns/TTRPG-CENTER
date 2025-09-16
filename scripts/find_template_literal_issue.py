#!/usr/bin/env python3
"""
Find Template Literal Issue

Specifically hunt for the template literal imbalance.
"""

import re
from pathlib import Path


def find_template_literal_issue():
    """Find the template literal balance issue."""

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

    print("Template Literal Analysis:")
    print("=" * 30)

    template_literals = []
    in_string = False
    string_char = None
    in_template = False

    for line_num, line in enumerate(lines, 1):
        html_line = line_num + 296

        i = 0
        while i < len(line):
            char = line[i]

            # Handle escape sequences
            if in_string and char == '\\':
                i += 2
                continue

            # Skip if already in a string
            if in_string:
                if char == string_char:
                    in_string = False
                    string_char = None
                i += 1
                continue

            # Handle strings
            if char in ['"', "'"] and not in_template:
                in_string = True
                string_char = char
            elif char == '`':
                if not in_template:
                    # Starting template literal
                    in_template = True
                    template_literals.append({
                        'start_html': html_line,
                        'start_js': line_num,
                        'start_col': i,
                        'context': line[max(0, i-10):i+30]
                    })
                    context = line[max(0, i-10):i+30].replace('\u2713', 'checkmark')
                    print(f"Template literal START: HTML:{html_line:4d} JS:{line_num:3d} col:{i:2d} - {context}")
                else:
                    # Ending template literal
                    in_template = False
                    if template_literals:
                        start_info = template_literals[-1]
                        start_info['end_html'] = html_line
                        start_info['end_js'] = line_num
                        start_info['end_col'] = i
                        context = line[max(0, i-10):i+30].replace('\u2713', 'checkmark')
                        print(f"Template literal END:   HTML:{html_line:4d} JS:{line_num:3d} col:{i:2d} - {context}")
                    else:
                        print(f"ERROR: Template literal END without START: HTML:{html_line:4d} JS:{line_num:3d} col:{i:2d}")

            i += 1

    print("\nSUMMARY:")
    print(f"Total template literals found: {len(template_literals)}")

    if in_template:
        print("ERROR: Unclosed template literal at end of file!")
        if template_literals:
            last = template_literals[-1]
            print(f"Last unclosed started at HTML:{last['start_html']} JS:{last['start_js']} col:{last['start_col']}")

    incomplete = [tl for tl in template_literals if 'end_html' not in tl]
    if incomplete:
        print(f"\nUNCLOSED TEMPLATE LITERALS: {len(incomplete)}")
        for tl in incomplete:
            print(f"  HTML:{tl['start_html']:4d} JS:{tl['start_js']:3d} col:{tl['start_col']:2d} - {tl['context']}")


if __name__ == "__main__":
    find_template_literal_issue()