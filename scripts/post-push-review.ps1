# Post-Push Code Review Script
# Automatically reviews code changes using OpenAI based on configuration

param(
    [string]$OpenAIApiKey = $env:OPENAI_API_KEY,
    [string]$GitHubRepo = "https://github.com/3Dzigns/TTRPG-CENTER.git",
    [string]$Model = "gpt-4o-mini"
)

# Configuration
$ReviewModeFile = ".ci/review_mode.txt"
$ReviewsDir = "docs/reviews"
$SystemPrompt = @"
You are a senior software engineer performing a peer review of a pull request.

STRICT SCOPE
- Review ONLY the supplied git DIFF/patch for this PR (changed lines and immediate context).
- Do NOT review or critique changes made to Markdown files (*.md). Treat .md diffs as documentation/context only.
- You may use .md content to understand requirements or intended behavior, but do NOT flag issues about .md changes.
- Do NOT review project-wide requirements, policies, or architecture unless changed lines in code directly violate them.
- Do NOT summarize the whole repo; focus only on code changes.

OUTPUT FORMAT
1. Summary: 2-5 bullet points.
2. Findings: Numbered list. Each finding MUST include:
   - File path and line(s) from the code diff
   - Issue description or improvement opportunity
   - Concrete suggestion with a sample code or patch snippet showing a possible resolution
   - Severity: LOW | MEDIUM | HIGH | CRITICAL
3. Tests: Explicitly call out missing or to-be-updated tests for the new code.
4. Security/Concurrency: Only if visible in the code diff; include the lines and a sample mitigation.
5. GO/NO-GO: Decide based only on the code diff.

TONE
- Be concise, technical, and actionable.
- Always include at least one possible resolution (sample code, config change, or patch) for each issue.
- If context outside the diff is needed, state clearly: Assumption: ...

Remember: this is a developer code review of code changes only. Markdown files are context, not review targets.
"@

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

function Test-Prerequisites {
    Write-Log "Checking prerequisites..."
    
    if (-not $OpenAIApiKey) {
        Write-Log "OPENAI_API_KEY environment variable not set" "ERROR"
        return $false
    }
    
    if (-not (Test-Path $ReviewModeFile)) {
        Write-Log "Review mode file not found: $ReviewModeFile" "ERROR"
        return $false
    }
    
    if (-not (Test-Path $ReviewsDir)) {
        Write-Log "Creating reviews directory: $ReviewsDir"
        New-Item -ItemType Directory -Path $ReviewsDir -Force | Out-Null
    }
    
    # Test git availability
    try {
        git --version | Out-Null
        Write-Log "Git is available"
    } catch {
        Write-Log "Git is not available or not in PATH" "ERROR"
        return $false
    }
    
    return $true
}

function Get-ReviewMode {
    $mode = Get-Content $ReviewModeFile -ErrorAction SilentlyContinue
    if (-not $mode) {
        Write-Log "Could not read review mode, defaulting to 'diff'" "WARN"
        return "diff"
    }
    $mode = $mode.Trim().ToLower()
    if ($mode -notin @("full", "diff")) {
        Write-Log "Invalid review mode '$mode', defaulting to 'diff'" "WARN"
        return "diff"
    }
    return $mode
}

function Get-CodeDiff {
    param([string]$Mode)
    
    Write-Log "Getting code diff for mode: $Mode"
    
    try {
        if ($Mode -eq "full") {
            # Get full repository diff from initial commit
            $initialCommit = git rev-list --max-parents=0 HEAD 2>$null
            if ($initialCommit) {
                $diff = git diff --unified=3 "$initialCommit..HEAD" -- . ":(exclude)**/*.md" 2>$null
            } else {
                # Fallback: show all files as diff
                $diff = git show --format="" --unified=3 HEAD -- . ":(exclude)**/*.md" 2>$null
            }
        } else {
            # Get diff for most recent commit only
            $diff = git show --format="" --unified=3 HEAD -- . ":(exclude)**/*.md" 2>$null
        }
        
        if (-not $diff -or $diff.Length -eq 0) {
            Write-Log "No code changes found (excluding .md files)" "WARN"
            return $null
        }
        
        Write-Log "Retrieved diff: $($diff.Length) characters"
        return $diff
    } catch {
        Write-Log "Failed to get git diff: $_" "ERROR"
        return $null
    }
}

function Invoke-OpenAIReview {
    param([string]$Diff, [string]$Mode)
    
    Write-Log "Sending request to OpenAI ($Model)..."
    
    $userContent = if ($Mode -eq "full") {
        "FULL REPOSITORY REVIEW`n$Diff`n`nReturn ONLY valid JSON with keys: summary, findings, tests, security_concurrency, go_no_go."
    } else {
        "RECENT COMMIT REVIEW`n$Diff`n`nReturn ONLY valid JSON with keys: summary, findings, tests, security_concurrency, go_no_go."
    }
    
    $requestBody = @{
        model = $Model
        temperature = 0
        response_format = @{type = "json_object"}
        messages = @(
            @{
                role = "system"
                content = $SystemPrompt
            }
            @{
                role = "user"
                content = $userContent
            }
        )
    } | ConvertTo-Json -Depth 10
    
    try {
        $headers = @{
            "Authorization" = "Bearer $OpenAIApiKey"
            "Content-Type" = "application/json"
        }
        
        $response = Invoke-RestMethod -Uri "https://api.openai.com/v1/chat/completions" -Method Post -Headers $headers -Body $requestBody
        
        if ($response.choices -and $response.choices[0].message.content) {
            Write-Log "Received response from OpenAI"
            return $response.choices[0].message.content
        } else {
            Write-Log "Invalid response structure from OpenAI" "ERROR"
            return $null
        }
    } catch {
        Write-Log "Failed to call OpenAI API: $_" "ERROR"
        return $null
    }
}

