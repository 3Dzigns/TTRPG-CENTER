#!/usr/bin/env python3

with open('extracted_admin.js', 'r') as f:
    content = f.read()

# Find lines with parentheses imbalance
lines = content.split('\n')
running_paren_count = 0

print("Lines with parentheses changes:")
print("=" * 60)

for i, line in enumerate(lines, 1):
    line_open = line.count('(')
    line_close = line.count(')')
    line_change = line_open - line_close
    running_paren_count += line_change

    if line_change != 0:
        print(f'Line {i:3d}: total={running_paren_count:3d} ({line_change:+d}) | {line.strip()[:80]}')

print(f'\nFinal balance: {running_paren_count}')

if running_paren_count < 0:
    print(f"ERROR: {abs(running_paren_count)} extra closing parentheses found!")
elif running_paren_count > 0:
    print(f"ERROR: {running_paren_count} unclosed opening parentheses found!")
else:
    print("Parentheses are balanced.")