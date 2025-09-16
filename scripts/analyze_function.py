#!/usr/bin/env python3

with open('templates/admin_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# Find the showLogDetails function
start_line = None
for i, line in enumerate(lines):
    if 'function showLogDetails' in line:
        start_line = i
        break

if start_line:
    print(f'Function starts at line {start_line + 1}')

    # Show first few lines to understand structure
    for i in range(start_line, min(start_line + 10, len(lines))):
        print(f'{i+1:4d}: {lines[i]}')

    print("\n--- Counting brackets ---")

    # Count braces and parentheses from the function start
    brace_count = 0
    paren_count = 0
    in_template_literal = False
    backtick_count = 0

    for i in range(start_line, min(len(lines), start_line + 200)):  # Limit to reasonable range
        line = lines[i]
        line_brace_change = 0
        line_paren_change = 0

        # Count backticks to track template literals
        line_backticks = line.count('`')
        backtick_count += line_backticks

        # Simple bracket counting (ignoring string complexities for now)
        open_braces = line.count('{')
        close_braces = line.count('}')
        open_parens = line.count('(')
        close_parens = line.count(')')

        brace_count += open_braces - close_braces
        paren_count += open_parens - close_parens

        line_brace_change = open_braces - close_braces
        line_paren_change = open_parens - close_parens

        if line_brace_change != 0 or line_paren_change != 0:
            print(f'Line {i+1:4d}: braces={brace_count:2d} ({line_brace_change:+d}), parens={paren_count:2d} ({line_paren_change:+d}) | {line.strip()[:60]}')

        # Check if function is complete
        if brace_count == 0 and i > start_line:
            print(f'\nFunction ends at line {i + 1}')
            print(f'Final counts: braces={brace_count}, parens={paren_count}')
            print(f'Total backticks in function: {backtick_count}')
            if paren_count != 0:
                print(f'ERROR: Unbalanced parentheses: {paren_count}')
            if backtick_count % 2 != 0:
                print(f'ERROR: Unbalanced template literals (odd number of backticks): {backtick_count}')
            break
    else:
        print(f'Function may be incomplete. Final counts: braces={brace_count}, parens={paren_count}')
        print(f'Total backticks: {backtick_count}')