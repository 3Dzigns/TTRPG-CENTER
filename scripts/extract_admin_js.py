#!/usr/bin/env python3

import re

# Read the admin template
with open('templates/admin_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the JavaScript block between {% block extra_scripts %} and {% endblock %}
pattern = r'{% block extra_scripts %}.*?<script>(.*?)</script>.*?{% endblock %}'
match = re.search(pattern, content, re.DOTALL)

if match:
    js_content = match.group(1)

    # Write the extracted JavaScript to a file for validation
    with open('extracted_admin.js', 'w', encoding='utf-8') as f:
        f.write(js_content)

    print(f"Extracted {len(js_content)} characters of JavaScript")
    print("JavaScript saved to: extracted_admin.js")

    # Basic syntax check - count brackets
    brace_count = js_content.count('{') - js_content.count('}')
    paren_count = js_content.count('(') - js_content.count(')')
    bracket_count = js_content.count('[') - js_content.count(']')

    print(f"\nBracket balance check:")
    print(f"Braces: {brace_count} (should be 0)")
    print(f"Parentheses: {paren_count} (should be 0)")
    print(f"Brackets: {bracket_count} (should be 0)")

    if brace_count == 0 and paren_count == 0 and bracket_count == 0:
        print("✓ Basic bracket balance looks correct")
    else:
        print("✗ Bracket imbalance detected")

    # Check for template literal balance
    backtick_count = js_content.count('`')
    print(f"Template literals (backticks): {backtick_count} (should be even)")

    if backtick_count % 2 == 0:
        print("✓ Template literal balance looks correct")
    else:
        print("✗ Template literal imbalance detected")

else:
    print("Could not extract JavaScript block from template")