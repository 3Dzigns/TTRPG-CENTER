#!/bin/bash
# This script will help visualize what needs to change

echo "Current structure:"
echo "- Lines 1-510: Imports, state, handlers"
echo "- Lines 511-813: Game list (left column) + Game details with tabs (right column)"  
echo "- Lines 814-919: AI Assistant (INSIDE activeGame conditional)"
echo "- Lines 920-927: Usage meters"
echo ""
echo "Needed structure (like Player Hub):"
echo "- Lines 1-510: Imports, state, handlers (same)"
echo "- Line 511: Change grid to xl:grid-cols-[2fr_1.5fr]"
echo "- Left column (2fr): Game list + AI Assistant (always visible)"
echo "- Right column (1.5fr): Sources panel (always visible)"
echo "- Below grid: Game details/members/settings tabs (conditionally shown when game selected)"
