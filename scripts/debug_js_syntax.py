#!/usr/bin/env python3
"""
Debug JavaScript Syntax - Enhanced Analysis

Enhanced script to find the exact location of missing braces and parentheses.
"""

import re
from pathlib import Path


def debug_js_syntax():
    """Debug JavaScript syntax with detailed tracking."""

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

    # Track braces, parentheses, and brackets with line numbers
    brace_stack = []
    paren_stack = []
    bracket_stack = []
    in_string = False
    in_comment = False
    string_char = None

    print("Detailed syntax analysis:")
    print("=" * 50)

    for line_num, line in enumerate(lines, 1):
        html_line = line_num + 296  # Approximate HTML line offset

        i = 0
        while i < len(line):
            char = line[i]

            # Handle escape sequences
            if in_string and char == '\\':
                i += 2  # Skip escaped character
                continue

            # Handle comments
            if not in_string:
                if i < len(line) - 1 and line[i:i+2] == '//':
                    break  # Rest of line is comment
                elif i < len(line) - 1 and line[i:i+2] == '/*':
                    in_comment = True
                    i += 2
                    continue
                elif in_comment and i > 0 and line[i-1:i+1] == '*/':
                    in_comment = False
                    i += 1
                    continue

            if in_comment:
                i += 1
                continue

            # Handle strings
            if char in ['"', "'", '`'] and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
            elif not in_string:
                # Track brackets outside strings
                if char == '{':
                    brace_stack.append((html_line, line_num, i, 'open'))
                elif char == '}':
                    if brace_stack:
                        brace_stack.pop()
                    else:
                        print(f"WARNING HTML:{html_line:4d} JS:{line_num:3d} col:{i:2d} - Extra closing brace '}}' (no matching opening)")

                elif char == '(':
                    paren_stack.append((html_line, line_num, i, 'open'))
                elif char == ')':
                    if paren_stack:
                        paren_stack.pop()
                    else:
                        print(f"WARNING HTML:{html_line:4d} JS:{line_num:3d} col:{i:2d} - Extra closing paren ')' (no matching opening)")

                elif char == '[':
                    bracket_stack.append((html_line, line_num, i, 'open'))
                elif char == ']':
                    if bracket_stack:
                        bracket_stack.pop()
                    else:
                        print(f"WARNING HTML:{html_line:4d} JS:{line_num:3d} col:{i:2d} - Extra closing bracket ']' (no matching opening)")

            i += 1

    # Report unclosed items
    print("\nUNCLOSED ITEMS:")
    print("-" * 20)

    if brace_stack:
        print(f"Missing {len(brace_stack)} closing brace(s) '}}' for:")
        for html_line, js_line, col, _ in brace_stack[-5:]:  # Show last 5
            context = lines[js_line-1][max(0, col-10):col+20]
            print(f"  HTML:{html_line:4d} JS:{js_line:3d} col:{col:2d} - ...{context}...")

    if paren_stack:
        print(f"Missing {len(paren_stack)} closing parenthesis(es) ')' for:")
        for html_line, js_line, col, _ in paren_stack[-3:]:  # Show last 3
            context = lines[js_line-1][max(0, col-10):col+20]
            print(f"  HTML:{html_line:4d} JS:{js_line:3d} col:{col:2d} - ...{context}...")

    if bracket_stack:
        print(f"Missing {len(bracket_stack)} closing bracket(s) ']' for:")
        for html_line, js_line, col, _ in bracket_stack:
            context = lines[js_line-1][max(0, col-10):col+20]
            print(f"  HTML:{html_line:4d} JS:{js_line:3d} col:{col:2d} - ...{context}...")

    # Look for function definitions that might be unclosed
    print("\nFUNCTION ANALYSIS:")
    print("-" * 18)

    function_pattern = r'^\s*(async\s+)?function\s+(\w+)\s*\('
    for line_num, line in enumerate(lines, 1):
        if re.search(function_pattern, line):
            html_line = line_num + 296
            print(f"HTML:{html_line:4d} JS:{line_num:3d} - {line.strip()}")

    print(f"\nTotal unclosed: {len(brace_stack)} braces, {len(paren_stack)} parens, {len(bracket_stack)} brackets")


if __name__ == "__main__":
    debug_js_syntax()