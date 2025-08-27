# Post-Push Code Review System

Automated code review system that runs after `git push` using OpenAI to analyze code changes.

## Setup

### 1. Prerequisites
- OpenAI API key set in environment variable `OPENAI_API_KEY`
- Git repository with commit history
- PowerShell execution environment

### 2. Configuration

The review mode is configured in `.ci/review_mode.txt`:

```
diff    # Review only the most recent commit
full    # Review entire repository against initial commit
```

### 3. Directory Structure

```
.ci/
├── review_mode.txt          # Configuration file
docs/reviews/
├── YYYYMMDD_HHMMSS_diff_review.md     # Diff mode reviews
├── YYYYMMDD_HHMMSS_full_review.md     # Full mode reviews
scripts/
├── post-push-review.ps1     # Main review script
├── test-review.ps1          # Test script (no API calls)
```

## Usage

### Manual Execution

```powershell
# Run review with current configuration
.\scripts\post-push-review.ps1

# Run with specific parameters
.\scripts\post-push-review.ps1 -Model "gpt-4o" -OpenAIApiKey "your-key"
```

### Post-Push Hook

Add to your git workflow or create a wrapper script:

```powershell
# After git push
git push
if ($LASTEXITCODE -eq 0) {
    Write-Host "Running automated code review..."
    .\scripts\post-push-review.ps1
}
```

### Testing (No API Calls)

```powershell
# Test functionality without OpenAI API
.\scripts\test-review.ps1
```

## Review Modes

### Diff Mode (`diff`)
- **Scope**: Reviews only the most recent commit
- **Use Case**: Regular development workflow
- **Performance**: Fast, low cost
- **Command**: `git show --format="" --unified=3 HEAD -- . ":(exclude)**/*.md"`

### Full Mode (`full`)
- **Scope**: Reviews entire repository from initial commit
- **Use Case**: Comprehensive audits, initial setup
- **Performance**: Slower, higher cost
- **Command**: `git diff --unified=3 <initial-commit>..HEAD -- . ":(exclude)**/*.md"`

## Review Output

### Markdown Structure
```markdown
# Code Review - <mode> Mode

**Date**: 2025-08-27 14:35:00 UTC
**Commit**: abc123def456
**Message**: Fix authentication bug
**Model**: gpt-4o-mini

## Summary
- Key changes identified
- Overall assessment

## Findings
### Finding 1
**File**: app/server.py
**Lines**: 45-52
**Severity**: MEDIUM

Description of the issue...

**Suggested Fix**:
```python
# Sample code fix
def fixed_function():
    pass
```

## Tests
- Missing test recommendations

## Security/Concurrency
- Security issues if any

## Recommendation
**GO** / **NO-GO**
```

### Finding Severities
- **LOW**: Minor issues, style improvements
- **MEDIUM**: Logic issues, potential bugs
- **HIGH**: Security concerns, major bugs
- **CRITICAL**: Breaking changes, security vulnerabilities

## Configuration Options

### Environment Variables
- `OPENAI_API_KEY`: Required for API access
- Model can be overridden via parameter

### Script Parameters
```powershell
param(
    [string]$OpenAIApiKey = $env:OPENAI_API_KEY,
    [string]$GitHubRepo = "https://github.com/3Dzigns/TTRPG-CENTER.git",
    [string]$Model = "gpt-4o-mini"
)
```

## File Exclusions

The system automatically excludes:
- Markdown files (`*.md`) - treated as documentation context only
- Files in `.gitignore`
- Binary files (handled by git diff)

## Error Handling

### Common Issues
1. **No OpenAI API Key**
   ```
   ERROR: OPENAI_API_KEY environment variable not set
   ```
   **Solution**: Set the environment variable or pass as parameter

2. **No Code Changes**
   ```
   WARN: No code changes found (excluding .md files)
   ```
   **Result**: Creates minimal review report

3. **Git Command Failure**
   ```
   ERROR: Failed to get git diff
   ```
   **Solution**: Ensure you're in a git repository with commit history

4. **OpenAI API Failure**
   ```
   ERROR: Failed to call OpenAI API
   ```
   **Solution**: Check API key, network connection, and rate limits

## Integration Examples

### Git Hook (PowerShell)
```powershell
# .git/hooks/post-push (if such hook existed)
#!/usr/bin/env pwsh
.\scripts\post-push-review.ps1
```

### CI/CD Pipeline
```yaml
# GitHub Actions example
- name: Run Code Review
  run: |
    pwsh -ExecutionPolicy Bypass -File "scripts/post-push-review.ps1"
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### Manual Workflow
```powershell
# Development workflow
git add .
git commit -m "Implement new feature"
git push
.\scripts\post-push-review.ps1
```

## Cost Considerations

### Token Usage (Approximate)
- **Diff Mode**: 500-2000 tokens per commit
- **Full Mode**: 5000-50000+ tokens for large repositories

### Optimization
- Use diff mode for regular development
- Use full mode sparingly for audits
- Consider token limits for large changes
- Monitor OpenAI API usage and costs

## Troubleshooting

### Test Mode First
```powershell
# Always test before using API
.\scripts\test-review.ps1
```

### Verbose Logging
The script includes detailed logging with timestamps:
```
[2025-08-27 14:35:02] [INFO] Starting post-push code review...
[2025-08-27 14:35:02] [INFO] Review mode: diff
[2025-08-27 14:35:02] [INFO] Retrieved diff: 229 characters
```

### Manual Review
Generated review files are stored in `docs/reviews/` with timestamps for manual inspection and tracking.