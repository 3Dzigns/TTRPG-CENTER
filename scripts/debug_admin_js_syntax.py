#!/usr/bin/env python3
"""
JavaScript Syntax Error Debugger for Admin Dashboard
Analyzes template files and identifies syntax issues causing "Unexpected end of input"
"""

import re
import json
from typing import List, Dict, Tuple, Optional
from pathlib import Path

class JSDebugger:
    def __init__(self):
        self.base_template_path = Path("templates/base.html")
        self.admin_template_path = Path("templates/admin_dashboard.html")
        self.errors = []
        self.warnings = []

    def analyze_templates(self):
        """Main analysis function"""
        print("JavaScript Syntax Error Analysis")
        print("=" * 50)

        # Step 1: Read template files
        base_content = self._read_file(self.base_template_path)
        admin_content = self._read_file(self.admin_template_path)

        if not base_content or not admin_content:
            return

        # Step 2: Calculate line mappings
        self._calculate_line_mapping(base_content, admin_content)

        # Step 3: Extract JavaScript content
        base_js = self._extract_javascript(base_content, "base.html")
        admin_js = self._extract_javascript(admin_content, "admin_dashboard.html")

        # Step 4: Comprehensive syntax validation
        print("\nJavaScript Content Analysis")
        print("-" * 30)

        if base_js:
            print(f"Base template JS: {len(base_js)} characters")
            self._validate_js_syntax(base_js, "base.html", 219)  # JS starts at line 219 in base

        if admin_js:
            print(f"Admin template JS: {len(admin_js)} characters")
            # Admin JS starts at line 297 in admin template, which maps to line 631 in combined
            admin_start_line = 334 + 297  # base lines + admin line offset
            self._validate_js_syntax(admin_js, "admin_dashboard.html", admin_start_line)

        # Step 5: Focus on line 1346 area
        self._analyze_line_1346_area(base_content, admin_content)

        # Step 6: Summary
        self._print_summary()

    def _read_file(self, path: Path) -> Optional[str]:
        """Read template file with error handling"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"Read {path}: {len(content)} characters, {len(content.splitlines())} lines")
                return content
        except Exception as e:
            print(f"Error reading {path}: {e}")
            return None

    def _calculate_line_mapping(self, base_content: str, admin_content: str):
        """Calculate exact line mapping between templates"""
        base_lines = base_content.splitlines()
        admin_lines = admin_content.splitlines()

        print(f"\nLine Mapping Analysis")
        print(f"Base template: {len(base_lines)} lines")
        print(f"Admin template: {len(admin_lines)} lines")

        # Find {% endblock %} in base to understand structure
        content_block_end = None
        scripts_block_start = None

        for i, line in enumerate(base_lines, 1):
            if '{% block content %}{% endblock %}' in line:
                content_block_end = i
            elif '{% block extra_scripts %}{% endblock %}' in line:
                scripts_block_start = i

        # Estimate combined template size
        # Base template content is replaced by admin content, scripts are appended
        admin_content_lines = len([l for l in admin_lines if not l.strip().startswith('{% extends')
                                  and not l.strip().startswith('{% block title')])

        estimated_combined_lines = len(base_lines) + len(admin_lines) - 4  # rough estimate

        print(f"Estimated combined template: ~{estimated_combined_lines} lines")
        print(f"Error reported at line: 1346")

        # Calculate where line 1346 falls
        if estimated_combined_lines >= 1346:
            print(f"Line 1346 is within expected range")

            # Line 1346 should be in the admin JS block
            admin_js_start = 297  # {% block extra_scripts %} starts at line 296 in admin
            admin_js_end = 1040   # {% endblock %} at line 1040 in admin

            base_end_estimate = 334  # base template ends around here
            line_1346_in_admin = 1346 - base_end_estimate

            print(f"Line 1346 maps to approximately line {line_1346_in_admin} in admin template")

            if 296 <= line_1346_in_admin <= 1040:
                print(f"Line 1346 is in admin JavaScript block (lines 296-1040)")
            else:
                print(f"WARNING: Line 1346 may be outside admin JavaScript block")
        else:
            print(f"ERROR: Line 1346 exceeds estimated template size")

    def _extract_javascript(self, content: str, filename: str) -> str:
        """Extract JavaScript content from template"""
        js_blocks = []

        # Find all <script> blocks
        script_pattern = r'<script[^>]*>(.*?)</script>'
        matches = re.findall(script_pattern, content, re.DOTALL)

        for i, match in enumerate(matches):
            js_blocks.append(f"// === {filename} Script Block {i+1} ===\n{match}\n")

        return '\n'.join(js_blocks)

    def _validate_js_syntax(self, js_content: str, filename: str, start_line: int):
        """Comprehensive JavaScript syntax validation"""
        print(f"\nAnalyzing {filename} JavaScript")

        lines = js_content.split('\n')

        # Track bracket/brace/parentheses balance
        brackets = []  # Stack for tracking opening brackets
        in_string = False
        in_regex = False
        in_comment = False
        in_template_literal = False
        string_char = None

        # Counters
        brace_count = 0
        paren_count = 0
        bracket_count = 0

        errors_found = []

        for line_idx, line in enumerate(lines):
            current_line = start_line + line_idx

            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith('//'):
                continue

            # Analyze character by character for this line
            i = 0
            while i < len(line):
                char = line[i]
                prev_char = line[i-1] if i > 0 else ''
                next_char = line[i+1] if i < len(line)-1 else ''

                # Handle string literals
                if not in_comment and not in_regex:
                    if char in ['"', "'", '`'] and prev_char != '\\':
                        if not in_string:
                            in_string = True
                            string_char = char
                            if char == '`':
                                in_template_literal = True
                        elif char == string_char:
                            in_string = False
                            string_char = None
                            in_template_literal = False

                # Handle comments
                if not in_string and char == '/' and next_char == '/':
                    in_comment = True
                    break  # Rest of line is comment

                if not in_string and char == '/' and next_char == '*':
                    in_comment = True
                    i += 1  # Skip next char

                if in_comment and char == '*' and next_char == '/':
                    in_comment = False
                    i += 1  # Skip next char

                # Track brackets when not in strings or comments
                if not in_string and not in_comment:
                    if char == '{':
                        brace_count += 1
                        brackets.append(('{', current_line, i))
                    elif char == '}':
                        brace_count -= 1
                        if brackets and brackets[-1][0] == '{':
                            brackets.pop()
                        else:
                            errors_found.append(f"Line {current_line}: Unmatched closing brace '}}' at position {i}")

                    elif char == '(':
                        paren_count += 1
                        brackets.append(('(', current_line, i))
                    elif char == ')':
                        paren_count -= 1
                        if brackets and brackets[-1][0] == '(':
                            brackets.pop()
                        else:
                            errors_found.append(f"Line {current_line}: Unmatched closing parenthesis ')' at position {i}")

                    elif char == '[':
                        bracket_count += 1
                        brackets.append(('[', current_line, i))
                    elif char == ']':
                        bracket_count -= 1
                        if brackets and brackets[-1][0] == '[':
                            brackets.pop()
                        else:
                            errors_found.append(f"Line {current_line}: Unmatched closing bracket ']' at position {i}")

                i += 1

        # Check for unclosed constructs
        if brace_count > 0:
            errors_found.append(f"ERROR: {brace_count} unclosed brace(s) '{{' - this causes 'Unexpected end of input'")
        if paren_count > 0:
            errors_found.append(f"ERROR: {paren_count} unclosed parenthesis(es) '(' - this causes 'Unexpected end of input'")
        if bracket_count > 0:
            errors_found.append(f"ERROR: {bracket_count} unclosed bracket(s) '[' - this causes 'Unexpected end of input'")

        if in_string:
            errors_found.append(f"ERROR: Unclosed string literal (started with {string_char}) - this causes 'Unexpected end of input'")

        if in_template_literal:
            errors_found.append(f"ERROR: Unclosed template literal (backtick) - this causes 'Unexpected end of input'")

        # Show unmatched opening brackets
        for bracket_type, line_num, pos in brackets:
            opener = {'(': 'parenthesis', '{': 'brace', '[': 'bracket'}[bracket_type]
            errors_found.append(f"ERROR: Unclosed {opener} '{bracket_type}' at line {line_num}, position {pos}")

        # Summary for this file
        if errors_found:
            print(f"Found {len(errors_found)} syntax errors:")
            for error in errors_found:
                print(f"  {error}")
                self.errors.append(f"{filename}: {error}")
        else:
            print(f"No syntax errors found")

        print(f"Bracket balance: {{ {brace_count}, ( {paren_count}, [ {bracket_count}")

    def _analyze_line_1346_area(self, base_content: str, admin_content: str):
        """Focus analysis on the problematic line 1346 area"""
        print(f"\nLine 1346 Area Analysis")
        print("-" * 25)

        # Extract admin JavaScript block (lines 296-1040)
        admin_lines = admin_content.splitlines()

        # Get the JavaScript block
        js_start = None
        js_end = None
        for i, line in enumerate(admin_lines):
            if '{% block extra_scripts %}' in line:
                js_start = i + 1  # Start after the block declaration
            elif '{% endblock %}' in line and js_start is not None:
                js_end = i
                break

        if js_start is not None and js_end is not None:
            js_lines = admin_lines[js_start:js_end]
            print(f"JavaScript block: lines {js_start+1} to {js_end} in admin template")
            print(f"JavaScript content: {len(js_lines)} lines")

            # Map line 1346 to this block
            base_lines_count = len(base_content.splitlines())
            # Rough estimate: line 1346 would be around line 1346 - 334 = 1012 in admin template
            estimated_admin_line = 1346 - 334

            if js_start <= estimated_admin_line <= js_end:
                relative_js_line = estimated_admin_line - js_start
                print(f"Line 1346 maps to approximately line {relative_js_line} in the JavaScript block")

                # Show context around the problematic line
                start_context = max(0, relative_js_line - 5)
                end_context = min(len(js_lines), relative_js_line + 5)

                print(f"\nContext around line {relative_js_line} in JavaScript:")
                for i in range(start_context, end_context):
                    line_num = js_start + i + 1
                    marker = " >>> " if i == relative_js_line else "     "
                    content = js_lines[i] if i < len(js_lines) else ""
                    print(f"{marker}{line_num:4d}: {content}")

                # Analyze specific line for syntax issues
                if relative_js_line < len(js_lines):
                    problematic_line = js_lines[relative_js_line]
                    self._analyze_specific_line(problematic_line, estimated_admin_line)

    def _analyze_specific_line(self, line: str, line_number: int):
        """Analyze a specific line for syntax issues"""
        print(f"\nDetailed Analysis of Line {line_number}")
        print(f"Content: {repr(line)}")

        issues = []

        # Check for common issues
        if line.count('{') != line.count('}'):
            issues.append(f"Unbalanced braces: {line.count('{')} opening, {line.count('}')} closing")

        if line.count('(') != line.count(')'):
            issues.append(f"Unbalanced parentheses: {line.count('(')} opening, {line.count(')')} closing")

        if line.count('[') != line.count(']'):
            issues.append(f"Unbalanced brackets: {line.count('[')} opening, {line.count(']')} closing")

        # Check for unclosed strings
        in_string = False
        string_char = None
        for i, char in enumerate(line):
            if char in ['"', "'"] and (i == 0 or line[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None

        if in_string:
            issues.append(f"Unclosed string starting with {string_char}")

        # Check for template literal issues
        backtick_count = line.count('`')
        if backtick_count % 2 != 0:
            issues.append(f"Unclosed template literal (backtick)")

        if issues:
            print("Issues found:")
            for issue in issues:
                print(f"  - {issue}")
                self.errors.append(f"Line {line_number}: {issue}")
        else:
            print("No obvious syntax issues on this line")

    def _print_summary(self):
        """Print analysis summary"""
        print(f"\nAnalysis Summary")
        print("=" * 20)

        if self.errors:
            print(f"{len(self.errors)} ERRORS found:")
            for error in self.errors:
                print(f"  {error}")

            print(f"\nMost Likely Cause of 'Unexpected end of input':")

            # Prioritize errors that typically cause this issue
            priority_keywords = ['unclosed', 'unmatched', 'unbalanced']
            priority_errors = [e for e in self.errors
                             if any(keyword in e.lower() for keyword in priority_keywords)]

            if priority_errors:
                print(f"  => {priority_errors[0]}")
            else:
                print(f"  => {self.errors[0]}")

        else:
            print("No syntax errors found")
            print("The 'Unexpected end of input' error may be caused by:")
            print("  - Dynamic content injection")
            print("  - Template rendering issues")
            print("  - Browser-specific parsing")

        if self.warnings:
            print(f"\n{len(self.warnings)} warnings:")
            for warning in self.warnings:
                print(f"  {warning}")

def main():
    """Main execution function"""
    debugger = JSDebugger()

    # Check if template files exist
    if not debugger.base_template_path.exists():
        print(f"Base template not found: {debugger.base_template_path}")
        return

    if not debugger.admin_template_path.exists():
        print(f"Admin template not found: {debugger.admin_template_path}")
        return

    debugger.analyze_templates()

if __name__ == "__main__":
    main()