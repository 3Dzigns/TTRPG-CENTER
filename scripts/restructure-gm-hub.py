#!/usr/bin/env python3
"""
Restructure GM Hub to match Player Hub layout with:
- AI Assistant panel always visible (left column)
- Sources panel always visible (right column)
- Game management tabs in left column
"""

# Read the original file
with open('apps/web/components/gm/gm-hub.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the return statement (around line 490)
return_idx = next(i for i, line in enumerate(lines) if 'return (' in line and i > 480)

# Find where the grid starts (around line 512)
grid_idx = next(i for i, line in enumerate(lines) if 'grid gap-6 lg:grid-cols' in line and i > 500)

# Find where the AI Assistant section starts (around line 816)
ai_section_start = next(i for i, line in enumerate(lines) if '{/* AI Assistant Section */}' in line and i > 800)

# Find where the AI Assistant section ends (around line 921)
ai_section_end = next(i for i, line in enumerate(lines) if '</section>' in line and i > ai_section_start and i < 930)

# Extract the AI Assistant section
ai_assistant_lines = lines[ai_section_start:ai_section_end+1]

# Remove AI Assistant from its current location
lines_without_ai = lines[:ai_section_start] + lines[ai_section_end+1:]

# Now insert the restructured layout
new_layout = f'''      <div className="grid gap-6 xl:grid-cols-[2fr_1.5fr]">
        <div className="space-y-6">
'''

# Write output
print(f"Found return at line {return_idx}")
print(f"Found grid at line {grid_idx}")
print(f"Found AI section at lines {ai_section_start}-{ai_section_end}")
print(f"\\nAI Assistant section has {len(ai_assistant_lines)} lines")
print("Restructuring would move AI Assistant to always be visible outside game conditional")
