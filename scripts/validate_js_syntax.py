#!/usr/bin/env python3
"""
JavaScript Syntax Validator for admin_dashboard.html

This script extracts JavaScript content from the admin dashboard HTML file
and performs basic syntax analysis to identify potential causes of
"Uncaught SyntaxError: Unexpected end of input" errors.

Focus: JavaScript block between {% block extra_scripts %} and {% endblock %}
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any


class JSyntaxAnalyzer:
    """Analyzes JavaScript syntax for common issues causing unexpected end of input."""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.issues = []

    def log(self, message: str):
        """Debug logging."""
        if self.debug:
            print(f"[DEBUG] {message}")

    def extract_js_from_html(self, html_content: str) -> str:
        """Extract JavaScript content from HTML, focusing on the extra_scripts block."""
        self.log("Extracting JavaScript from HTML...")

        # Look for the extra_scripts block
        pattern = r'{% block extra_scripts %}(.*?){% endblock %}'
        match = re.search(pattern, html_content, re.DOTALL)

        if not match:
            self.log("No extra_scripts block found")
            return ""

        scripts_block = match.group(1)
        self.log(f"Found extra_scripts block with {len(scripts_block)} characters")

        # Extract content between <script> tags
        script_pattern = r'<script[^>]*>(.*?)</script>'
        script_matches = re.findall(script_pattern, scripts_block, re.DOTALL)

        if not script_matches:
            self.log("No <script> tags found in extra_scripts block")
            return ""

        # Combine all script content
        js_content = '\n'.join(script_matches)
        self.log(f"Extracted {len(js_content)} characters of JavaScript")

        return js_content

    def count_brackets_and_quotes(self, js_content: str) -> Dict[str, Any]:
        """Count opening/closing brackets, parentheses, braces, and quotes."""
        self.log("Counting brackets, braces, parentheses, and quotes...")

        counts = {
            'braces_open': 0,
            'braces_close': 0,
            'parens_open': 0,
            'parens_close': 0,
            'brackets_open': 0,
            'brackets_close': 0,
            'single_quotes': 0,
            'double_quotes': 0,
            'template_literals': 0,
            'issues': []
        }

        # Track string/comment context to avoid counting inside strings
        in_single_quote = False
        in_double_quote = False
        in_template_literal = False
        in_single_comment = False
        in_multi_comment = False
        escaped = False

        for i, char in enumerate(js_content):
            line_num = js_content[:i].count('\n') + 1

            # Handle escape sequences
            if escaped:
                escaped = False
                continue

            if char == '\\' and (in_single_quote or in_double_quote or in_template_literal):
                escaped = True
                continue

            # Handle comments
            if not (in_single_quote or in_double_quote or in_template_literal):
                if i < len(js_content) - 1:
                    if char == '/' and js_content[i + 1] == '/':
                        in_single_comment = True
                        continue
                    elif char == '/' and js_content[i + 1] == '*':
                        in_multi_comment = True
                        continue

                if in_single_comment and char == '\n':
                    in_single_comment = False
                    continue

                if in_multi_comment and i > 0:
                    if js_content[i - 1] == '*' and char == '/':
                        in_multi_comment = False
                        continue

            # Skip if in comments
            if in_single_comment or in_multi_comment:
                continue

            # Handle string delimiters
            if char == "'" and not (in_double_quote or in_template_literal):
                in_single_quote = not in_single_quote
                counts['single_quotes'] += 1
            elif char == '"' and not (in_single_quote or in_template_literal):
                in_double_quote = not in_double_quote
                counts['double_quotes'] += 1
            elif char == '`' and not (in_single_quote or in_double_quote):
                in_template_literal = not in_template_literal
                counts['template_literals'] += 1

            # Skip counting brackets if inside strings
            elif not (in_single_quote or in_double_quote or in_template_literal):
                if char == '{':
                    counts['braces_open'] += 1
                elif char == '}':
                    counts['braces_close'] += 1
                elif char == '(':
                    counts['parens_open'] += 1
                elif char == ')':
                    counts['parens_close'] += 1
                elif char == '[':
                    counts['brackets_open'] += 1
                elif char == ']':
                    counts['brackets_close'] += 1

        # Check for unclosed strings/template literals
        if in_single_quote:
            counts['issues'].append("Unclosed single quote string")
        if in_double_quote:
            counts['issues'].append("Unclosed double quote string")
        if in_template_literal:
            counts['issues'].append("Unclosed template literal")
        if in_multi_comment:
            counts['issues'].append("Unclosed multi-line comment")

        return counts

    def analyze_syntax_issues(self, counts: Dict[str, Any]) -> List[str]:
        """Analyze counts to identify potential syntax issues."""
        self.log("Analyzing potential syntax issues...")

        issues = list(counts['issues'])  # Start with issues from parsing

        # Check bracket mismatches
        if counts['braces_open'] != counts['braces_close']:
            diff = counts['braces_open'] - counts['braces_close']
            if diff > 0:
                issues.append(f"Missing {diff} closing brace(s) '}}' - this commonly causes 'unexpected end of input'")
            else:
                issues.append(f"{abs(diff)} extra closing brace(s) '}}'")

        if counts['parens_open'] != counts['parens_close']:
            diff = counts['parens_open'] - counts['parens_close']
            if diff > 0:
                issues.append(f"Missing {diff} closing parenthesis(es) ')' - this can cause 'unexpected end of input'")
            else:
                issues.append(f"{abs(diff)} extra closing parenthesis(es) ')'")

        if counts['brackets_open'] != counts['brackets_close']:
            diff = counts['brackets_open'] - counts['brackets_close']
            if diff > 0:
                issues.append(f"Missing {diff} closing bracket(s) ']' - this can cause 'unexpected end of input'")
            else:
                issues.append(f"{abs(diff)} extra closing bracket(s) ']'")

        # Check quote mismatches
        if counts['single_quotes'] % 2 != 0:
            issues.append("Odd number of single quotes - likely unclosed string literal")

        if counts['double_quotes'] % 2 != 0:
            issues.append("Odd number of double quotes - likely unclosed string literal")

        if counts['template_literals'] % 2 != 0:
            issues.append("Odd number of template literal backticks - likely unclosed template literal")

        return issues

    def find_line_with_issue(self, js_content: str, target_line: int = 518) -> str:
        """Find content around the specified line number for context."""
        lines = js_content.split('\n')

        # Adjust for 0-based indexing and HTML line offset
        # The JavaScript starts around line 297 in HTML, so line 518 would be around line 221 in JS
        js_line = target_line - 296  # Approximate offset

        if js_line < 0 or js_line >= len(lines):
            return f"Line {target_line} (JS line ~{js_line}) is outside the JavaScript content range"

        # Show context around the target line
        start = max(0, js_line - 3)
        end = min(len(lines), js_line + 4)

        context_lines = []
        for i in range(start, end):
            marker = ">>> " if i == js_line else "    "
            html_line_num = i + 297  # Convert back to HTML line number
            context_lines.append(f"{marker}HTML:{html_line_num:4d} JS:{i+1:3d}: {lines[i]}")

        return '\n'.join(context_lines)


def main():
    """Main execution function."""
    print("JavaScript Syntax Validator for admin_dashboard.html")
    print("=" * 55)

    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    html_file = project_root / "templates" / "admin_dashboard.html"

    if not html_file.exists():
        print(f"ERROR: Could not find {html_file}")
        sys.exit(1)

    print(f"Analyzing: {html_file}")
    print()

    # Read HTML file
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"ERROR: Could not read {html_file}: {e}")
        sys.exit(1)

    # Initialize analyzer
    analyzer = JSyntaxAnalyzer(debug=True)

    # Extract JavaScript
    js_content = analyzer.extract_js_from_html(html_content)

    if not js_content:
        print("ERROR: No JavaScript content found in extra_scripts block")
        sys.exit(1)

    print(f"JavaScript content length: {len(js_content)} characters")
    print(f"JavaScript lines: {len(js_content.split(chr(10)))}")
    print()

    # Analyze syntax
    counts = analyzer.count_brackets_and_quotes(js_content)
    issues = analyzer.analyze_syntax_issues(counts)

    # Display results
    print("BRACKET/BRACE/PARENTHESIS ANALYSIS:")
    print("-" * 40)
    print(f"Opening braces '{{':    {counts['braces_open']}")
    print(f"Closing braces '}}':    {counts['braces_close']}")
    print(f"Opening parentheses '(': {counts['parens_open']}")
    print(f"Closing parentheses ')': {counts['parens_close']}")
    print(f"Opening brackets '[':    {counts['brackets_open']}")
    print(f"Closing brackets ']':    {counts['brackets_close']}")
    print()

    print("QUOTE ANALYSIS:")
    print("-" * 15)
    print(f"Single quotes \"'\": {counts['single_quotes']} ({'even' if counts['single_quotes'] % 2 == 0 else 'ODD - ISSUE'})")
    print(f"Double quotes '\"': {counts['double_quotes']} ({'even' if counts['double_quotes'] % 2 == 0 else 'ODD - ISSUE'})")
    print(f"Template literals '`': {counts['template_literals']} ({'even' if counts['template_literals'] % 2 == 0 else 'ODD - ISSUE'})")
    print()

    print("SYNTAX ISSUES DETECTED:")
    print("-" * 25)
    if issues:
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")
        print()

        # Show context around line 518 (the reported error line)
        print("CONTEXT AROUND LINE 518 (HTML) / ~222 (JavaScript):")
        print("-" * 55)
        context = analyzer.find_line_with_issue(js_content, 518)
        print(context)

    else:
        print("✓ No obvious syntax issues detected!")
        print("  The 'unexpected end of input' error might be caused by:")
        print("  - Dynamic JavaScript loaded later")
        print("  - Issues in other JavaScript files")
        print("  - Server-side template rendering issues")
        print("  - Browser-specific parsing differences")

    print()
    print("RECOMMENDATIONS:")
    print("-" * 15)
    if issues:
        print("1. Fix the syntax issues listed above")
        print("2. Use browser developer tools to get the exact error location")
        print("3. Check for missing semicolons or commas")
        print("4. Validate the JavaScript in an online JS validator")
    else:
        print("1. Check browser console for the exact error line")
        print("2. Look for dynamically generated JavaScript")
        print("3. Verify server-side template rendering")
        print("4. Check for issues in included JavaScript libraries")

    # Exit with appropriate code
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()