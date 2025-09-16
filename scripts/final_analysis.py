#!/usr/bin/env python3
"""
Final comprehensive analysis of the JavaScript syntax issue
"""

import re

def analyze_admin_template():
    """Analyze the admin template for JavaScript syntax issues"""

    print("=" * 60)
    print("FINAL JAVASCRIPT SYNTAX ANALYSIS")
    print("=" * 60)

    # Read the template file
    with open('templates/admin_dashboard.html', 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()

    print(f"Template file: {len(lines)} lines")

    # Find the JavaScript block boundaries
    js_start = None
    js_end = None

    for i, line in enumerate(lines):
        if '{% block extra_scripts %}' in line:
            js_start = i + 1  # Line after the block declaration
        elif '{% endblock %}' in line and js_start is not None:
            js_end = i
            break

    if js_start is None or js_end is None:
        print("Could not find JavaScript block boundaries")
        return

    print(f"JavaScript block: lines {js_start+1} to {js_end}")

    # Extract just the JavaScript content (between <script> tags)
    script_start = None
    script_end = None

    for i in range(js_start, js_end):
        line = lines[i].strip()
        if line == '<script>':
            script_start = i + 1
        elif line == '</script>':
            script_end = i
            break

    if script_start is None or script_end is None:
        print("Could not find <script> tag boundaries")
        return

    print(f"Pure JavaScript: lines {script_start+1} to {script_end}")

    # Extract the JavaScript code
    js_lines = lines[script_start:script_end]
    js_content = '\n'.join(js_lines)

    print(f"JavaScript content: {len(js_content)} characters")

    # Analyze brackets and parentheses balance
    analyze_brackets(js_content, script_start + 1)

    # Check for problematic patterns
    check_problematic_patterns(js_content, script_start + 1)

    # Summary
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)

    # Basic balance check
    brace_balance = js_content.count('{') - js_content.count('}')
    paren_balance = js_content.count('(') - js_content.count(')')
    bracket_balance = js_content.count('[') - js_content.count(']')
    backtick_count = js_content.count('`')

    print(f"Bracket balance:")
    print(f"  Braces: {brace_balance} (should be 0)")
    print(f"  Parentheses: {paren_balance} (should be 0)")
    print(f"  Square brackets: {bracket_balance} (should be 0)")
    print(f"  Backticks: {backtick_count} (should be even)")

    errors = []
    if brace_balance != 0:
        errors.append(f"Unbalanced braces: {brace_balance}")
    if paren_balance != 0:
        errors.append(f"Unbalanced parentheses: {paren_balance}")
    if bracket_balance != 0:
        errors.append(f"Unbalanced square brackets: {bracket_balance}")
    if backtick_count % 2 != 0:
        errors.append(f"Unbalanced template literals: {backtick_count}")

    if errors:
        print(f"\nERRORS FOUND ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")
        print(f"\nMost likely cause of 'Unexpected end of input': {errors[0]}")
    else:
        print(f"\nNo syntax errors detected!")
        print("The JavaScript appears to be syntactically correct.")
        print("The browser error may be caused by:")
        print("  - Template rendering issues")
        print("  - Dynamic content injection")
        print("  - Browser-specific parsing")

def analyze_brackets(js_content, start_line_num):
    """Detailed bracket analysis"""

    lines = js_content.split('\n')
    stack = []  # Stack for tracking opening brackets
    line_errors = []

    for line_idx, line in enumerate(lines):
        current_line = start_line_num + line_idx

        # Simple character-by-character analysis
        in_string = False
        string_char = None

        for pos, char in enumerate(line):
            # Handle string literals
            if char in ['"', "'", '`'] and (pos == 0 or line[pos-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None

            # Track brackets outside strings
            if not in_string:
                if char in '({[':
                    stack.append((char, current_line, pos))
                elif char in ')}]':
                    if stack:
                        opener = stack[-1][0]
                        expected = {'(': ')', '{': '}', '[': ']'}
                        if char == expected.get(opener):
                            stack.pop()
                        else:
                            line_errors.append(f"Line {current_line}: Mismatched bracket. Expected '{expected.get(opener)}' but found '{char}' at position {pos}")
                    else:
                        line_errors.append(f"Line {current_line}: Unexpected closing '{char}' at position {pos}")

    # Check for unclosed brackets
    for bracket, line_num, pos in stack:
        line_errors.append(f"Line {line_num}: Unclosed '{bracket}' at position {pos}")

    if line_errors:
        print(f"\nDETAILED BRACKET ANALYSIS - {len(line_errors)} issues found:")
        for error in line_errors:
            print(f"  {error}")
    else:
        print(f"\nDETAILED BRACKET ANALYSIS - No issues found")

def check_problematic_patterns(js_content, start_line_num):
    """Check for specific problematic patterns"""

    lines = js_content.split('\n')
    issues = []

    for line_idx, line in enumerate(lines):
        current_line = start_line_num + line_idx

        # Check for escaped script tags in template literals
        if '<\\/' in line or '<\\script' in line:
            issues.append(f"Line {current_line}: Escaped script tag found: {line.strip()}")

        # Check for unescaped script tags in template literals
        if '`' in line and '</script>' in line:
            issues.append(f"Line {current_line}: Unescaped script tag in template literal: {line.strip()}")

    if issues:
        print(f"\nPROBLEMATIC PATTERNS - {len(issues)} found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print(f"\nPROBLEMATIC PATTERNS - None found")

if __name__ == "__main__":
    analyze_admin_template()