function Convert-JsonToMarkdown {
    param([string]$JsonContent, [string]$Mode)
    
    try {
        $review = $JsonContent | ConvertFrom-Json
        
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss UTC"
        $commitHash = git rev-parse HEAD 2>$null
        $commitMessage = git log -1 --pretty=format:"%s" 2>$null
        
        $markdown = @"
# Code Review - $Mode Mode

**Date**: $timestamp  
**Commit**: $commitHash  
**Message**: $commitMessage  
**Model**: $Model  

## Summary
"@
        
        if ($review.summary -is [array]) {
            foreach ($item in $review.summary) {
                $markdown += "`n- $item"
            }
        } else {
            $markdown += "`n- $($review.summary)"
        }
        
        $markdown += "`n`n## Findings`n"
        
        if ($review.findings -and $review.findings.Count -gt 0) {
            for ($i = 0; $i -lt $review.findings.Count; $i++) {
                $finding = $review.findings[$i]
                $markdown += "`n### Finding $($i + 1)`n"
                $markdown += "**File**: $($finding.file)`n"
                $markdown += "**Lines**: $($finding.lines)`n"
                $markdown += "**Severity**: $($finding.severity)`n`n"
                $markdown += "$($finding.description)`n`n"
                if ($finding.suggestion) {
                    $markdown += "**Suggested Fix**:`n``````n$($finding.suggestion)`n```````n"
                }
            }
        } else {
            $markdown += "No findings identified.`n"
        }
        
        $markdown += "`n## Tests`n"
        if ($review.tests -is [array] -and $review.tests.Count -gt 0) {
            foreach ($test in $review.tests) {
                $markdown += "- $test`n"
            }
        } elseif ($review.tests) {
            $markdown += "$($review.tests)`n"
        } else {
            $markdown += "No test recommendations.`n"
        }
        
        $markdown += "`n## Security/Concurrency`n"
        if ($review.security_concurrency -is [array] -and $review.security_concurrency.Count -gt 0) {
            foreach ($item in $review.security_concurrency) {
                $markdown += "- $item`n"
            }
        } elseif ($review.security_concurrency) {
            $markdown += "$($review.security_concurrency)`n"
        } else {
            $markdown += "No security or concurrency issues identified.`n"
        }
        
        $markdown += "`n## Recommendation`n"
        $markdown += "**$($review.go_no_go)**`n"
        
        $markdown += "`n---`n*Generated by automated code review system using OpenAI $Model*"
        
        return $markdown
    } catch {
        Write-Log "Failed to parse JSON response: $_" "ERROR"
        return "# Code Review Failed`n`nFailed to parse OpenAI response.`n`n## Raw Response`n``````json`n$JsonContent`n```````n"
    }
}

function Save-Review {
    param([string]$Content, [string]$Mode)
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $filename = "${timestamp}_${Mode}_review.md"
    $filepath = Join-Path $ReviewsDir $filename
    
    try {
        $Content | Out-File -FilePath $filepath -Encoding UTF8
        Write-Log "Review saved to: $filepath"
        return $filepath
    } catch {
        Write-Log "Failed to save review: $_" "ERROR"
        return $null
    }
}

# Main execution
function Main {
    Write-Log "Starting post-push code review..."
    
    if (-not (Test-Prerequisites)) {
        Write-Log "Prerequisites not met, exiting" "ERROR"
        exit 1
    }
    
    $reviewMode = Get-ReviewMode
    Write-Log "Review mode: $reviewMode"
    
    $diff = Get-CodeDiff -Mode $reviewMode
    if (-not $diff) {
        Write-Log "No code changes to review, creating minimal report..."
        $minimalReview = @"
# Code Review - $reviewMode Mode

**Date**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss UTC")  
**Commit**: $(git rev-parse HEAD 2>$null)  
**Message**: $(git log -1 --pretty=format:"%s" 2>$null)  
**Result**: No applicable code changes found (non-.md files)

## Summary
- No code changes detected in this commit
- Only documentation or configuration files were modified
- No review required

## Recommendation
**GO** - No code changes to review
"@
        $savedPath = Save-Review -Content $minimalReview -Mode $reviewMode
        if ($savedPath) {
            Write-Log "Minimal review completed successfully"
        }
        exit 0
    }
    
    $reviewJson = Invoke-OpenAIReview -Diff $diff -Mode $reviewMode
    if (-not $reviewJson) {
        Write-Log "Failed to get review from OpenAI" "ERROR"
        exit 1
    }
    
    $reviewMarkdown = Convert-JsonToMarkdown -JsonContent $reviewJson -Mode $reviewMode
    $savedPath = Save-Review -Content $reviewMarkdown -Mode $reviewMode
    
    if ($savedPath) {
        Write-Log "Code review completed successfully: $savedPath"
        
        # Show summary in console
        Write-Log "Review Summary:"
        try {
            $review = $reviewJson | ConvertFrom-Json
            Write-Host "  GO/NO-GO: $($review.go_no_go)" -ForegroundColor $(if ($review.go_no_go -eq "GO") { "Green" } else { "Red" })
            Write-Host "  Findings: $($review.findings.Count) issues identified"
        } catch {
            Write-Log "Could not parse review summary" "WARN"
        }
    } else {
        Write-Log "Failed to save review" "ERROR"
        exit 1
    }
}

# Execute main function
Main